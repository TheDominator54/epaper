#!/usr/bin/env bash
# Run the 13.3" E-Paper (E) Python demo (Pi 5 adapted).
# Run from repo root (e.g. on Pi: cd ~/epaper && ./run_demo.sh)
# Optional: EPD_SPI_DEVICE=1 ./run_demo.sh if the display stays blank.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_LIB="${SCRIPT_DIR}/13.3inch_e-Paper_E/RaspberryPi/python/lib"
EXAMPLES_DIR="${SCRIPT_DIR}/13.3inch_e-Paper_E/RaspberryPi/python/examples"
if [ ! -f "${EXAMPLES_DIR}/epd_13in3E_test.py" ] || [ ! -f "${DEMO_LIB}/epd13in3E.py" ]; then
  echo "Demo not found. Run from repo root (directory containing run_demo.sh)." >&2
  exit 1
fi
export PYTHONPATH="${DEMO_LIB}:${PYTHONPATH}"
cd "${EXAMPLES_DIR}"
exec python3 epd_13in3E_test.py
