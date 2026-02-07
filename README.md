# E-paper image server

Web server that accepts image uploads and displays them on a **Waveshare 13.3" E Ink Spectra 6 (E6) Full Color** e-paper display (1600×1200, SPI, HAT+ Standard Driver HAT). Runs bare metal on a Raspberry Pi (e.g. Pi Zero 2 W) with wall power.

**Reference:** [Waveshare 13.3inch e-Paper HAT+ (E) Manual – Raspberry Pi](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi)

---

## Install on a new Raspberry Pi Zero 2 W

Use a fresh Raspberry Pi OS (64-bit) image. Connect to the Pi over SSH (or keyboard/monitor).

### 1. Install and configure Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Follow the URL to authorize the machine in your Tailscale admin. Optionally:
# sudo tailscale set --advertise-exit-node
```

### 2. Install and configure GitHub CLI

```bash
sudo apt-get update
sudo apt-get install -y gh
gh auth login
# Choose: GitHub.com, HTTPS, then paste a token or authenticate in browser
```

### 3. Clone this repo

```bash
cd ~
gh repo clone TheDominator54/epaper
cd epaper
```

### 4. Run the install script

```bash
chmod +x install.sh troubleshoot.sh enable-boot.sh
./install.sh
```

This installs system packages (including Python deps via **apt**: Flask, Pillow, spidev, RPi.GPIO — no virtual environment or pip), enables SPI, adds the required **config.txt** lines for the HAT+ (E), installs the 13.3" E driver from Waveshare’s demo, and adds your user to `spi` and `gpio`. **Reboot** after install so SPI, config.txt, and group membership apply.

### 5. (Optional) Run the app once from the terminal

After rebooting, run the server manually to confirm it works before enabling it at boot:

```bash
cd ~/epaper
export PYTHONPATH="$HOME/epaper/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
python3 app/main.py
```

Open `http://<pi-ip>:8080` in a browser, upload an image, and check that the e-paper updates. Stop the server with **Ctrl+C** when done.

### 6. Enable the service to run at boot

From the repo directory:

```bash
cd ~/epaper
sudo ./enable-boot.sh
```

This installs the systemd unit, sets your username in the service file, and enables and starts the epaper service. The web server will be available at `http://<pi-ip>:8080` (or your Tailscale IP). Upload an image there to display it on the e-paper (scaled to 1600×1200).

### 7. (Optional) Run the troubleshoot script

```bash
chmod +x troubleshoot.sh   # if you see "Permission denied"
./troubleshoot.sh
```

Use this anytime to check that packages, SPI, the Waveshare lib, and the systemd service are correct.

### 8. (Optional) Test the display with the manufacturer demo

If the web app says “display updating” but nothing appears on the panel, run the built-in demo to confirm hardware and SPI:

```bash
chmod +x scripts/run_epd_demo.sh
./scripts/run_epd_demo.sh
```

This runs Init → Clear → draw a test pattern → display → Clear → Sleep. If you see “Display Done!!” and a simple pattern on the screen, the hardware path is working and any issue is likely in the web app’s image format or pipeline.

---

## File paths

| Path | Description |
|------|-------------|
| `app/main.py` | Web server and e-paper update logic. |
| `install.sh` | One-time install: system packages, SPI, config.txt, Waveshare lib, groups. |
| `enable-boot.sh` | Installs systemd unit and enables the service to run at boot. |
| `troubleshoot.sh` | Checks packages, SPI, lib, and service. |
| `scripts/test_epd_demo.py` | Manufacturer-style EPD test: Init, Clear, draw, display, Sleep. |
| `scripts/run_epd_demo.sh` | Sets PYTHONPATH and runs `test_epd_demo.py`. |
| `scripts/check_hat_gpio.py` | Checks SPI devices and reads BUSY pin (no display update). Verifies HAT wiring. |
| `epaper.service` | Systemd unit (installed by `enable-boot.sh`). |
| `API.md` | API reference (endpoints, request/response). |
| `requirements.txt` | Python dependencies. |
| `lib/e-Paper/` | Waveshare e-Paper library (created by `install.sh`). |
| `lib/e-Paper/RaspberryPi_JetsonNano/python/lib` | Set as `PYTHONPATH` in the service. |
| `lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/` | Driver modules (e.g. for 13.3" E6). |
| `/etc/systemd/system/epaper.service` | Installed unit file. |
| `uploads/` | Uploaded images (created by app). |

---

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `EPD_LISTEN_HOST` | `0.0.0.0` | Host to bind the web server. |
| `EPD_LISTEN_PORT` | `8080` | Port for HTTP. |
| `EPD_DRIVER` | `epd13in3e` | Waveshare driver module name (e.g. `epd13in3e` for 13.3" E6). |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `EPD_SPI_BUS` | `0` | SPI bus for epdconfig (default 0). |
| `EPD_SPI_DEVICE` | `0` | SPI device (0 or 1). Try `1` if display stays blank (Waveshare FAQ). |
| `EPD_SPI_SPEED_HZ` | `4000000` | SPI clock (Hz). Try 2000000 or 1000000 if image is corrupt. |

---

## 13.3" E6 (Spectra 6) driver and config

The **13.3" E (E6)** 1600×1200 driver is in the same `waveshareteam/e-Paper` repo under `E-paper_Separate_Program/13.3inch_e-Paper_E`; the file is **epd13in3E.py** (capital E). The install script copies it into `waveshare_epd/epd13in3e.py` so `EPD_DRIVER=epd13in3e` works.

**If you see `ModuleNotFoundError: No module named 'waveshare_epd.epd13in3e'` or `No module named 'epdconfig'`**, copy the driver and config into the lib (from repo root). **epdconfig.py must live in `.../python/lib/`** (the PYTHONPATH directory). Prefer the repo’s **Python-only** epdconfig (no compiled .so) so you don’t need `DEV_Config*.so`:

```bash
LIB=lib/e-Paper/RaspberryPi_JetsonNano/python/lib
cp config/epdconfig_13in3e.py "$LIB/epdconfig.py"
# If the driver is missing:
# E_LIB=lib/e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib
# cp "$E_LIB/epd13in3E.py" "$LIB/waveshare_epd/epd13in3e.py"
```

**If you see `'NoneType' object has no attribute 'DEV_ModuleInit'`**, the Waveshare demo epdconfig is in use and expects compiled `DEV_Config_64_b.so` / `DEV_Config_32_b.so`, which are not shipped. Fix: use the repo’s Python-only epdconfig: `cp config/epdconfig_13in3e.py "$LIB/epdconfig.py"` (with `LIB` as above).

The manual also requires **config.txt** on the Pi: add `gpio=7=op,dl` and `gpio=8=op,dl` (install.sh does this). Use `/boot/config.txt` or `/boot/firmware/config.txt` depending on your OS. Reboot after install.

If the display does not respond (e.g. “e-Paper busy” or no output): check wiring, that SPI is enabled, and see the [manual FAQ](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi) — e.g. if `ls /dev/spi*` shows SPI occupied, you may need to adjust `lib/e-Paper/.../waveshare_epd/epdconfig.py` (CS/position) per Waveshare’s instructions.

**If the app process is killed when you upload** (terminal shows `Killed`), the system ran out of memory (OOM). Check with `dmesg | tail -5` for an `oom-kill` line. On a Pi with 512 MB RAM (e.g. Pi Zero 2 W) and a desktop session, the 13.3" EPD driver's buffers can trigger this. Options: (1) **Add swap** — e.g. `sudo dphys-swapfile swapoff`, edit `/etc/dphys-swapfile` and set `CONF_SWAPSIZE=512` (or `1024`), then `sudo dphys-swapfile setup && sudo dphys-swapfile swapon`. (2) **Run with less load** — close other apps; or run the Pi headless (no desktop) and start the app over SSH so more RAM is free for the EPD update.

### Display shows nothing (software runs, no image)

If the app or `./scripts/run_epd_demo.sh` reports success and you see “Display Done!!” but the panel stays blank, work through this list:

1. **Hardware**
   - **Power:** Use a 3.3V/5V supply that can deliver enough current (e.g. 1A+). Avoid powering only from USB if the Pi is under load.
   - **Connection:** HAT must be firmly on the 40-pin header (pins aligned). If using a cable, follow the [manual pin table](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi): VCC→3.3V, GND→GND, DIN→MOSI(19), CLK→SCLK(23), CS_M→CE0(24), CS_S→CE1(26), DC→22, RST→11, BUSY→18, PWR→12.
   - **FPC:** Don’t bend the display cable; ensure the connector is fully seated on the driver board.

2. **SPI and config**
   - **SPI enabled:** `ls /dev/spi*` should show at least `/dev/spidev0.0` (and often `spidev0.1`). If not, run `sudo raspi-config` → Interface Options → SPI → Enable, then reboot.
   - **config.txt:** Must contain `gpio=7=op,dl` and `gpio=8=op,dl` (install.sh adds these). Use `/boot/firmware/config.txt` or `/boot/config.txt` as appropriate, then reboot.

3. **SPI device and speed (Python epdconfig)**
   - If the display is still blank, try the **other** SPI device (Waveshare FAQ: “modify position to 0,1” when SPI is occupied):
     ```bash
     export EPD_SPI_DEVICE=1
     ./scripts/run_epd_demo.sh
     ```
   - If you see corruption or random content, **lower SPI speed**:
     ```bash
     export EPD_SPI_SPEED_HZ=2000000
     ./scripts/run_epd_demo.sh
     ```
   - Same env vars apply when running the web app (e.g. set them in `epaper.service` or before `python3 app/main.py`).

4. **C demo / reboot**
   - If you previously ran the **C** demo (BCM2835 or WiringPi), reboot the Pi before running the Python demo or web app.

5. **Stuck at “e-Paper busy”**
   - Check wiring and SPI. Ensure BUSY is connected and epdconfig uses BCM 24 for BUSY. If the driver board has a power switch, a long reset can cut power; keep reset low duration short.

6. **Run the official demo**
   - Download the [Waveshare 13.3" E demo](https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch_e-Paper_E.zip), unzip, then from `13.3inch_e-Paper_E/RaspberryPi/python/examples/` run `python3 epd_13in3E_test.py` (with their lib on `PYTHONPATH`). If the **official** demo also shows nothing, the issue is hardware or wiring; if it works, the issue is our epdconfig or driver usage.

---

## Prerequisites

- Raspberry Pi (e.g. Pi Zero 2 W) with Raspberry Pi OS (64-bit)
- Waveshare 13.3" E Ink Spectra 6 (E6) display with HAT+ Driver HAT
- SPI enabled (done by `install.sh`)
- Wall power (no battery)

---

## API

See **[API.md](API.md)** for full details.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI (upload form) |
| POST | `/upload` | Form upload (redirect) |
| POST | `/api/photos` | Upload image — `multipart/form-data` with field `image` or `file`; returns JSON `{"ok": true, "message": "..."}` or `{"ok": false, "error": "..."}` |
| GET | `/health` | Liveness check |

Example: `curl -X POST -F "image=@photo.jpg" http://<pi-ip>:8080/api/photos`
