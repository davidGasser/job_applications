import logging
import os
from models import db, SearchCriteria, Job, UserProfile
from scrapers import LinkedInScraper
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import threading
from sqlalchemy.exc import IntegrityError
import json

from job_scoring import score_with_summary_gemini
from google import genai


# Setup component-specific loggers
# worker_logger = logging.getLogger('workers')
queue_logger = logging.getLogger('queue')

# Global flag to interrupt scraping
scraping_active = False

def register_socketio_events(socketio, app):
    """Register all SocketIO event handlers."""

    @socketio.on('stop_scrape')
    def handle_stop_scrape():
        global scraping_active
        scraping_active = False
        socketio.emit('scrape_stopped', {'data': 'Scraping interrupted by user'}, namespace='/')

    def run_scraping_task(data):
        """Background task to run the scraper."""
        global scraping_active
        scraping_active = True  # Set active flag for both manual and scheduled scrapes

        # Shared variable to pass search_criteria_id between threads
        # We use a list so it can be modified inside nested functions
        search_criteria_id_holder = [None]

        # ===================================================================
        # STEP 1: Define the rating_worker function (runs in worker threads)
        # ===================================================================
        def rating_worker(queue, worker_id):
            """
            Worker function that processes jobs from the queue.
            Runs in its own thread, continuously pulling and processing jobs.
            """
            # worker_logger.info(f"Worker {worker_id} started")

            # Load CV and preferences once, outside the loop
            with app.app_context():
                user_profile = UserProfile.query.first()
                if user_profile:
                    cv_text = user_profile.cv_text or ""
                    preferences = user_profile.job_preferences or ""
                    no_preferences = user_profile.no_preferences or ""
                else:
                    cv_text = ""
                    preferences = ""
                    no_preferences = ""

                if not cv_text or not preferences:
                    queue_logger.warning("No user profile found. Jobs will be assigned default score of 80.")

            # Create Gemini client ONCE per worker for efficient connection reuse
            # This significantly improves performance for parallel processing
            gemini_client = genai.Client(api_key=os.getenv("API_KEY_GEMINI"))

            while True:
                job_data = queue.get()  # Blocks here waiting for a job

                try:
                    # Check for sentinel (stop signal)
                    if job_data is None:
                        # worker_logger.info(f"Worker {worker_id} received stop signal, shutting down")
                        break  # Exit the loop, worker stops

                    # worker_logger.info(f"Worker {worker_id} picked up: {job_data['title']} @ {job_data['company']}")

                    # Wait for search_criteria_id to be available
                    # (The scraper thread will set this once it creates the SearchCriteria)
                    while search_criteria_id_holder[0] is None:
                        socketio.sleep(0.1)  # Wait a bit before checking again

                    search_criteria_id = search_criteria_id_holder[0]

                    with app.app_context():
                        # Check if job already exists in DB (avoids wasting time rating duplicates)
                        exists = db.session.query(Job.application_link).filter_by(
                            application_link=job_data["application_link"]
                        ).first() is not None

                        if exists:
                            queue_logger.info(f"Found and skipped duplicate: {job_data['title']}")
                        else:
                            # Score the job
                            if not cv_text or not preferences:
                                # No CV/preferences available, use default score of 80
                                score_dict = {
                                    "skillset": 80,
                                    "academic": 80,
                                    "experience": 80,
                                    "professional": 80,
                                    "language": 80,
                                    "preference": 80,
                                    "overall": 80,
                                    "reasoning": {
                                        "strengths": ["No CV/preferences provided - default score applied"],
                                        "concerns": [],
                                        "summary": "Default score applied due to missing user profile information."
                                    }
                                }
                                matching_score = 80.0
                            else:
                                # Score using the LLM (reuse the same client for efficiency)
                                score_dict = score_with_summary_gemini(
                                    job_data, cv_text, preferences, no_preferences,
                                    client=gemini_client
                                )
                                matching_score = float(score_dict.get("overall", 0))

                            # Store the overall score and full details
                            job_data["matching_score"] = matching_score
                            job_data["score_details"] = json.dumps(score_dict)

                            try:
                                # Save to database
                                job = Job(**job_data, search_criteria_id=search_criteria_id)
                                db.session.add(job)
                                db.session.commit()

                                # Notify frontend
                                socketio.emit('job_processed', {
                                    'job': job_data['title'],
                                    'company': job_data['company'],
                                    'location': job_data['location'],
                                    'score': job_data['matching_score']
                                }, namespace='/')
                                # worker_logger.info(f"Worker {worker_id} saved: {job_data['title']} @ {job_data['company']}")

                            except IntegrityError:
                                # Race condition: Another worker inserted it between our check and insert
                                db.session.rollback()
                                # worker_logger.info(f"Worker {worker_id} race condition on: {job_data['title']}")

                except Exception as e:
                    # worker_logger.error(f"Worker {worker_id} error: {e}")
                    db.session.rollback()
                    # Continue to next job even if this one failed

                finally:
                    # Mark this job as done (important for queue.join())
                    queue.task_done()

        # ===================================================================
        # STEP 2: Define the scrape_and_queue function (runs in scraper thread)
        # ===================================================================
        def scrape_and_queue(job_queue):
            """
            Scraper function that runs in its own thread.
            Creates the scraper and calls scrape_jobs(), which puts jobs
            directly into the queue as they're scraped (streaming).
            """
            global scraping_active  # Need to declare global to access/modify it
            try:
                with app.app_context():
                    # Send initial confirmation that scraping started
                    socketio.emit('log_message', {'data': 'Scraping task started...'}, namespace='/')
                    socketio.sleep(0.1)  # Small delay to ensure message is sent

                    # Validate that template ID is provided
                    if 'id' not in data or not data['id']:
                        socketio.emit('scrape_error', {'data': 'No search criteria template ID provided'}, namespace='/')
                        return

                    # Fetch the template
                    template = SearchCriteria.query.get(data['id'])
                    if not template:
                        socketio.emit('scrape_error', {'data': 'Search criteria template not found'}, namespace='/')
                        return

                    # Create a new run from the template (is_template=False)
                    search_criteria = SearchCriteria(
                        keywords=template.keywords,
                        locations=template.locations,
                        distance_in_km=template.distance_in_km,
                        date_posted=template.date_posted,
                        exp_level=template.exp_level,
                        job_type=template.job_type,
                        pages=template.pages,
                        is_template=False  # This is a run, not a template
                    )
                    db.session.add(search_criteria)
                    db.session.commit()

                    # IMPORTANT: Put the search_criteria_id into the holder
                    # so workers can access it
                    search_criteria_id_holder[0] = search_criteria.id
                    queue_logger.info(f"Created search criteria run with ID: {search_criteria.id}")

                    # Create the scraper
                    scraper = LinkedInScraper(
                        keywords=search_criteria.keywords,
                        locations=[loc.strip() for loc in search_criteria.locations.split(',')],
                        distance_in_km=search_criteria.distance_in_km,
                        date_posted=search_criteria.date_posted,
                        exp_level=search_criteria.exp_level.split(', ') if search_criteria.exp_level else None,
                        job_type=search_criteria.job_type.split(', ') if search_criteria.job_type else None,
                        pages=search_criteria.pages,
                        stop_callback=lambda: not scraping_active  # Pass stop check callback
                    )

                    # Start scraping! The scraper will put jobs into the queue
                    # one-by-one as it finds them (streaming)
                    scraper.scrape_jobs(job_queue)

                    # Check if scraping was stopped early
                    if not scraping_active:
                        queue_logger.info("Scraping was stopped by user")
                        socketio.emit('scrape_stopped', {'data': 'Scraping was stopped by user'}, namespace='/')
                    else:
                        queue_logger.info("Scraping finished successfully")

            except Exception as e:
                queue_logger.error(f"An error occurred during scraping: {e}")
                socketio.emit('scrape_error', {'data': str(e)}, namespace='/')
            finally:
                scraping_active = False

        # ===================================================================
        # STEP 3: Orchestrate the pipeline
        # ===================================================================

        # Create the job queue (mailbox for jobs)
        job_queue = Queue(maxsize=50)  # Limit to 50 to prevent memory issues

        # Create the thread pool executor (manages worker threads)
        executor = ThreadPoolExecutor(max_workers=3)

        try:
            # Start the 3 rating workers
            queue_logger.info("Starting 3 rating workers...")
            rating_futures = []
            for i in range(3):
                worker_id = i + 1
                future = executor.submit(rating_worker, job_queue, worker_id)
                rating_futures.append(future)

            # Create and start the scraper thread
            queue_logger.info("Starting scraper thread...")
            scraper_thread = threading.Thread(
                target=scrape_and_queue,
                args=(job_queue,)
            )
            scraper_thread.start()

            # Wait for scraper thread to finish
            scraper_thread.join()
            queue_logger.info("Scraper thread finished")

            # Send sentinels (stop signals) to workers - one per worker
            queue_logger.info("Sending stop signals to workers...")
            for _ in range(3):
                job_queue.put(None)

            # Wait for all jobs in queue to be processed
            queue_logger.info("Waiting for all jobs to be processed...")
            job_queue.join()
            queue_logger.info("All jobs processed successfully")

            # Shutdown the executor and wait for workers to finish
            queue_logger.info("Shutting down executor...")
            executor.shutdown(wait=True)
            queue_logger.info("Executor shut down successfully")

            # Send final completion message
            socketio.emit('scrape_finished', {
                'data': 'Scraping and rating complete!'
            }, namespace='/')

        except Exception as e:
            logging.error(f"Error in scraping pipeline: {e}")
            socketio.emit('scrape_error', {'data': str(e)}, namespace='/')
        finally:
            # Ensure cleanup even if there's an error
            scraping_active = False
            executor.shutdown(wait=False)

    @socketio.on('start_scrape')
    def handle_start_scrape(json):
        data = json.get('data')
        # Run scraping in background thread to avoid blocking SocketIO
        socketio.start_background_task(run_scraping_task, data)

    # Return the run_scraping_task function so it can be used by the scheduler
    return run_scraping_task
