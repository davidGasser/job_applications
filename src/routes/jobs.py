from flask import Blueprint, jsonify, request, render_template
from models import db, Job, SearchCriteria, Contact
from datetime import datetime
import random

jobs_bp = Blueprint('jobs', __name__)

# ============================================================================
# PAGE ROUTE
# ============================================================================

@jobs_bp.route('/jobs')
def index():
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
            'non_shortlisted_count': 0,
            'is_processed': True,
            'created_at': datetime.utcnow(),
            'is_archived': True
        })

    # Sort by most recent
    scrapes.sort(key=lambda x: x['created_at'], reverse=True)

    return render_template('index.html', scrapes=scrapes, active_page='index')

# ============================================================================
# JOB API ENDPOINTS
# ============================================================================

@jobs_bp.route('/job', methods=['POST'])
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

@jobs_bp.route('/job/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        db.session.delete(job)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Job deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@jobs_bp.route('/job/<int:job_id>/status', methods=['POST'])
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

@jobs_bp.route('/job/<int:job_id>/shortlist', methods=['POST'])
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

@jobs_bp.route('/job/<int:job_id>/details', methods=['GET'])
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

@jobs_bp.route('/job/<int:job_id>/details', methods=['POST'])
def update_job_details(job_id):
    try:
        job = Job.query.get_or_404(job_id)
        data = request.json
        if 'notes' in data:
            job.notes = data['notes']
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Details updated'})
    except Exception as e:
        print(f"Error updating job details: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@jobs_bp.route('/scrape/<scrape_id>/jobs')
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
            'score_details': job.score_details,
            'scraped_at': job.scraped_at.isoformat(),
            'updated_at': job.updated_at.isoformat(),
            'search_criteria_id': job.search_criteria_id,
            'search_criteria': {
                'keywords': job.search_criteria.keywords,
                'locations': job.search_criteria.locations
            } if job.search_criteria else {'keywords': 'Archived', 'locations': 'Various'}
        } for job in jobs])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@jobs_bp.route('/scrape/<int:scrape_id>/confirm', methods=['POST'])
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

# ============================================================================
# CONTACT API ENDPOINTS (related to jobs)
# ============================================================================

@jobs_bp.route('/contact/<int:contact_id>', methods=['PUT'])
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

@jobs_bp.route('/contact/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    try:
        contact = Contact.query.get_or_404(contact_id)
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@jobs_bp.route('/job/<int:job_id>/contact', methods=['POST'])
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
