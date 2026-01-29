FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Waveshare-style libs commonly use spidev + RPi.GPIO
RUN pip install --no-cache-dir spidev RPi.GPIO pillow

# Pull Waveshare/soonuse python library (widely used for demos)
RUN git clone --depth=1 https://github.com/soonuse/epd-library-python.git /opt/epd-library-python
