#!/usr/bin/env bash
# Create a venv for the 13.3" E-Paper demo (Pi 5 / Bookworm friendly).
# Uses system-site-packages so apt-installed rpi-lgpio and PIL/numpy are available;
# installs spidev via pip (often more reliable on Bookworm than python3-spidev).
# Run from repo root: ./setup_venv.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "13.3inch_e-Paper_E/RaspberryPi/python/lib/epd13in3E.py" ]; then
  echo "Demo not found. Run from repo root." >&2
  exit 1
fi

# Ensure venv module and system deps exist (user may need to apt install first)
if ! python3 -c "import venv" 2>/dev/null; then
  echo "Install python3-venv first: sudo apt install -y python3-venv" >&2
  exit 1
fi
if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
  echo "Install rpi-lgpio first: sudo apt install -y python3-rpi-lgpio && sudo apt remove -y python3-rpi.gpio" >&2
  exit 1
fi
if ! python3 -c "import PIL" 2>/dev/null; then
  echo "Install PIL first: sudo apt install -y python3-pil python3-numpy" >&2
  exit 1
fi

VENV_DIR="${SCRIPT_DIR}/.venv"
if [ -d "$VENV_DIR" ]; then
  echo "Venv already exists at .venv — upgrading pip and (re)installing spidev."
else
  echo "Creating venv at .venv (--system-site-packages for RPi.GPIO, PIL, numpy)..."
  python3 -m venv --system-site-packages --prompt epaper "$VENV_DIR"
fi

set +e
source "${VENV_DIR}/bin/activate"
set -e
pip install --upgrade pip -q
if [ -f "${SCRIPT_DIR}/requirements-venv.txt" ]; then
  pip install -r "${SCRIPT_DIR}/requirements-venv.txt"
else
  pip install spidev
fi
echo "Venv ready. Run: ./run_demo.sh (or ./check_demo.sh then ./run_demo.sh)"
deactivate 2>/dev/null || true
