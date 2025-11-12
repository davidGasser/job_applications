import os
import logging

# Enable debugpy for remote debugging from VS Code
if os.environ.get('ENABLE_DEBUGPY', '0') == '1':
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))
    print("⏳ Debugger listening on port 5678...")
    # Uncomment to make app wait for debugger before continuing:
    # debugpy.wait_for_client()
    print("✅ Ready for debugger attachment")

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

# Initialize SocketIO with threading mode
# Threading mode is REQUIRED because our scraper uses real Python threads (ThreadPoolExecutor)
# which would block gevent/eventlet's event loop and prevent receiving events like 'stop_scrape'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

# --- Logging Setup for Real-time Updates ---
class SocketIOHandler(logging.Handler):
    def __init__(self, socketio_instance, prefix=""):
        super().__init__()
        self.socketio = socketio_instance
        self.prefix = prefix

    def emit(self, record):
        try:
            # Format with clear prefix for component identification
            log_entry = f"[{self.prefix}] {record.getMessage()}"
            # Emit to all connected clients (namespace='/' for default)
            self.socketio.emit('log_message', {'data': log_entry}, namespace='/')
        except Exception as e:
            # Fallback to stderr if socket emission fails
            import sys
            print(f"SocketIOHandler error: {e}", file=sys.stderr)
            print(f"Original message: [{self.prefix}] {record.getMessage()}", file=sys.stderr)

# Setup console handler for all loggers (so we see logs in Docker)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Setup separate loggers for different components
scraper_logger = logging.getLogger('scrapers')
scraper_logger.setLevel(logging.INFO)
scraper_console = logging.StreamHandler()
scraper_console.setFormatter(logging.Formatter('[SCRAPER] %(message)s'))
scraper_logger.addHandler(scraper_console)
scraper_socket = SocketIOHandler(socketio, prefix="SCRAPER")
scraper_logger.addHandler(scraper_socket)
scraper_logger.propagate = False

# # worker_logger = logging.getLogger('workers')
# # worker_logger.setLevel(logging.INFO)
# worker_console = logging.StreamHandler()
# worker_console.setFormatter(logging.Formatter('[WORKER] %(message)s'))
# # worker_logger.addHandler(worker_console)
# worker_socket = SocketIOHandler(socketio, prefix="WORKER")
# # worker_logger.addHandler(worker_socket)
# # worker_logger.propagate = False

queue_logger = logging.getLogger('queue')
queue_logger.setLevel(logging.INFO)
queue_console = logging.StreamHandler()
queue_console.setFormatter(logging.Formatter('[QUEUE] %(message)s'))
queue_logger.addHandler(queue_console)
queue_socket = SocketIOHandler(socketio, prefix="QUEUE")
queue_logger.addHandler(queue_socket)
queue_logger.propagate = False

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

    # Run with threading mode
    # allow_unsafe_werkzeug=True is required for threading mode in development
    # This is safe for local development; use proper WSGI server (gunicorn/uwsgi) in production
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        use_reloader=use_reloader,
        allow_unsafe_werkzeug=True
    )
