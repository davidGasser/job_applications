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
    status = db.Column(db.String(50), nullable=False, default='New') # New, Interested, Applied, Archived
    notes = db.Column(db.Text, nullable=True)
    contact_info = db.Column(db.Text, nullable=True)
    positives = db.Column(db.Text, nullable=True)
    negatives = db.Column(db.Text, nullable=True)
    search_criteria_id = db.Column(db.Integer, db.ForeignKey('search_criteria.id'), nullable=False)
    search_criteria = db.relationship('SearchCriteria', backref=db.backref('jobs', lazy=True))

    def __repr__(self):
        return f'<Job {self.title} @ {self.company}>'

# --- HTTP Routes ---
@app.route('/')
def index():
    jobs = Job.query.order_by(Job.id.desc()).all()
    return render_template('index.html', jobs=jobs, active_page='index')

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

@app.route('/kanban')
def kanban():
    statuses = ['New', 'Interested', 'Applied', 'Archived']
    jobs = Job.query.order_by(Job.id.desc()).all()
    return render_template('kanban.html', jobs=jobs, statuses=statuses, active_page='kanban')

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

@app.route('/job/<int:job_id>/details', methods=['POST'])
def update_job_details(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        data = request.json
        job.notes = data.get('notes', job.notes)
        job.contact_info = data.get('contact_info', job.contact_info)
        job.positives = data.get('positives', job.positives)
        job.negatives = data.get('negatives', job.negatives)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Details updated'})
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
