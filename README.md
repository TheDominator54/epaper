# E-Paper display on Raspberry Pi

Runs a Waveshare e-paper display (e.g. 2.13" V4) on a Raspberry Pi with Python. No Docker.

## Prerequisites

- **Raspberry Pi** (e.g. Pi Zero 2 W) with Raspberry Pi OS
- **SPI enabled:** `sudo raspi-config` → Interface Options → SPI → Enable, then reboot
- **Git**, **Python 3**, **pip**

---

## 1. Get the project with Git

```bash
git clone https://github.com/YOUR_USERNAME/epaper.git
cd epaper
```

(Replace with your repo URL if you pushed this elsewhere.)

---

## 2. Set up (on the Pi)

```bash
chmod +x setup.sh run.sh
./setup.sh
```

This clones the Waveshare e-Paper library into `lib/e-Paper` and installs Python dependencies (spidev, RPi.GPIO, Pillow).

---

## 3. Run

```bash
./run.sh
```

Or manually:

```bash
export PYTHONPATH="$(pwd)/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
python3 app/main.py
```

---

## Changing the display or code

- **Different display:** Edit `app/main.py` and change the import (e.g. `epd2in13_V4` → `epd7in5_V2`). Driver files are in `lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/`.
- **Your code:** Edit `app/main.py` and run `./run.sh` again.

---

## Optional: run at boot

Example with cron (run every 5 minutes):

```bash
crontab -e
# Add (adjust path):
*/5 * * * * cd /home/pi/epaper && ./run.sh
```

Or use a systemd service if you want it to run once at startup.
