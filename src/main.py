import os
import logging
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup
from scrapers import LinkedInScraper
from flask_socketio import SocketIO

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
    search_criteria_id = db.Column(db.Integer, db.ForeignKey('search_criteria.id'))
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
            job_type=data.get('job_type')
        )
        db.session.add(new_criteria)
        db.session.commit()
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
            'job_type': criteria.job_type
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
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/search_criteria/<int:criteria_id>', methods=['DELETE'])
def delete_search_criteria(criteria_id):
    try:
        criteria = SearchCriteria.query.get_or_404(criteria_id)
        db.session.delete(criteria)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/search_criterias')
def get_search_criterias():
    try:
        criterias = SearchCriteria.query.all()
        return jsonify([{
            'id': c.id,
            'keywords': c.keywords,
            'locations': c.locations,
            'distance_in_km': c.distance_in_km,
            'date_posted': c.date_posted,
            'exp_level': c.exp_level,
            'job_type': c.job_type
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

    # Get unique search criteria with job counts
    search_criterias = SearchCriteria.query.all()
    scrapes = []
    for sc in search_criterias:
        job_count = Job.query.filter_by(search_criteria_id=sc.id).count()
        if job_count > 0:  # Only include scrapes that have jobs
            # Check if scrape is processed (all remaining jobs are shortlisted)
            non_shortlisted_count = Job.query.filter_by(search_criteria_id=sc.id, shortlisted=False).count()
            is_processed = non_shortlisted_count == 0

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
                'is_processed': is_processed,
                'created_at': sc.created_at
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
        new_job = Job(
            title=data['title'],
            company=data.get('company'),
            location=data.get('location'),
            status='New'
        )
        db.session.add(new_job)
        db.session.commit()
        return jsonify({
            'id': new_job.id,
            'title': new_job.title,
            'company': new_job.company
        })
    except Exception as e:
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
            'created_at': job.created_at.isoformat(),
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

@app.route('/scrape/<int:scrape_id>/jobs')
def get_scrape_jobs(scrape_id):
    try:
        jobs = Job.query.filter_by(search_criteria_id=scrape_id).order_by(Job.matching_score.desc()).all()
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
            } if job.search_criteria else None
        } for job in jobs])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/scrape/<int:scrape_id>/confirm', methods=['POST'])
def confirm_scrape(scrape_id):
    try:
        # Delete all non-shortlisted jobs from this scrape
        jobs_to_delete = Job.query.filter_by(search_criteria_id=scrape_id, shortlisted=False).all()
        for job in jobs_to_delete:
            db.session.delete(job)
        db.session.commit()

        # Check if any jobs remain for this scrape
        remaining_jobs = Job.query.filter_by(search_criteria_id=scrape_id).count()

        return jsonify({
            'status': 'success',
            'deleted_count': len(jobs_to_delete),
            'remaining_jobs': remaining_jobs
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
@socketio.on('start_scrape')
def handle_start_scrape(json):
    try:
        with app.app_context():
            data = json.get('data')
            # Find or create the SearchCriteria
            criteria_data = {
                'keywords': data.get('keywords'),
                'locations': data.get('locations'),
                'distance_in_km': int(data.get('distance')) if data.get('distance') else None,
                'date_posted': data.get('date_posted') if data.get('date_posted') else None,
                'exp_level': ', '.join(data.get('exp_level', [])) if data.get('exp_level') else None,
                'job_type': ', '.join(data.get('job_type', [])) if data.get('job_type') else None
            }
            search_criteria = SearchCriteria.query.filter_by(**criteria_data).first()
            if not search_criteria:
                search_criteria = SearchCriteria(**criteria_data)
                db.session.add(search_criteria)
                db.session.commit()

            scraper = LinkedInScraper(
                keywords=data.get('keywords'),
                locations=[loc.strip() for loc in data.get('locations', '').split(',')],
                distance_in_km=int(data.get('distance')) if data.get('distance') else None,
                date_posted=data.get('date_posted') if data.get('date_posted') else None,
                exp_level=data.get('exp_level') if data.get('exp_level') else None,
                job_type=data.get('job_type') if data.get('job_type') else None,
                pages=int(data.get('pages', 1))
            )
            jobs_data = scraper.scrape_jobs()

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

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000)
