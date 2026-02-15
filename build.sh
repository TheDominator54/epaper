#!/usr/bin/env bash
# Build the 13.3" e-Paper C demo for Raspberry Pi 5 (wiringPi).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CDIR="$SCRIPT_DIR/demo"
if [[ ! -d "$CDIR" ]]; then
  echo "Demo source not found: $CDIR"
  exit 1
fi
cd "$CDIR"
sudo make clean
sudo make -j4 USELIB=USE_WIRINGPI_LIB
echo "Build OK. Binary: $CDIR/epd"
