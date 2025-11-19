from flask import Blueprint, render_template, request, jsonify
from models import db, Job
from scrapers import LinkedInScraper

kanban_bp = Blueprint('kanban', __name__)

# ============================================================================
# PAGE ROUTE
# ============================================================================

@kanban_bp.route('/kanban')
def kanban():
    statuses = ['Interested', 'Applied', 'Interviewing', 'Offer', 'Rejected']
    jobs = Job.query.filter_by(shortlisted=True).order_by(Job.id.desc()).all()

    # Get all unique interview steps from jobs that are interviewing
    interviewing_jobs = [j for j in jobs if j.status == 'Interviewing']
    interview_steps = sorted(set(j.interview_step for j in interviewing_jobs if j.interview_step is not None))

    # If there are interviewing jobs without a step, default them to step 1
    needs_commit = False
    for job in interviewing_jobs:
        if job.interview_step is None:
            job.interview_step = 1
            if not job.interview_stage_name:
                job.interview_stage_name = "Interview"
            needs_commit = True

    # Commit defaults if any were set
    if needs_commit:
        db.session.commit()

    # Refresh interview steps after defaults
    if interviewing_jobs:
        interview_steps = sorted(set(j.interview_step for j in interviewing_jobs if j.interview_step is not None))
    else:
        interview_steps = []

    return render_template('kanban.html', jobs=jobs, statuses=statuses, interview_steps=interview_steps, active_page='kanban')

# ============================================================================
# API ENDPOINTS
# ============================================================================

@kanban_bp.route('/extract_job_info', methods=['POST'])
def extract_job_info():
    """Extract job information from a LinkedIn URL."""
    scraper = None
    try:
        data = request.json
        linkedin_url = data.get('url')

        if not linkedin_url:
            return jsonify({'status': 'error', 'message': 'No URL provided'}), 400

        if 'linkedin.com/jobs' not in linkedin_url:
            return jsonify({'status': 'error', 'message': 'Invalid LinkedIn job URL'}), 400

        # Create scraper instance
        scraper = LinkedInScraper(keywords="", locations="")

        # Initialize the driver (same as in scrape_jobs method)
        from selenium import webdriver
        opts = webdriver.ChromeOptions()
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_experimental_option('excludeSwitches', ['enable-automation'])
        opts.add_experimental_option('useAutomationExtension', False)
        opts.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        opts.add_argument("--start-maximized")
        scraper.driver = webdriver.Remote(
            command_executor='http://selenium:4444/wd/hub',
            options=opts
        )

        # Load cookies for authentication
        scraper._load_cookies()

        # Navigate to the job URL and extract info
        scraper.driver.get(linkedin_url)
        job_data = scraper.extract_info()

        return jsonify({
            'status': 'success',
            'data': job_data
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        # Always close the driver, even if there was an error
        if scraper and scraper.driver:
            try:
                scraper.driver.quit()
            except:
                pass  # Ignore errors during cleanup
