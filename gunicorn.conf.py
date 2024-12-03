import multiprocessing
import os

# Get the HOME directory from environment
home_dir = os.environ.get('HOME', '/tmp')
log_dir = os.path.join(home_dir, 'LogFiles')
os.makedirs(log_dir, exist_ok=True)

# Basic Configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
threads = 2

# Logging Configuration
accesslog = os.path.join(log_dir, "gunicorn_access.log")
errorlog = os.path.join(log_dir, "gunicorn_error.log")
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True

# Timeout Settings
timeout = 120
keepalive = 60

# Application Settings
wsgi_app = 'application:app'

# Process Naming
proc_name = 'church-app'

# Worker Process Settings
worker_tmp_dir = '/tmp'
max_requests = 1000
max_requests_jitter = 50

# Debugging and Development
reload = False
daemon = False
