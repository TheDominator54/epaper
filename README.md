# StellarEars e-ink display client

E-ink display client for **StellarEars**. Runs on a Raspberry Pi, polls the StellarEars `GET /status` API, and refreshes the display only when the shown state changes. Only needs HTTP to the status API.

**Hardware:** Waveshare 2.13" e-Paper HAT V4 (or change the driver in `app/main.py`).

---

## Install (on the Pi)

**1. Enable SPI**

```bash
sudo raspi-config
```

→ **Interface Options** → **SPI** → **Enable** → Finish, then reboot.

**2. Clone the repo**

```bash
git clone https://github.com/YOUR_USERNAME/epaper.git
cd epaper
```

(Use your repo URL if different.)

**3. Run setup**

```bash
chmod +x setup.sh run.sh
./setup.sh
```

This installs Python dependencies (spidev, RPi.GPIO, Pillow) and clones the Waveshare e-Paper library into `lib/e-Paper`.

**4. Run**

```bash
./run.sh
```

Stop with Ctrl+C. To run at boot, see **Run at boot (systemd)** below.

---

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `STELLAREARS_STATUS_URL` | `http://127.0.0.1:8080` | Base URL of StellarEars (no trailing slash). Client requests `GET <url>/status`. |
| `EPD_POLL_INTERVAL` | `30` | Seconds between polls. E-ink is only redrawn when the displayed state changes. |

Example (StellarEars on another host):

```bash
export STELLAREARS_STATUS_URL="http://192.168.1.10:8080"
export EPD_POLL_INTERVAL=60
./run.sh
```

---

## Run at boot (systemd)

```bash
# Adjust paths in epaper.service if your repo is not in /home/pi/epaper
sudo cp epaper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable epaper
sudo systemctl start epaper
```

To override `STELLAREARS_STATUS_URL` or `EPD_POLL_INTERVAL`, see the comment at the top of `epaper.service`.

---

## Prerequisites

- Raspberry Pi (e.g. Pi Zero 2 W) with Raspberry Pi OS
- SPI enabled (step 1 above)
- Git, Python 3, pip
- StellarEars running and reachable at `STELLAREARS_STATUS_URL` (e.g. `http://127.0.0.1:8080` on the same Pi)

---

## API (StellarEars `/status`)

The client expects JSON with at least:

- `muted` (bool) → Mute line
- `saving_speech` (bool) → Rec: Live when true
- `session_will_upload` (bool) → Rec: Will upload when true and not Live
- `last_upload` (str | null), `last_http` (int | null) → Upload line
- `battery_percent` (int | float | null) → Battery line

If the API is unreachable, the first line shows "StellarEars: no API".

---

## Different display model

Edit `app/main.py` and change the driver import (e.g. `epd2in13_V4` → `epd7in5_V2`). Driver files are in `lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/`.
