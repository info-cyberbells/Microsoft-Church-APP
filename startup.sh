#!/bin/bash

# Install gevent if not already installed
pip install gevent

# Create necessary directories
mkdir -p "$HOME/LogFiles"
chmod 755 "$HOME/LogFiles"

mkdir -p /home/site/libs
cd /home/site/libs

# Updated package URLs for Ubuntu 20.04
wget http://archive.ubuntu.com/ubuntu/pool/main/a/alsa-lib/libasound2_1.2.4-1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/p/portaudio19-dev/libportaudio2_19.6.0-1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/p/pulseaudio/libpulse0_13.99.1-1ubuntu3.13_amd64.deb

dpkg -x libasound2_1.2.4-1_amd64.deb /home/site/libs
dpkg -x libportaudio2_19.6.0-1_amd64.deb /home/site/libs  
dpkg -x libpulse0_13.99.1-1ubuntu3.13_amd64.deb /home/site/libs

export LD_LIBRARY_PATH=/home/site/libs/usr/lib/x86_64-linux-gnu

python application.py

# Start Gunicorn with gevent worker
exec gunicorn --config=gunicorn.conf.py application:app
