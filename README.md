# StellarEars e-ink display client

E-ink display client for **StellarEars**. Runs on a Raspberry Pi and listens for **push** updates: when StellarEars state changes, StellarEars POSTs the status JSON to this client; the display updates only on those events. No polling.

**Hardware:** Waveshare 2.13" e-Paper HAT V4 (or change the driver in `app/main.py`).

---

## File paths

| Path | Description |
|------|-------------|
| **In repo** | |
| `app/main.py` | Main app and display logic. |
| `run.sh` | Run script; sets `PYTHONPATH` and starts the app. |
| `setup.sh` | Clones Waveshare lib and installs Python deps. |
| `epaper.service` | Systemd unit (copy to `/etc/systemd/system/` for run-at-boot). |
| `requirements.txt` | Python dependencies. |
| `lib/e-Paper/` | Waveshare e-Paper library (created by `./setup.sh`, not in git). |
| `lib/e-Paper/RaspberryPi_JetsonNano/python/lib` | Added to `PYTHONPATH` by `run.sh`. |
| `lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/` | Display driver modules (e.g. `epd2in13_V4`). |
| **On the Pi (systemd)** | |
| `/home/YOUR_USER/epaper` | Repo location; set `YOUR_USER` in `epaper.service` to your username. |
| `/etc/systemd/system/epaper.service` | Installed unit file. |
| `/etc/systemd/system/epaper.service.d/override.conf` | Optional env overrides. |

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

This installs Python dependencies (spidev, RPi.GPIO, Pillow) and clones the Waveshare e-Paper library into `lib/e-Paper/`.

**4. Run**

```bash
./run.sh
```

Stop with Ctrl+C. To run at boot, see **Run at boot (systemd)** below.

---

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `EPD_LISTEN_HOST` | `0.0.0.0` | Host to bind the push listener. |
| `EPD_LISTEN_PORT` | `9090` | Port for POST /update and GET /health. |

Example (different port):

```bash
export EPD_LISTEN_PORT=9091
./run.sh
```

---

## Run at boot (systemd)

```bash
# 1. Copy unit and set your Pi username (see File paths: /home/YOUR_USER/epaper)
sudo cp epaper.service /etc/systemd/system/
sudo sed -i 's/YOUR_USER/your_username/' /etc/systemd/system/epaper.service

# 2. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable epaper
sudo systemctl start epaper
```

If it fails: `journalctl -u epaper -n 40 --no-pager`. Ensure you ran `./setup.sh` (so `lib/e-Paper/` exists) and add your user to `spi` and `gpio`: `sudo usermod -aG spi,gpio your_username` (then log out and back in).

To override `EPD_LISTEN_HOST` or `EPD_LISTEN_PORT`, see the comment at the top of `epaper.service` (e.g. `/etc/systemd/system/epaper.service.d/override.conf`).

---

## Prerequisites

- Raspberry Pi (e.g. Pi Zero 2 W) with Raspberry Pi OS
- SPI enabled (step 1 above)
- Git, Python 3, pip
- StellarEars configured to **push** status to this client when state changes (POST to `http://<epaper-host>:9090/update` with JSON body; see StellarEars repo).

---

## Push API (this client)

- **POST /update** — Body: JSON object with the same shape as StellarEars `/status`. The client redraws the e-ink display only when the derived display state (mute/session, battery, connection) changes.
- **GET /health** — Returns 200 for liveness.

StellarEars should call `POST http://<epaper-host>:<EPD_LISTEN_PORT>/update` with the current status JSON whenever its state changes (e.g. mute, session, battery, upload result).

Expected JSON fields (same as StellarEars `/status`):

- `muted` (bool), `session_will_upload` (bool), `last_upload`, `last_http`, `battery_percent`

---

## Different display model

Edit `app/main.py` and change the driver import (e.g. `epd2in13_V4` → `epd7in5_V2`). Driver files are in `lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/`.
