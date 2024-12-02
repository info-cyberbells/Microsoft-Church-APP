import os
import multiprocessing

# Basic Configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
threads = 4

# Logging Configuration
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Timeout Settings
timeout = 120
keepalive = 60

# Application Settings
wsgi_app = 'application:app'
chdir = '/home/site/wwwroot'

# Process Naming
proc_name = 'church-app'

# SSL Configuration (if needed)
keyfile = None
certfile = None

# Worker Process Settings
worker_tmp_dir = '/dev/shm'
max_requests = 1000
max_requests_jitter = 50

# Debugging and Reloading
reload = False
capture_output = True
enable_stdio_inheritance = True
