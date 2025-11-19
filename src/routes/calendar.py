from flask import Blueprint, jsonify, request, render_template
from models import db, JobDate
from datetime import datetime

calendar_bp = Blueprint('calendar', __name__)

# ============================================================================
# PAGE ROUTE
# ============================================================================

@calendar_bp.route('/calendar')
def calendar():
    return render_template('calendar.html', active_page='calendar')

# ============================================================================
# JOB DATES API ENDPOINTS
# ============================================================================

@calendar_bp.route('/job_dates')
def get_job_dates():
    try:
        dates = JobDate.query.all()
        events = []
        for d in dates:
            # Include interview type/appointment title in calendar event
            event_type = d.title if d.title else d.category.title()
            events.append({
                'title': f"{event_type}\n{d.job.title} - {d.job.company}",
                'start': d.date.isoformat(),
                'extendedProps': {
                    'job_id': d.job_id,
                    'job_title': d.job.title,
                    'company': d.job.company,
                    'category': d.category,
                    'event_type': event_type,
                    'description': d.description
                }
            })
        return jsonify(events)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@calendar_bp.route('/job/<int:job_id>/date', methods=['POST'])
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

@calendar_bp.route('/job_date/<int:date_id>/details')
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

@calendar_bp.route('/job_date/<int:date_id>', methods=['PUT'])
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

@calendar_bp.route('/job_date/<int:date_id>', methods=['DELETE'])
def delete_job_date(date_id):
    try:
        job_date = JobDate.query.get_or_404(date_id)
        db.session.delete(job_date)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
