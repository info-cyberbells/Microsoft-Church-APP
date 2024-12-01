import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 4
timeout = 600
keepalive = 75
worker_class = 'sync'
