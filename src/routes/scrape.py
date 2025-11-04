from flask import Blueprint, jsonify, request, render_template
from models import db, SearchCriteria, Job
from scrapers import LinkedInScraper

scrape_bp = Blueprint('scrape', __name__)

# ============================================================================
# PAGE ROUTE
# ============================================================================

@scrape_bp.route('/scrape')
def scrape():
    return render_template(
        'scrape.html',
        distance_map=LinkedInScraper.DISTANCE_MAP,
        date_map=LinkedInScraper.DATE_MAP,
        exp_level_map=LinkedInScraper.EXP_LEVEL_MAP,
        job_type_map=LinkedInScraper.JOB_TYPE_MAP,
        active_page='scrape'
    )

# ============================================================================
# SEARCH CRITERIA API ENDPOINTS
# ============================================================================

@scrape_bp.route('/search_criteria', methods=['POST'])
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
            pages=data.get('pages', 1),
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
            from scheduler import sync_scheduler_jobs
            sync_scheduler_jobs()

        return jsonify({'status': 'success', 'id': new_criteria.id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@scrape_bp.route('/search_criteria/<int:criteria_id>', methods=['GET'])
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
            'pages': criteria.pages,
            'schedule_enabled': criteria.schedule_enabled,
            'schedule_hour': criteria.schedule_hour,
            'schedule_minute': criteria.schedule_minute,
            'schedule_day_of_week': criteria.schedule_day_of_week,
            'schedule_day_of_month': criteria.schedule_day_of_month,
            'last_run': criteria.last_run.isoformat() if criteria.last_run else None
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@scrape_bp.route('/search_criteria/<int:criteria_id>', methods=['PUT'])
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
        criteria.pages = data.get('pages', criteria.pages)

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
        from scheduler import sync_scheduler_jobs
        sync_scheduler_jobs()

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@scrape_bp.route('/search_criteria/<int:criteria_id>', methods=['DELETE'])
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
        from scheduler import sync_scheduler_jobs
        sync_scheduler_jobs()

        return jsonify({'status': 'success', 'archived_jobs': len(jobs)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@scrape_bp.route('/search_criterias')
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
            'pages': c.pages,
            'schedule_enabled': c.schedule_enabled,
            'schedule_hour': c.schedule_hour,
            'schedule_minute': c.schedule_minute,
            'schedule_day_of_week': c.schedule_day_of_week,
            'schedule_day_of_month': c.schedule_day_of_month,
            'last_run': c.last_run.isoformat() if c.last_run else None
        } for c in criterias])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
