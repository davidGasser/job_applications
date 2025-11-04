from flask import Blueprint, render_template
from models import Job

kanban_bp = Blueprint('kanban', __name__)

# ============================================================================
# PAGE ROUTE
# ============================================================================

@kanban_bp.route('/kanban')
def kanban():
    statuses = ['Interested', 'Applied', 'Interviewing', 'Offer', 'Rejected']
    jobs = Job.query.filter_by(shortlisted=True).order_by(Job.id.desc()).all()
    return render_template('kanban.html', jobs=jobs, statuses=statuses, active_page='kanban')
