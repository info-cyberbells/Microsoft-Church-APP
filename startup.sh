#!/bin/bash

# Create necessary directories
mkdir -p "$HOME/LogFiles"
chmod 755 "$HOME/LogFiles"

# Start Gunicorn
exec gunicorn --config=gunicorn.conf.py application:app
