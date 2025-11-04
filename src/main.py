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

from flask import Flask, redirect, url_for
from flask_socketio import SocketIO
from markupsafe import Markup

# Import database and models
from models import db

# Import blueprints
from routes.jobs import jobs_bp
from routes.scrape import scrape_bp
from routes.calendar import calendar_bp
from routes.kanban import kanban_bp
from routes.prompt import prompt_bp

# Import scheduler and socketio event handlers
from scheduler import sync_scheduler_jobs
from socketio_events import register_socketio_events

# --- App and DB Setup ---
app = Flask(__name__, template_folder='../templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with app
db.init_app(app)

# Initialize SocketIO
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

# --- Register Blueprints ---
app.register_blueprint(jobs_bp)
app.register_blueprint(scrape_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(kanban_bp)
app.register_blueprint(prompt_bp)

# --- Register SocketIO Events ---
# Get the run_scraping_task function for use with scheduler
run_scraping_task_func = register_socketio_events(socketio, app)

# --- Home Route ---
@app.route('/')
def home():
    # Redirect to prompt page as the home page
    return redirect(url_for('prompt.prompt'))

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Sync scheduled jobs on startup
        sync_scheduler_jobs(app, run_scraping_task_func)
        logging.info("Scheduler initialized and jobs synced")

    # Disable Flask's reloader when using debugpy to avoid port conflicts
    use_reloader = os.environ.get('ENABLE_DEBUGPY', '0') != '1'
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=use_reloader)
