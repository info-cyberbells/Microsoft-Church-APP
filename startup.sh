#!/bin/bash

apt-get update
apt-get install -y python3-pyaudio portaudio19-dev python3-dev build-essential

# Install gevent if not already installed
pip install gevent

# Create necessary directories
mkdir -p "$HOME/LogFiles"
chmod 755 "$HOME/LogFiles"

# Start Gunicorn with gevent worker
exec gunicorn  --bind="0.0.0.0:8000"  --workers=2 --worker_class="gthread" --threads=2 --accesslog="/home/LogFiles/gunicorn_access.log" --errorlog="/home/LogFiles/gunicorn_error.log" --loglevel="info" --capture_output=True --enable_stdio_inheritance=True --timeout=120 --keepalive=60 --wsgi_app="application:app" --proc_name="church-app" --worker_tmp_dir="/tmp" --max_requests=1000 --max_requests_jitter=50 --reload=False --daemon=False application:app
