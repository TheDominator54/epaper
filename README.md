# e-Paper Photo Display

Waveshare 13.3" e-Paper HAT+ (E) on Raspberry Pi 5. Single-script web app to load image/text into a preview, adjust it, and either display immediately (static mode) or add it to a rotating playlist.

## Run manually (foreground)

```bash
cd ~/epaper
python3 display_photo.py
```

Then open `http://localhost:5000` (or `http://<pi-ip>:5000` from another device).

Health check:

```bash
curl http://localhost:5000/api/status
```

## Static mode vs rotation mode

- **Static mode**: Load a source into preview, then click **Display Now**.
- **Rotation mode**: Add one or more preview snapshots to the queue, set interval seconds, and toggle rotation on/off at any time.
- **Display Now + Also add**: Enable the checkbox to both show immediately and append the same preview to the rotation queue.
- Rotation queue and settings persist on disk under `.rotation_store/` and are restored after restart.

## Install service (run at boot)

```bash
cd ~/epaper
sudo sh install-service.sh
```

## Control the background service

```bash
# Start
sudo systemctl start epaper

# Stop
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

## API quick reference

```bash
# Service status (includes rotation status summary)
curl http://localhost:5000/api/status

# Rotation status
curl http://localhost:5000/api/rotation/status

# Enable rotation
curl -X POST http://localhost:5000/api/rotation/toggle \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true}'

# Set rotation interval in seconds
curl -X POST http://localhost:5000/api/rotation/settings \
  -H 'Content-Type: application/json' \
  -d '{"interval_seconds":900}'

# Add current preview to rotation queue
curl -X POST http://localhost:5000/api/rotation/add

# Display now and optionally add to queue
curl -X POST http://localhost:5000/api/rotation/display_now \
  -H 'Content-Type: application/json' \
  -d '{"also_add":true}'
```

## Reliability defaults

- Max upload size: 16 MB (`POST /api/preview/source` multipart)
- Max fetched URL image size: 12 MB
- URL fetch accepts `http`/`https` only
- Private-network URLs are blocked by default; allow with:

```bash
export EPAPER_ALLOW_PRIVATE_URLS=1
```