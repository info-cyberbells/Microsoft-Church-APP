#!/bin/bash

# Install gevent if not already installed
pip install gevent

# Create necessary directories
mkdir -p "$HOME/LogFiles"
chmod 755 "$HOME/LogFiles"

mkdir /home/site/libs
cd /home/site/libs
wget http://security.ubuntu.com/ubuntu/pool/main/a/alsa-lib/libasound2_1.2.4-1ubuntu3_amd64.deb
wget http://security.ubuntu.com/ubuntu/pool/main/p/portaudio19/libportaudio2_19.6.0-1.1_amd64.deb
wget http://security.ubuntu.com/ubuntu/pool/main/p/pulseaudio/libpulse0_15.99.1+dfsg1-1ubuntu1_amd64.deb
dpkg -x libasound2_1.2.4-1ubuntu3_amd64.deb /home/site/libs
dpkg -x libportaudio2_19.6.0-1.1_amd64.deb /home/site/libs
dpkg -x libpulse0_15.99.1+dfsg1-1ubuntu1_amd64.deb /home/site/libs
export LD_LIBRARY_PATH=/home/site/libs/usr/lib/x86_64-linux-gnu

# Start Gunicorn with gevent worker
exec gunicorn --config=gunicorn.conf.py application:app
