# e-Paper Photo Display

Waveshare 13.3" e-Paper HAT+ (E) on Raspberry Pi 5. Web UI to upload or paste a photo URL, rotate/crop, and display. Runs as a single script; no extra installs.

## Run manually (foreground)

```bash
cd ~/epaper
python3 display_photo.py
```

Then open http://localhost:5000 (or http://\<pi-ip\>:5000 from another device).

## Install service (run at boot)

```bash
cd ~/epaper
sudo sh install-service.sh
```

Edit `epaper.service` first if your username is not `dominic` (change `User=`).

## Control the background service

```bash
# Start
sudo systemctl start epaper

# Stop (kill)
sudo systemctl stop epaper

# Restart
sudo systemctl restart epaper

# Status
sudo systemctl status epaper

# Disable from starting at boot
sudo systemctl disable epaper
```

## CLI (without starting the server)

```bash
# Display image from URL
python3 display_photo.py https://example.com/photo.jpg

# Clear screen
python3 display_photo.py --clear
```
