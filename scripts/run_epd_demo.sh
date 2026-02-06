#!/usr/bin/env bash
# Run the manufacturer-style EPD demo (Init, Clear, draw, display, Sleep).
# Use from repo root so lib path exists. Sets PYTHONPATH and runs test_epd_demo.py.

set -e
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
LIB="${REPO_ROOT}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"

if [ ! -d "$LIB" ]; then
  echo "Missing lib: $LIB. Run install.sh first." >&2
  exit 1
fi

export PYTHONPATH="$LIB"
exec python3 scripts/test_epd_demo.py
