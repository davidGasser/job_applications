import logging
import atexit
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from models import db, SearchCriteria

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

# Module-level references, set once from main.py on startup
_app = None
_run_scraping_task_func = None

def run_scheduled_scrape(criteria_id, app, run_scraping_task_func):
    """Function called by APScheduler to run a scheduled scrape."""
    with app.app_context():
        try:
            criteria = SearchCriteria.query.get(criteria_id)
            if not criteria or not criteria.schedule_enabled:
                logging.warning(f"Skipping scheduled scrape for criteria {criteria_id}: not found or disabled")
                return

            logging.info(f"Running scheduled scrape for: {criteria.keywords}")

            # Update last_run timestamp
            criteria.last_run = datetime.now()
            db.session.commit()

            # Create the scraper data object (pages will be pulled from criteria)
            data = {
                'id': criteria_id
            }

            # Run the scraping task directly (not via SocketIO since this is background)
            run_scraping_task_func(data)

        except Exception as e:
            logging.error(f"Error in scheduled scrape for criteria {criteria_id}: {e}")

def sync_scheduler_jobs(app=None, run_scraping_task_func=None):
    """Synchronize APScheduler jobs with enabled SearchCriteria in database.

    On first call (from main.py), pass app and run_scraping_task_func to store them.
    Subsequent calls (from routes) can omit these args and the stored references are used.
    """
    global _app, _run_scraping_task_func

    # Store references if provided (first call from main.py)
    if app is not None:
        _app = app
    if run_scraping_task_func is not None:
        _run_scraping_task_func = run_scraping_task_func

    # Use stored references if args not provided (calls from routes)
    effective_app = app or _app
    effective_func = run_scraping_task_func or _run_scraping_task_func

    if effective_app is None:
        # Fallback to current_app if no stored app
        from flask import current_app
        effective_app = current_app._get_current_object()

    with effective_app.app_context():
        # Remove all existing jobs
        scheduler.remove_all_jobs()

        # Add jobs for all enabled schedules
        enabled_criteria = SearchCriteria.query.filter_by(schedule_enabled=True, is_template=True).all()

        for criteria in enabled_criteria:
            if criteria.schedule_hour is None:
                continue  # Skip if no time is set

            job_id = f"scrape_{criteria.id}"

            # Get timezone (default to UTC if not set)
            timezone = criteria.schedule_timezone or 'UTC'

            # Use interval-based scheduling
            interval_hours = criteria.schedule_interval_hours or 24

            trigger = IntervalTrigger(
                hours=interval_hours,
                timezone=timezone,
                start_date=datetime.now().replace(
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0,
                    second=0,
                    microsecond=0
                )
            )

            # Only add the job if we have the scraping function
            if effective_func:
                scheduler.add_job(
                    func=run_scheduled_scrape,
                    trigger=trigger,
                    args=[criteria.id, effective_app, effective_func],
                    id=job_id,
                    name=f"Scrape: {criteria.keywords}",
                    replace_existing=True
                )
                logging.info(f"Scheduled job added: {criteria.keywords} - every {interval_hours}h starting at {criteria.schedule_hour:02d}:{(criteria.schedule_minute or 0):02d} {timezone}")
