#!/bin/sh
# Install systemd service to run display_photo.py at boot.
# Run from repo root: sudo ./install-service.sh

set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SVC_FILE="$REPO_DIR/epaper.service"
DEST="/etc/systemd/system/epaper.service"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo sh install-service.sh"
  exit 1
fi

if [ ! -f "$REPO_DIR/display_photo.py" ]; then
  echo "Run this script from the epaper repo root."
  exit 1
fi

if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
  SERVICE_USER="$SUDO_USER"
else
  SERVICE_USER="$(id -un)"
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "Could not determine a valid service user."
  exit 1
fi

escape_sed_replacement() {
  printf '%s' "$1" | sed 's/[|&]/\\&/g'
}

REPO_DIR_ESCAPED="$(escape_sed_replacement "$REPO_DIR")"
SERVICE_USER_ESCAPED="$(escape_sed_replacement "$SERVICE_USER")"

sed -e "s|REPO_DIR|$REPO_DIR_ESCAPED|g" \
    -e "s|SERVICE_USER|$SERVICE_USER_ESCAPED|g" \
    "$SVC_FILE" > "$DEST"
echo "Installed $DEST"
echo "Configured service user: $SERVICE_USER"
systemctl daemon-reload
systemctl enable epaper.service
echo "Enabled epaper.service at boot. Start now with: sudo systemctl start epaper"
