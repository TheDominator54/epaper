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
# BMP must be 1200×1600 or 1600×1200 for getbuffer()
BMP="${DEMO}/pic/13in3E.bmp"
if [ -f "$BMP" ]; then
  BMP_SIZE=$(python3 -c "
import sys
try:
    with open(sys.argv[1], 'rb') as f:
        f.seek(18)
        w = int.from_bytes(f.read(4), 'little')
        h = int.from_bytes(f.read(4), 'little')
    ok = (w == 1200 and h == 1600) or (w == 1600 and h == 1200)
    print(f'{w}x{h}' if ok else 'BAD')
except Exception:
    print('BAD')
" "$BMP" 2>/dev/null)
  if [ "$BMP_SIZE" = "BAD" ]; then
    MISSING="${MISSING}\n  - ${BMP}: must be 1200×1600 or 1600×1200 (check file or re-download)"
  else
    echo "[OK] 13in3E.bmp size ${BMP_SIZE}"
  fi
fi

# SPI
if [ ! -c /dev/spidev0.0 ] || [ ! -c /dev/spidev0.1 ]; then
  MISSING="${MISSING}\n  - SPI not enabled (no /dev/spidev0.0 or /dev/spidev0.1). Run: sudo raspi-config → Interface Options → SPI → Yes, then reboot"
else
  echo "[OK] SPI (/dev/spidev0.0, /dev/spidev0.1)"
  if ! python3 -c "import spidev; s=spidev.SpiDev(); s.open(0,0); s.close()" 2>/dev/null; then
    echo "  (Warning: cannot open SPI as this user — run with sudo: sudo ./run_demo.sh — or: sudo usermod -aG spi \$USER then re-login)"
  fi
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

# Driver import (verifies epdconfig + RPi.GPIO + spidev + PIL chain)
DEMO_LIB="${DEMO}/lib"
if ! python3 -c "import sys; sys.path.insert(0, '${DEMO_LIB}'); import epd13in3E" 2>/dev/null; then
  MISSING="${MISSING}\n  - Driver import failed (check above deps and that you're in repo root)"
else
  echo "[OK] epd13in3E driver imports"
fi

if [ -n "$MISSING" ]; then
  echo -e "\nMissing or failed:$MISSING"
  exit 1
fi

echo ""
echo "Ready. Run: ./run_demo.sh"
