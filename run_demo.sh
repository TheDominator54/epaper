#!/usr/bin/env bash
# Run the 13.3" E-Paper (E) Python demo (Pi 5 adapted).
# Uses .venv if present (recommended); otherwise system python3.
# Run from repo root: ./run_demo.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_LIB="${SCRIPT_DIR}/13.3inch_e-Paper_E/RaspberryPi/python/lib"
EXAMPLES_DIR="${SCRIPT_DIR}/13.3inch_e-Paper_E/RaspberryPi/python/examples"
if [ ! -f "${EXAMPLES_DIR}/epd_13in3E_test.py" ] || [ ! -f "${DEMO_LIB}/epd13in3E.py" ]; then
  echo "Demo not found. Run from repo root (directory containing run_demo.sh)." >&2
  exit 1
fi

if [ -d "${SCRIPT_DIR}/.venv" ] && [ -x "${SCRIPT_DIR}/.venv/bin/python" ]; then
  PYTHON="${SCRIPT_DIR}/.venv/bin/python"
else
  PYTHON=python3
fi

export PYTHONPATH="${DEMO_LIB}:${PYTHONPATH}"
cd "${EXAMPLES_DIR}"
exec "$PYTHON" epd_13in3E_test.py
