import logging
import atexit
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from models import db, SearchCriteria

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

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
    """Synchronize APScheduler jobs with enabled SearchCriteria in database."""
    # Import here to avoid circular imports
    from flask import current_app

    if app is None:
        app = current_app._get_current_object()

    with app.app_context():
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

            # Determine frequency based on date_posted
            if criteria.date_posted == 'past 24 hours':
                # Daily schedule
                trigger = CronTrigger(
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0,
                    timezone=timezone
                )
            elif criteria.date_posted == 'past week':
                # Weekly schedule
                trigger = CronTrigger(
                    day_of_week=criteria.schedule_day_of_week or 0,  # Default to Monday
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0,
                    timezone=timezone
                )
            elif criteria.date_posted == 'past month':
                # Monthly schedule
                trigger = CronTrigger(
                    day=criteria.schedule_day_of_month or 1,  # Default to 1st of month
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0,
                    timezone=timezone
                )
            else:
                # Default to weekly if date_posted not specified
                trigger = CronTrigger(
                    day_of_week=criteria.schedule_day_of_week or 0,
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0,
                    timezone=timezone
                )

            # Only add the job if we have the scraping function
            if run_scraping_task_func:
                scheduler.add_job(
                    func=run_scheduled_scrape,
                    trigger=trigger,
                    args=[criteria.id, app, run_scraping_task_func],
                    id=job_id,
                    name=f"Scrape: {criteria.keywords}",
                    replace_existing=True
                )
                logging.info(f"Scheduled job added: {criteria.keywords} - {trigger}")
