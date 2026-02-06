#!/usr/bin/env bash
# Checks packages, SPI, Waveshare lib, and (if present) systemd service for the e-paper server.
# Run from repo root.
set -e
cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"
ERR=0

check() {
  if "$@"; then
    echo "  OK: $*"
  else
    echo "  FAIL: $*"
    ERR=1
  fi
}

echo "=== E-paper server troubleshoot ==="
echo ""

echo "--- Python and pip ---"
check command -v python3
check command -v pip3
check python3 -c "import PIL"
check python3 -c "import spidev"
check python3 -c "import RPi.GPIO"
echo ""

echo "--- Waveshare library ---"
check [ -d "${REPO_ROOT}/lib/e-Paper" ]
check [ -d "${REPO_ROOT}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib" ]
check [ -d "${REPO_ROOT}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd" ]
echo ""

echo "--- SPI ---"
check [ -e /dev/spidev0.0 ]
if [ -e /dev/spidev0.0 ]; then
  check [ -r /dev/spidev0.0 ]
fi
echo ""

echo "--- User groups ---"
if groups | tr ' ' '\n' | grep -q spi; then
  echo "  OK: user in group spi"
else
  echo "  FAIL: user not in group spi (run: sudo usermod -aG spi $(whoami))"
  ERR=1
fi
if groups | tr ' ' '\n' | grep -q gpio; then
  echo "  OK: user in group gpio"
else
  echo "  FAIL: user not in group gpio (run: sudo usermod -aG gpio $(whoami))"
  ERR=1
fi
echo ""

echo "--- Systemd service (optional) ---"
if [ -f /etc/systemd/system/epaper.service ]; then
  echo "  epaper.service is installed."
  check systemctl is-enabled epaper 2>/dev/null || true
  check systemctl is-active epaper 2>/dev/null || true
else
  echo "  epaper.service not installed (optional)."
fi
echo ""

echo "--- PYTHONPATH and import ---"
export PYTHONPATH="${REPO_ROOT}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
if PYTHONPATH="${REPO_ROOT}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib" python3 -c "import waveshare_epd" 2>/dev/null; then
  echo "  OK: waveshare_epd import"
else
  echo "  FAIL: waveshare_epd import (check PYTHONPATH and lib/e-Paper)"
  ERR=1
fi
echo ""

if [ $ERR -eq 0 ]; then
  echo "All checks passed."
else
  echo "Some checks failed. Fix the issues above and run again."
  exit 1
fi
