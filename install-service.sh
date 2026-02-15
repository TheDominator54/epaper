#!/bin/sh
# Install systemd service to run display_photo.py at boot.
# Run from repo root: sudo ./install-service.sh
# Edit epaper.service and change User= if your username is not dominic.

set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SVC_FILE="$REPO_DIR/epaper.service"
DEST="/etc/systemd/system/epaper.service"

if [ ! -f "$REPO_DIR/display_photo.py" ]; then
  echo "Run this script from the epaper repo root."
  exit 1
fi

sed "s|REPO_DIR|$REPO_DIR|g" "$SVC_FILE" > "$DEST"
echo "Installed $DEST"
systemctl daemon-reload
systemctl enable epaper.service
echo "Enabled epaper.service at boot. Start now with: sudo systemctl start epaper"
