# syntax=docker/dockerfile:1
# Use full bookworm so apt has python3-dev (slim can miss it on some arches)
FROM python:3.11-bookworm

# Single-job compile = less RAM, more reliable on Pi Zero 2 W
ENV MAKEFLAGS="-j1"
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Build one package at a time to avoid OOM on low-RAM devices
RUN pip install --no-cache-dir spidev
RUN pip install --no-cache-dir RPi.GPIO
RUN pip install --no-cache-dir pillow

RUN git clone --depth=1 https://github.com/soonuse/epd-library-python.git /opt/epd-library-python
