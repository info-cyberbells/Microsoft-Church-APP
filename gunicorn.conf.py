import multiprocessing
import os
import ssl

# Basic Configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2 * multiprocessing.cpu_count()
worker_class = "gevent"

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
capture_output = True
enable_stdio_inheritance = True

# Timeouts
timeout = 300
keepalive = 2
graceful_timeout = 30

# SSL Configuration
keyfile = None
certfile = None

# Server Mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Server Hooks
def on_starting(server):
    server.log.info("Server is starting up")

def on_reload(server):
    server.log.info("Server is reloading")

def on_exit(server):
    server.log.info("Server is shutting down")

def when_ready(server):
    server.log.info("Server is ready. Doing nothing.")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")

# Additional Settings
max_requests = 1000
max_requests_jitter = 50
reload = False
reload_engine = 'auto'

# Worker Configurations
worker_connections = 1000
worker_tmp_dir = None
sendfile = True

# Process Naming
proc_name = None

# SSL Options - Corrected
ssl_version = ssl.PROTOCOL_TLS
cert_reqs = ssl.CERT_NONE
ca_certs = None
suppress_ragged_eofs = True

# Development Settings
reload_extra_files = []
raw_env = []

# HTTP Settings
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Debugging
spew = False
check_config = False

# Server Mechanics
preload_app = True
sendfile = True
reuse_port = True

# Only enable this in development
reload = False

try:
    # Azure-specific configurations if running on Azure
    if os.environ.get('WEBSITE_SITE_NAME'):
        accesslog = os.path.join(os.environ.get('HOME', ''), 'LogFiles', 'gunicorn_access.log')
        errorlog = os.path.join(os.environ.get('HOME', ''), 'LogFiles', 'gunicorn_error.log')
        
        # Adjust workers for Azure App Service
        web_apps_max_workers = int(os.environ.get('WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT', '1'))
        workers = min(workers, web_apps_max_workers * 2)
        
        # Enable logging for Azure
        capture_output = True
        enable_stdio_inheritance = True
        
        # Azure timeout settings
        timeout = 600
        keepalive = 5
        graceful_timeout = 30
except Exception as e:
    print(f"Error configuring Azure-specific settings: {e}")
