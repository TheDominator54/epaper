#!/usr/bin/env bash
# Verify everything is ready for the 13.3" E-Paper demo. Run from repo root.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO="${SCRIPT_DIR}/13.3inch_e-Paper_E/RaspberryPi/python"
MISSING=""

# Demo files
for f in "${DEMO}/examples/epd_13in3E_test.py" "${DEMO}/lib/epd13in3E.py" "${DEMO}/lib/epdconfig.py" "${DEMO}/pic/Font.ttc" "${DEMO}/pic/13in3E.bmp"; do
  if [ -e "$f" ]; then
    echo "[OK] $f"
  else
    MISSING="${MISSING}\n  - $f"
  fi
done

# SPI
if [ ! -c /dev/spidev0.0 ] || [ ! -c /dev/spidev0.1 ]; then
  MISSING="${MISSING}\n  - SPI not enabled (no /dev/spidev0.0 or /dev/spidev0.1). Run: sudo raspi-config → Interface Options → SPI → Yes, then reboot"
else
  echo "[OK] SPI (/dev/spidev0.0, /dev/spidev0.1)"
fi

# Python deps
if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
  MISSING="${MISSING}\n  - Python: RPi.GPIO (on Pi 5 install: sudo apt install python3-rpi-lgpio && sudo apt remove python3-rpi.gpio)"
else
  echo "[OK] Python RPi.GPIO"
fi
if ! python3 -c "import spidev" 2>/dev/null; then
  MISSING="${MISSING}\n  - Python: spidev (sudo apt install python3-spidev)"
else
  echo "[OK] Python spidev"
fi
if ! python3 -c "import PIL" 2>/dev/null; then
  MISSING="${MISSING}\n  - Python: PIL (sudo apt install python3-pil)"
else
  echo "[OK] Python PIL"
fi

if [ -n "$MISSING" ]; then
  echo -e "\nMissing or failed:$MISSING"
  exit 1
fi

echo ""
echo "Ready. Run: ./run_demo.sh"
