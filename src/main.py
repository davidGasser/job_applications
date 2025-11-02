import os
import logging

# --- Debugpy Setup (MUST be before any gevent imports) ---
# Enable debugpy for remote debugging from VS Code
if os.environ.get('ENABLE_DEBUGPY', '0') == '1':
    os.environ['GEVENT_SUPPORT'] = 'True'
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))
    print("⏳ Debugger is waiting for client to attach on port 5678...")
    # Uncomment the next line if you want the app to wait for debugger to attach before continuing
    # debugpy.wait_for_client()
    print("✅ Debugger ready!")

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup
from scrapers import LinkedInScraper
from flask_socketio import SocketIO
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

from datetime import datetime

# --- App and DB Setup ---
app = Flask(__name__, template_folder='../templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)

# --- Logging Setup for Real-time Updates ---
class SocketIOHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        # Emit to all connected clients (default behavior from background thread)
        socketio.emit('log_message', {'data': log_entry})

# Get the logger from scrapers.py and add our custom handler
scraper_logger = logging.getLogger('scrapers')
scraper_logger.setLevel(logging.INFO)
scraper_logger.addHandler(SocketIOHandler())

# --- Jinja Filter ---
def nl2br_filter(s):
    return Markup(s.replace('\n', '<br>'))
app.jinja_env.filters['nl2br'] = nl2br_filter

# --- DB Model ---
class SearchCriteria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.String(255), nullable=False)
    locations = db.Column(db.String(255), nullable=False)
    distance_in_km = db.Column(db.Integer, nullable=True)
    date_posted = db.Column(db.String(50), nullable=True)
    exp_level = db.Column(db.String(255), nullable=True)
    job_type = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_processed = db.Column(db.Boolean, nullable=False, default=False)
    is_template = db.Column(db.Boolean, nullable=False, default=True)  # True = saved config, False = search run
    schedule_enabled = db.Column(db.Boolean, nullable=False, default=False)
    schedule_hour = db.Column(db.Integer, nullable=True)  # 0-23
    schedule_minute = db.Column(db.Integer, nullable=True, default=0)  # 0-59
    schedule_day_of_week = db.Column(db.Integer, nullable=True)  # 0-6 for weekly (Monday=0)
    schedule_day_of_month = db.Column(db.Integer, nullable=True)  # 1-31 for monthly
    last_run = db.Column(db.DateTime, nullable=True)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    application_link = db.Column(db.Text, unique=True)
    scraped_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='New') # New, Interested, Applied, Interviewing, Offer, Rejected
    shortlisted = db.Column(db.Boolean, nullable=False, default=False)
    matching_score = db.Column(db.Float, nullable=False, default=0.0) # 0-100 percentage score
    notes = db.Column(db.Text, nullable=True)
    search_criteria_id = db.Column(db.Integer, db.ForeignKey('search_criteria.id'), nullable=True)
    search_criteria = db.relationship('SearchCriteria', backref=db.backref('jobs', lazy=True))
    dates = db.relationship('JobDate', backref='job', lazy=True, cascade="all, delete-orphan")
    contacts = db.relationship('Contact', backref='job', lazy=True, cascade="all, delete-orphan")

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(255), nullable=False)

class JobDate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Job {self.title} @ {self.company}>'

# --- HTTP Routes ---
@app.route('/search_criteria', methods=['POST'])
def create_search_criteria():
    try:
        data = request.json
        new_criteria = SearchCriteria(
            keywords=data['keywords'],
            locations=data['locations'],
            distance_in_km=data.get('distance_in_km'),
            date_posted=data.get('date_posted'),
            exp_level=data.get('exp_level'),
            job_type=data.get('job_type'),
            schedule_enabled=data.get('schedule_enabled', False),
            schedule_hour=data.get('schedule_hour'),
            schedule_minute=data.get('schedule_minute', 0),
            schedule_day_of_week=data.get('schedule_day_of_week'),
            schedule_day_of_month=data.get('schedule_day_of_month')
        )
        db.session.add(new_criteria)
        db.session.commit()

        # Sync scheduler if scheduling was enabled
        if new_criteria.schedule_enabled:
            sync_scheduler_jobs()

        return jsonify({'status': 'success', 'id': new_criteria.id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/search_criteria/<int:criteria_id>', methods=['GET'])
def get_search_criteria(criteria_id):
    try:
        criteria = SearchCriteria.query.get_or_404(criteria_id)
        return jsonify({
            'id': criteria.id,
            'keywords': criteria.keywords,
            'locations': criteria.locations,
            'distance_in_km': criteria.distance_in_km,
            'date_posted': criteria.date_posted,
            'exp_level': criteria.exp_level,
            'job_type': criteria.job_type,
            'schedule_enabled': criteria.schedule_enabled,
            'schedule_hour': criteria.schedule_hour,
            'schedule_minute': criteria.schedule_minute,
            'schedule_day_of_week': criteria.schedule_day_of_week,
            'schedule_day_of_month': criteria.schedule_day_of_month,
            'last_run': criteria.last_run.isoformat() if criteria.last_run else None
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/search_criteria/<int:criteria_id>', methods=['PUT'])
def update_search_criteria(criteria_id):
    try:
        data = request.json
        criteria = SearchCriteria.query.get_or_404(criteria_id)
        criteria.keywords = data.get('keywords', criteria.keywords)
        criteria.locations = data.get('locations', criteria.locations)
        criteria.distance_in_km = data.get('distance_in_km', criteria.distance_in_km)
        criteria.date_posted = data.get('date_posted', criteria.date_posted)
        criteria.exp_level = data.get('exp_level', criteria.exp_level)
        criteria.job_type = data.get('job_type', criteria.job_type)

        # Update scheduling fields if provided
        if 'schedule_enabled' in data:
            criteria.schedule_enabled = data['schedule_enabled']
        if 'schedule_hour' in data:
            criteria.schedule_hour = data['schedule_hour']
        if 'schedule_minute' in data:
            criteria.schedule_minute = data['schedule_minute']
        if 'schedule_day_of_week' in data:
            criteria.schedule_day_of_week = data['schedule_day_of_week']
        if 'schedule_day_of_month' in data:
            criteria.schedule_day_of_month = data['schedule_day_of_month']

        db.session.commit()

        # Sync scheduler whenever criteria is updated
        sync_scheduler_jobs()

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/search_criteria/<int:criteria_id>', methods=['DELETE'])
def delete_search_criteria(criteria_id):
    try:
        criteria = SearchCriteria.query.get_or_404(criteria_id)

        # Detach jobs from this criteria (archive them) before deleting the criteria
        jobs = Job.query.filter_by(search_criteria_id=criteria_id).all()
        for job in jobs:
            job.search_criteria_id = None

        # Now delete the search criteria
        db.session.delete(criteria)
        db.session.commit()

        # Sync scheduler to remove any scheduled jobs for this criteria
        sync_scheduler_jobs()

        return jsonify({'status': 'success', 'archived_jobs': len(jobs)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/search_criterias')
def get_search_criterias():
    try:
        # Only return templates (saved configurations), not search runs
        criterias = SearchCriteria.query.filter_by(is_template=True).all()
        return jsonify([{
            'id': c.id,
            'keywords': c.keywords,
            'locations': c.locations,
            'distance_in_km': c.distance_in_km,
            'date_posted': c.date_posted,
            'exp_level': c.exp_level,
            'job_type': c.job_type,
            'schedule_enabled': c.schedule_enabled,
            'schedule_hour': c.schedule_hour,
            'schedule_minute': c.schedule_minute,
            'schedule_day_of_week': c.schedule_day_of_week,
            'schedule_day_of_month': c.schedule_day_of_month,
            'last_run': c.last_run.isoformat() if c.last_run else None
        } for c in criterias])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
def index():
    import random

    # Get all jobs and assign random scores if not set
    jobs = Job.query.all()
    for job in jobs:
        if job.matching_score == 0.0:
            job.matching_score = round(random.uniform(60, 100), 1)
    db.session.commit()

    # Get search runs (not templates) with job counts
    search_criterias = SearchCriteria.query.filter_by(is_template=False).all()
    scrapes = []
    for sc in search_criterias:
        job_count = Job.query.filter_by(search_criteria_id=sc.id).count()
        if job_count > 0:  # Only include scrapes that have jobs
            non_shortlisted_count = Job.query.filter_by(search_criteria_id=sc.id, shortlisted=False).count()

            scrapes.append({
                'id': sc.id,
                'keywords': sc.keywords,
                'locations': sc.locations,
                'distance_in_km': sc.distance_in_km,
                'date_posted': sc.date_posted,
                'exp_level': sc.exp_level,
                'job_type': sc.job_type,
                'job_count': job_count,
                'non_shortlisted_count': non_shortlisted_count,
                'is_processed': sc.is_processed,
                'created_at': sc.created_at,
                'is_archived': False
            })

    # Add archived jobs (jobs with no search_criteria_id and shortlisted) as a special scrape
    # Only shortlisted jobs should be in archived
    archived_job_count = Job.query.filter_by(search_criteria_id=None, shortlisted=True).count()
    if archived_job_count > 0:
        scrapes.append({
            'id': 'archived',
            'keywords': 'Archived Jobs',
            'locations': 'Various',
            'distance_in_km': None,
            'date_posted': None,
            'exp_level': None,
            'job_type': None,
            'job_count': archived_job_count,
            'non_shortlisted_count': 0,  # No non-shortlisted jobs in archived
            'is_processed': True,  # Archived jobs are always "processed"
            'created_at': datetime.utcnow(),  # Current time for sorting
            'is_archived': True
        })

    # Sort by most recent
    scrapes.sort(key=lambda x: x['created_at'], reverse=True)

    return render_template('index.html', scrapes=scrapes, active_page='index')

@app.route('/scrape')
def scrape():
    return render_template(
        'scrape.html',
        distance_map=LinkedInScraper.DISTANCE_MAP,
        date_map=LinkedInScraper.DATE_MAP,
        exp_level_map=LinkedInScraper.EXP_LEVEL_MAP,
        job_type_map=LinkedInScraper.JOB_TYPE_MAP,
        active_page='scrape'
    )

@app.route('/calendar')
def calendar():
    return render_template('calendar.html', active_page='calendar')

@app.route('/kanban')
def kanban():
    statuses = ['Interested', 'Applied', 'Interviewing', 'Offer', 'Rejected']
    jobs = Job.query.filter_by(shortlisted=True).order_by(Job.id.desc()).all()
    return render_template('kanban.html', jobs=jobs, statuses=statuses, active_page='kanban')

@app.route('/job', methods=['POST'])
def create_job():
    try:
        data = request.json
        # Handle application_link - if empty, set to None to avoid unique constraint issues
        app_link = data.get('application_link')
        if app_link == '':
            app_link = None

        # Explicitly convert shortlisted to boolean
        shortlisted_val = data.get('shortlisted', False)
        if isinstance(shortlisted_val, str):
            shortlisted_val = shortlisted_val.lower() == 'true'

        new_job = Job(
            title=data['title'],
            company=data.get('company'),
            location=data.get('location'),
            description=data.get('description'),
            application_link=app_link,
            notes=data.get('notes'),
            status=data.get('status', 'New'),
            shortlisted=bool(shortlisted_val)
        )
        db.session.add(new_job)
        db.session.commit()

        return jsonify({
            'id': new_job.id,
            'title': new_job.title,
            'company': new_job.company
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        db.session.delete(job)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Job deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>/status', methods=['POST'])
def update_job_status(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        new_status = request.json.get('status')
        if new_status:
            job.status = new_status
            db.session.commit()
            return jsonify({'status': 'success', 'new_status': new_status})
        return jsonify({'status': 'error', 'message': 'No status provided'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>/shortlist', methods=['POST'])
def toggle_shortlist(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        job.shortlisted = not job.shortlisted
        # If shortlisting for the first time, set status to Interested
        if job.shortlisted and job.status == 'New':
            job.status = 'Interested'
        # If un-shortlisting, reset to New
        elif not job.shortlisted:
            job.status = 'New'
        db.session.commit()
        return jsonify({'status': 'success', 'shortlisted': job.shortlisted, 'job_status': job.status})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>/details', methods=['GET'])
def get_job_details(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        dates = []
        for d in job.dates:
            dates.append({
                'id': d.id,
                'date': d.date.isoformat(),
                'title': d.title,
                'description': d.description
            })
        contacts = []
        for c in job.contacts:
            contacts.append({
                'id': c.id,
                'name': c.name,
                'type': c.type,
                'value': c.value
            })
        return jsonify({
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'location': job.location,
            'description': job.description,
            'application_link': job.application_link,
            'status': job.status,
            'shortlisted': job.shortlisted,
            'notes': job.notes,
            'dates': dates,
            'contacts': contacts,
            'scraped_at': job.scraped_at.isoformat(),
            'updated_at': job.updated_at.isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>/details', methods=['POST'])
def update_job_details(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        data = request.json
        job.notes = data.get('notes', job.notes)
        job.contact_info = data.get('contact_info', job.contact_info)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Details updated'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/contact/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    try:
        data = request.json
        contact = Contact.query.get_or_404(contact_id)
        contact.name = data.get('name', contact.name)
        contact.type = data.get('type', contact.type)
        contact.value = data.get('value', contact.value)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/contact/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    try:
        contact = Contact.query.get_or_404(contact_id)
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>/contact', methods=['POST'])
def add_contact(job_id):
    try:
        data = request.json
        new_contact = Contact(
            job_id=job_id,
            name=data['name'],
            type=data['type'],
            value=data['value']
        )
        db.session.add(new_contact)
        db.session.commit()
        return jsonify({'status': 'success', 'id': new_contact.id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job/<int:job_id>/date', methods=['POST'])
def add_job_date(job_id):
    try:
        data = request.json
        new_date = JobDate(
            job_id=job_id,
            date=datetime.fromisoformat(data['date']),
            category=data['category'],
            title=data.get('title'),
            description=data.get('description')
        )
        db.session.add(new_date)
        db.session.commit()
        return jsonify({'status': 'success', 'id': new_date.id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job_date/<int:date_id>/details')
def get_job_date_details(date_id):
    try:
        job_date = JobDate.query.get_or_404(date_id)
        return jsonify({
            'id': job_date.id,
            'date': job_date.date.isoformat(),
            'title': job_date.title,
            'description': job_date.description
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job_date/<int:date_id>', methods=['PUT'])
def update_job_date(date_id):
    try:
        data = request.json
        job_date = JobDate.query.get_or_404(date_id)
        job_date.date = datetime.fromisoformat(data['date'])
        job_date.category = data['category']
        job_date.title = data.get('title')
        job_date.description = data.get('description')
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job_date/<int:date_id>', methods=['DELETE'])
def delete_job_date(date_id):
    try:
        job_date = JobDate.query.get_or_404(date_id)
        db.session.delete(job_date)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/scrape/<scrape_id>/jobs')
def get_scrape_jobs(scrape_id):
    try:
        # Handle archived jobs specially - only show shortlisted jobs
        if scrape_id == 'archived':
            jobs = Job.query.filter_by(search_criteria_id=None, shortlisted=True).order_by(Job.matching_score.desc()).all()
        else:
            jobs = Job.query.filter_by(search_criteria_id=int(scrape_id)).order_by(Job.matching_score.desc()).all()

        return jsonify([{
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'location': job.location,
            'description': job.description,
            'application_link': job.application_link,
            'shortlisted': job.shortlisted,
            'matching_score': job.matching_score,
            'scraped_at': job.scraped_at.isoformat(),
            'search_criteria': {
                'keywords': job.search_criteria.keywords,
                'locations': job.search_criteria.locations
            } if job.search_criteria else {'keywords': 'Archived', 'locations': 'Various'}
        } for job in jobs])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/scrape/<int:scrape_id>/confirm', methods=['POST'])
def confirm_scrape(scrape_id):
    try:
        # Delete all non-shortlisted jobs from this scrape
        jobs_to_delete = Job.query.filter_by(search_criteria_id=scrape_id, shortlisted=False).all()
        deleted_count = len(jobs_to_delete)
        for job in jobs_to_delete:
            db.session.delete(job)

        # Move all shortlisted jobs to archived (remove search_criteria_id)
        shortlisted_jobs = Job.query.filter_by(search_criteria_id=scrape_id, shortlisted=True).all()
        archived_count = len(shortlisted_jobs)
        for job in shortlisted_jobs:
            job.search_criteria_id = None

        # Delete the search criteria (scraper run)
        search_criteria = SearchCriteria.query.get_or_404(scrape_id)
        db.session.delete(search_criteria)

        db.session.commit()

        return jsonify({
            'status': 'success',
            'deleted_count': deleted_count,
            'archived_count': archived_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/job_dates')
def get_job_dates():
    try:
        dates = JobDate.query.all()
        events = []
        for d in dates:
            events.append({
                'title': d.title,
                'start': d.date.isoformat(),
                'extendedProps': {
                    'job_id': d.job_id,
                    'job_title': d.job.title,
                    'description': d.description
                }
            })
        return jsonify(events)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- WebSocket Event Handlers ---
# Global flag to interrupt scraping
scraping_active = False

@socketio.on('stop_scrape')
def handle_stop_scrape():
    global scraping_active
    scraping_active = False
    socketio.emit('scrape_stopped', {'data': 'Scraping interrupted by user'})

def run_scraping_task(data):
    """Background task to run the scraper."""
    global scraping_active
    scraping_active = True  # Set active flag for both manual and scheduled scrapes
    try:
        with app.app_context():
            # Send initial confirmation that scraping started
            socketio.emit('log_message', {'data': 'Scraping task started...'})
            socketio.sleep(0.1)  # Small delay to ensure message is sent

            # Always create a NEW SearchCriteria as a run (is_template=False)
            # The ID provided is for the template, we create a new run from it
            if 'id' in data and data['id']:
                template = SearchCriteria.query.get(data['id'])
                if not template:
                    socketio.emit('scrape_error', {'data': 'Search criteria template not found'})
                    return

                # Create a new run from the template
                search_criteria = SearchCriteria(
                    keywords=template.keywords,
                    locations=template.locations,
                    distance_in_km=template.distance_in_km,
                    date_posted=template.date_posted,
                    exp_level=template.exp_level,
                    job_type=template.job_type,
                    is_template=False  # This is a run, not a template
                )
                db.session.add(search_criteria)
                db.session.commit()
            else:
                # Direct scrape without template (old behavior, create run directly)
                keywords = data.get('keywords')
                locations = data.get('locations')
                distance_in_km = int(data.get('distance')) if data.get('distance') else None
                date_posted = data.get('date_posted') if data.get('date_posted') else None
                exp_level = ', '.join(data.get('exp_level', [])) if data.get('exp_level') else None
                job_type = ', '.join(data.get('job_type', [])) if data.get('job_type') else None

                search_criteria = SearchCriteria(
                    keywords=keywords,
                    locations=locations,
                    distance_in_km=distance_in_km,
                    date_posted=date_posted,
                    exp_level=exp_level,
                    job_type=job_type,
                    is_template=False  # This is a run, not a template
                )
                db.session.add(search_criteria)
                db.session.commit()

            # Use search_criteria fields for the scraper
            scraper = LinkedInScraper(
                keywords=search_criteria.keywords,
                locations=[loc.strip() for loc in search_criteria.locations.split(',')],
                distance_in_km=search_criteria.distance_in_km,
                date_posted=search_criteria.date_posted,
                exp_level=search_criteria.exp_level.split(', ') if search_criteria.exp_level else None,
                job_type=search_criteria.job_type.split(', ') if search_criteria.job_type else None,
                pages=int(data.get('pages', 1)),
                stop_callback=lambda: not scraping_active  # Pass stop check callback
            )
            jobs_data = scraper.scrape_jobs()

            # Check if scraping was stopped
            if not scraping_active:
                socketio.emit('scrape_stopped', {'data': 'Scraping was stopped by user'})
                return

            for job_data in jobs_data.to_dict('records'):
                if job_data.get('application_link') == 'Not Available':
                    continue # Skip jobs with no valid application link

                exists = db.session.query(Job.application_link).filter_by(application_link=job_data['application_link']).first() is not None
                if not exists:
                    job = Job(**job_data, search_criteria_id=search_criteria.id)
                    db.session.add(job)
            db.session.commit()

            socketio.emit('scrape_finished', {'data': f'Scraping complete. {len(jobs_data)} unique jobs found.'})

    except Exception as e:
        logging.error(f"An error occurred during scraping: {e}")
        socketio.emit('scrape_error', {'data': str(e)})
    finally:
        scraping_active = False

@socketio.on('start_scrape')
def handle_start_scrape(json):
    data = json.get('data')
    # Run scraping in background thread to avoid blocking SocketIO
    socketio.start_background_task(run_scraping_task, data)

# --- APScheduler Setup ---
scheduler = BackgroundScheduler()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

def run_scheduled_scrape(criteria_id):
    """Function called by APScheduler to run a scheduled scrape."""
    with app.app_context():
        try:
            criteria = SearchCriteria.query.get(criteria_id)
            if not criteria or not criteria.schedule_enabled:
                logging.warning(f"Skipping scheduled scrape for criteria {criteria_id}: not found or disabled")
                return

            logging.info(f"Running scheduled scrape for: {criteria.keywords}")

            # Update last_run timestamp
            criteria.last_run = datetime.utcnow()
            db.session.commit()

            # Create the scraper data object
            data = {
                'id': criteria_id,
                'pages': 1  # Default to 1 page for scheduled scrapes
            }

            # Run the scraping task directly (not via SocketIO since this is background)
            run_scraping_task(data)

        except Exception as e:
            logging.error(f"Error in scheduled scrape for criteria {criteria_id}: {e}")

def sync_scheduler_jobs():
    """Synchronize APScheduler jobs with enabled SearchCriteria in database."""
    with app.app_context():
        # Remove all existing jobs
        scheduler.remove_all_jobs()

        # Add jobs for all enabled schedules
        enabled_criteria = SearchCriteria.query.filter_by(schedule_enabled=True, is_template=True).all()

        for criteria in enabled_criteria:
            if criteria.schedule_hour is None:
                continue  # Skip if no time is set

            job_id = f"scrape_{criteria.id}"

            # Determine frequency based on date_posted
            if criteria.date_posted == 'past 24 hours':
                # Daily schedule
                trigger = CronTrigger(
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0
                )
            elif criteria.date_posted == 'past week':
                # Weekly schedule
                trigger = CronTrigger(
                    day_of_week=criteria.schedule_day_of_week or 0,  # Default to Monday
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0
                )
            elif criteria.date_posted == 'past month':
                # Monthly schedule
                trigger = CronTrigger(
                    day=criteria.schedule_day_of_month or 1,  # Default to 1st of month
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0
                )
            else:
                # Default to weekly if date_posted not specified
                trigger = CronTrigger(
                    day_of_week=criteria.schedule_day_of_week or 0,
                    hour=criteria.schedule_hour,
                    minute=criteria.schedule_minute or 0
                )

            scheduler.add_job(
                func=run_scheduled_scrape,
                trigger=trigger,
                args=[criteria.id],
                id=job_id,
                name=f"Scrape: {criteria.keywords}",
                replace_existing=True
            )
            logging.info(f"Scheduled job added: {criteria.keywords} - {trigger}")

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Sync scheduled jobs on startup
        sync_scheduler_jobs()
        logging.info("Scheduler initialized and jobs synced")

    # Disable Flask's reloader when using debugpy to avoid port conflicts
    use_reloader = os.environ.get('ENABLE_DEBUGPY', '0') != '1'
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=use_reloader)
