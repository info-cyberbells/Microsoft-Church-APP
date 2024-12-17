# gunicorn.conf.py
import multiprocessing

# Basic Configuration
bind = "0.0.0.0:8010"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'  # Changed from 'gthread' for better Azure compatibility
threads = 4

# Logging Configuration
accesslog = "-"  # Log to stdout for Azure to capture
errorlog = "-"   # Log to stderr for Azure to capture
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True

# Timeout Settings
timeout = 120
keepalive = 60

# Application Settings
wsgi_app = 'app:app'  # Make sure this matches your main Flask app

# Worker Process Settings
max_requests = 1000
max_requests_jitter = 50

# Azure-specific settings
preload_app = True
forwarded_allow_ips = '*'
