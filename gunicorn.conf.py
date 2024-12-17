import multiprocessing
# Basic Configuration
bind = "0.0.0.0:8010"  # Azure expects port 8000
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gthread'
threads = 2
# Logging Configuration
accesslog = "/home/LogFiles/gunicorn_access.log"
errorlog = "/home/LogFiles/gunicorn_error.log"
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
