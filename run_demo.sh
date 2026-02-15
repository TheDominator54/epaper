#!/usr/bin/env bash
# Run the 13.3" E-Paper (E) Python demo (Pi 5 adapted). Use from repo root.
# Optional: EPD_SPI_DEVICE=1 ./run_demo.sh if the display stays blank.
set -e
cd "$(dirname "$0")/13.3inch_e-Paper_E/RaspberryPi/python/examples"
exec python3 epd_13in3E_test.py
