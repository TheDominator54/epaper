#!/usr/bin/env bash
# Run the e-paper app. Use after setup.sh.
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"
export PYTHONPATH="${SCRIPT_DIR}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
python3 app/main.py
