#!/bin/bash

# Install gevent if not already installed
pip install gevent

# Create necessary directories
mkdir -p "$HOME/LogFiles"
chmod 755 "$HOME/LogFiles"

# Start Gunicorn with gevent worker
exec gunicorn --config=gunicorn.conf.py application:app
