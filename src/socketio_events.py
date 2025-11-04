import logging
from models import db, SearchCriteria, Job
from scrapers import LinkedInScraper
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import threading

# Global flag to interrupt scraping
scraping_active = False

def register_socketio_events(socketio, app):
    """Register all SocketIO event handlers."""

    @socketio.on('stop_scrape')
    def handle_stop_scrape():
        global scraping_active
        scraping_active = False
        socketio.emit('scrape_stopped', {'data': 'Scraping interrupted by user'})

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
        def rating_worker(queue):
            """
            Worker function that processes jobs from the queue.
            Runs in its own thread, continuously pulling and processing jobs.
            """
            while True:
                job_data = queue.get()  # Blocks here waiting for a job

                try:
                    # Check for sentinel (stop signal)
                    if job_data is None:
                        logging.info("Worker received stop signal, shutting down...")
                        break  # Exit the loop, worker stops

                    # Wait for search_criteria_id to be available
                    # (The scraper thread will set this once it creates the SearchCriteria)
                    while search_criteria_id_holder[0] is None:
                        socketio.sleep(0.1)  # Wait a bit before checking again

                    search_criteria_id = search_criteria_id_holder[0]

                    with app.app_context():
                        # Check if job already exists in DB
                        exists = db.session.query(Job.application_link).filter_by(
                            application_link=job_data["application_link"]
                        ).first() is not None

                        if not exists:
                            # TODO: Rate the job with Ollama
                            # score = rate_job(job_data["description"], cv_text, preferences)
                            # job_data["matching_score"] = score

                            # Placeholder score for now
                            job_data["matching_score"] = 0.0

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
                            })
                            logging.info(f"Saved job: {job_data['title']} @ {job_data['company']} - {job_data['location']}")

                except Exception as e:
                    logging.error(f"Error processing job: {e}")
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
            try:
                with app.app_context():
                    # Send initial confirmation that scraping started
                    socketio.emit('log_message', {'data': 'Scraping task started...'})
                    socketio.sleep(0.1)  # Small delay to ensure message is sent

                    # Validate that template ID is provided
                    if 'id' not in data or not data['id']:
                        socketio.emit('scrape_error', {'data': 'No search criteria template ID provided'})
                        return

                    # Fetch the template
                    template = SearchCriteria.query.get(data['id'])
                    if not template:
                        socketio.emit('scrape_error', {'data': 'Search criteria template not found'})
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
                    logging.info(f"Created search criteria run with ID: {search_criteria.id}")

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
                        logging.info("Scraping was stopped by user")
                        socketio.emit('scrape_stopped', {'data': 'Scraping was stopped by user'})
                    else:
                        logging.info("Scraping finished successfully")

            except Exception as e:
                logging.error(f"An error occurred during scraping: {e}")
                socketio.emit('scrape_error', {'data': str(e)})
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
            logging.info("Starting 3 rating workers...")
            rating_futures = []
            for i in range(3):
                future = executor.submit(rating_worker, job_queue)
                rating_futures.append(future)

            # Create and start the scraper thread
            logging.info("Starting scraper thread...")
            scraper_thread = threading.Thread(
                target=scrape_and_queue,
                args=(job_queue,)
            )
            scraper_thread.start()

            # Wait for scraper thread to finish
            logging.info("Waiting for scraper to finish...")
            scraper_thread.join()
            logging.info("Scraper thread finished")

            # Send sentinels (stop signals) to workers - one per worker
            logging.info("Sending stop signals to workers...")
            for _ in range(3):
                job_queue.put(None)

            # Wait for all jobs in queue to be processed
            logging.info("Waiting for all jobs to be processed...")
            job_queue.join()
            logging.info("All jobs processed")

            # Shutdown the executor and wait for workers to finish
            logging.info("Shutting down executor...")
            executor.shutdown(wait=True)
            logging.info("Executor shut down successfully")

            # Send final completion message
            socketio.emit('scrape_finished', {
                'data': 'Scraping and rating complete!'
            })

        except Exception as e:
            logging.error(f"Error in scraping pipeline: {e}")
            socketio.emit('scrape_error', {'data': str(e)})
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
