#!/usr/bin/env bash
# One-time install for e-paper image server on Raspberry Pi (e.g. Pi Zero 2 W).
# Follows: https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi
# Run from repo root. Reboot after install so SPI, config.txt, and groups apply.
set -e
cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"
WAVESHARE_LIB="${REPO_ROOT}/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
WAVESHARE_EPD="${WAVESHARE_LIB}/waveshare_epd"

echo "[1/8] Updating system and installing packages..."
sudo apt-get update
# Use apt for Python deps to avoid PEP 668 externally-managed-environment (no venv)
sudo apt-get install -y python3 python3-pil python3-numpy python3-spidev python3-flask python3-rpi.gpio git unzip wget

echo "[2/8] Enabling SPI..."
sudo raspi-config nonint do_spi 0
echo "SPI enabled."

echo "[3/8] config.txt: adding gpio=7=op,dl and gpio=8=op,dl for 13.3\" HAT+ (E)..."
for CONFIG in /boot/firmware/config.txt /boot/config.txt; do
  if [ -f "$CONFIG" ]; then
    if grep -q "gpio=7=op,dl" "$CONFIG" 2>/dev/null; then
      echo "  $CONFIG already has gpio lines, skipping."
    else
      echo "" | sudo tee -a "$CONFIG" >/dev/null
      echo "# 13.3inch e-Paper HAT+ (E) - Waveshare wiki" | sudo tee -a "$CONFIG" >/dev/null
      echo "gpio=7=op,dl" | sudo tee -a "$CONFIG" >/dev/null
      echo "gpio=8=op,dl" | sudo tee -a "$CONFIG" >/dev/null
      echo "  Appended to $CONFIG"
    fi
    break
  fi
done

echo "[4/8] Cloning Waveshare e-Paper library (for epdconfig and waveshare_epd)..."
if [ ! -d "lib/e-Paper" ]; then
  git clone --depth 1 https://github.com/waveshareteam/e-Paper.git lib/e-Paper
else
  echo "  lib/e-Paper already exists, skipping clone."
fi
mkdir -p "$WAVESHARE_EPD"

echo "[5/8] Downloading 13.3\" E (E6) demo and installing driver..."
E_DEMO_ZIP="${REPO_ROOT}/lib/13.3inch_e-Paper_E.zip"
E_DEMO_DIR="${REPO_ROOT}/lib/13.3inch_e-Paper_E"
if [ ! -f "$WAVESHARE_EPD/epd13in3e.py" ]; then
  if [ ! -d "${E_DEMO_DIR}" ]; then
    if [ ! -f "$E_DEMO_ZIP" ]; then
      echo "  Downloading 13.3inch e-Paper E demo from Waveshare..."
      wget -q -O "$E_DEMO_ZIP" "https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch%5Fe-Paper%5FE.zip" || true
    fi
    if [ -f "$E_DEMO_ZIP" ]; then
      unzip -o -q "$E_DEMO_ZIP" -d "${REPO_ROOT}/lib"
    else
      echo "  wget failed, trying GitHub E-paper_Separate_Program..."
      if [ ! -d "${REPO_ROOT}/lib/e-Paper-E-repo" ]; then
        git clone --depth 1 https://github.com/waveshare/e-Paper.git "${REPO_ROOT}/lib/e-Paper-E-repo"
      fi
      E_DEMO_DIR="${REPO_ROOT}/lib/e-Paper-E-repo/E-paper_Separate_Program/13.3inch_e-Paper_E"
    fi
  fi
  # Copy 13.3" E driver and its epdconfig into waveshare_epd (repo has epd13in3E.py with capital E; we need epd13in3e.py)
  E_LIB="${REPO_ROOT}/lib/e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib"
  for candidate in \
    "${E_LIB}/epd13in3E.py" \
    "${E_LIB}/epd13in3e.py" \
    "${E_DEMO_DIR}/RaspberryPi/python/lib/epd13in3E.py" \
    "${E_DEMO_DIR}/RaspberryPi/python/lib/epd13in3e.py"; do
    if [ -f "$candidate" ]; then
      cp "$candidate" "$WAVESHARE_EPD/epd13in3e.py"
      echo "  Installed epd13in3e.py from $(dirname "$candidate")"
      # Driver does "import epdconfig" (top-level); Python finds it in PYTHONPATH dir (lib), not inside waveshare_epd
      E_EPDCONFIG="$(dirname "$candidate")/epdconfig.py"
      if [ -f "$E_EPDCONFIG" ]; then
        cp "$E_EPDCONFIG" "$WAVESHARE_LIB/"
        echo "  Installed epdconfig.py (13.3\" E) into lib/"
      fi
      break
    fi
  done
  if [ ! -f "$WAVESHARE_EPD/epd13in3e.py" ]; then
    FOUND="$(find "${REPO_ROOT}/lib" \( -name "epd13in3E.py" -o -name "epd13in3e.py" \) 2>/dev/null | head -1)"
    if [ -n "$FOUND" ]; then
      cp "$FOUND" "$WAVESHARE_EPD/epd13in3e.py"
      E_EPDCONFIG="$(dirname "$FOUND")/epdconfig.py"
      if [ -f "$E_EPDCONFIG" ]; then
        cp "$E_EPDCONFIG" "$WAVESHARE_LIB/"
        echo "  Installed epd13in3e.py and epdconfig.py from $FOUND"
      else
        echo "  Installed epd13in3e.py from $FOUND"
      fi
    else
      echo "  WARNING: 13.3\" E driver not found. Check lib/e-Paper contains E-paper_Separate_Program/13.3inch_e-Paper_E/.../epd13in3E.py"
    fi
  fi
else
  echo "  epd13in3e.py already present, skipping."
fi

echo "[6/8] Python dependencies (installed via apt in step 1, no pip needed)..."
echo "  Skipping pip to avoid externally-managed-environment."

echo "[7/8] Adding user to spi and gpio groups..."
USER="$(whoami)"
sudo usermod -aG spi "$USER"
sudo usermod -aG gpio "$USER"
echo "  User $USER added to spi and gpio."

echo "[8/8] Creating uploads directory..."
mkdir -p uploads

echo ""
echo "Done. Next steps:"
echo "  1. Reboot so SPI, config.txt, and group membership apply: sudo reboot"
echo "  2. After reboot, run: sudo ./enable-boot.sh   (to run the server at boot)"
echo "  3. Open http://<this-pi-ip>:8080 and upload an image."
echo "  4. Optional: ./troubleshoot.sh to verify setup."
echo ""
