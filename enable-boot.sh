#!/usr/bin/env bash
# Install and enable the epaper systemd service so it runs at boot.
# Run from repo root: sudo ./enable-boot.sh
set -e
cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"
USER="$(logname 2>/dev/null || echo "${SUDO_USER:-$USER}")"
if [ -z "$USER" ] || [ "$USER" = root ]; then
  echo "Run as: sudo -u YOUR_USER ./enable-boot.sh  (or sudo ./enable-boot.sh after logging in as your user)"
  USER="$(whoami)"
  if [ "$USER" = root ]; then
    echo "Could not detect non-root user. Set USER in this script or run: sudo sed -i 's/YOUR_USER/pi/' /etc/systemd/system/epaper.service"
    exit 1
  fi
fi

echo "Installing epaper.service for user: $USER"
sudo cp epaper.service /etc/systemd/system/
sudo sed -i "s/YOUR_USER/${USER}/g" /etc/systemd/system/epaper.service
sudo systemctl daemon-reload
sudo systemctl enable epaper
sudo systemctl start epaper
echo "Done. Service is enabled and started. Check: systemctl status epaper"
echo "Logs: journalctl -u epaper -f"
