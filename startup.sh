#!/bin/bash
cd /home/site/wwwroot
python -m gunicorn --bind=0.0.0.0:8000 --workers=4 --timeout=120 --access-logfile='-' --error-logfile='-' --log-level='info' --keep-alive=60 application:app
