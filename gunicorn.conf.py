import multiprocessing
import os

# Get the HOME directory from environment
home_dir = os.environ.get('HOME', '/tmp')
log_dir = os.path.join(home_dir, 'LogFiles')
os.makedirs(log_dir, exist_ok=True)

# Basic Configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'  # Changed from sync to gevent for better streaming support
threads = 4
timeout = 300  # Increased timeout

# Logging Configuration
accesslog = os.path.join(log_dir, "gunicorn_access.log")
errorlog = os.path.join(log_dir, "gunicorn_error.log")
loglevel = 'debug'  # Changed to debug for more detailed logging
capture_output = True
enable_stdio_inheritance = True

# Keepalive Settings
keepalive = 120
worker_connections = 1000

# Application Settings
wsgi_app = 'application:app'
proc_name = 'church-app'

# Worker Process Settings
worker_tmp_dir = '/tmp'
max_requests = 1000
max_requests_jitter = 50

# Debugging and Development
reload = False
daemon = False

# Add these settings for better streaming support
forwarded_allow_ips = '*'
proxy_allow_ips = '*'
