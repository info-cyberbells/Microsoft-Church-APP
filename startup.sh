#!/bin/bash
cd /home/site/wwwroot
gunicorn --bind=0.0.0.0:8000 \
         --workers=4 \
         --timeout=120 \
         --access-logfile=- \
         --error-logfile=- \
         --log-level=info \
         application:app
