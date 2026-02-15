# E-paper image server

Web server that accepts image uploads and displays them on a **Waveshare 13.3" E Ink Spectra 6 (E6) Full Color** e-paper display (1600×1200, SPI, HAT+ Standard Driver HAT). Runs bare metal on a Raspberry Pi (e.g. Pi Zero 2 W or Pi 5) with wall power.

**Reference:** [Waveshare 13.3inch e-Paper HAT+ (E) Manual – Raspberry Pi](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi)

---

## Install on a new Raspberry Pi (Zero 2 W or Pi 5)

Use a fresh Raspberry Pi OS (64-bit) image. Connect to the Pi over SSH (or keyboard/monitor).

**Using Raspberry Pi 5:** Same install and app; only these differ: (1) **Power** — use the **official Raspberry Pi USB-C PSU** (5 V 5 A). (2) **config.txt** — on current OS it’s `/boot/firmware/config.txt`; install.sh adds the GPIO lines there. (3) **Swap** — optional on Pi 5 (4 GB+ RAM); you can skip step 0 swap or still add it. (4) **GPIO** — the classic RPi.GPIO library does not support Pi 5’s SoC; install.sh detects Pi 5 and installs **python3-rpi-lgpio** (drop-in replacement) instead. If you see `RuntimeError: Cannot determine SOC peripheral base address`, run `sudo apt install python3-rpi-lgpio` and `sudo apt remove python3-rpi.gpio`, then try again. (5) GPIO/SPI pinout is the same; the HAT uses the same 40-pin header.

### Install your SSH key (passwordless login)

From your **laptop or desktop** (not the Pi), copy your public key to the Pi so you can SSH without typing a password:

**If you already have an SSH key** (e.g. `~/.ssh/id_ed25519.pub` or `~/.ssh/id_rsa.pub`):

```bash
ssh-copy-id pi@<pi-ip>
# Enter the Pi's password when prompted. Example:
# ssh-copy-id pi@192.168.1.100
```

**If you don't have an SSH key yet**, generate one:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Accept the default path (~/.ssh/id_ed25519), optionally set a passphrase
```

Then copy it to the Pi:

```bash
ssh-copy-id pi@<pi-ip>
```

**Alternative (manual):** If `ssh-copy-id` isn't available, on the Pi create `~/.ssh` and append your public key:

```bash
# On the Pi (after SSH with password):
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "PASTE_YOUR_PUBLIC_KEY_LINE_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Replace `<pi-ip>` with the Pi’s IP (from your router, or run `hostname -I` on the Pi). Use the Pi’s default user (often `pi`) or the user you created during Raspberry Pi OS setup. After this, `ssh pi@<pi-ip>` (or `ssh user@<pi-ip>`) should log in without a password.

### 0. Initial Pi setup (update and swap)

**Update the system:**

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo reboot
```

**Add swap (recommended for Pi Zero 2 W with 512MB RAM):**

After reboot, create a 512MB swap file:

```bash
sudo fallocate -l 512M /swapfile
# Or if fallocate isn't available:
# sudo dd if=/dev/zero of=/swapfile bs=1M count=512 status=progress

sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

Make it permanent (enabled after reboot):

```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Verify swap is active:

```bash
free -h
# Should show Swap with non-zero size and some "used" if the system is under load
```

**Note:** Swap helps prevent OOM kills when the 13.3" EPD driver allocates large buffers during display updates. On a Pi Zero 2 W with desktop, this is especially important.

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

### 8. (Optional) Install and run the official Waveshare demo

Before using the web app, test the display with the **official Waveshare demo** to confirm hardware, wiring, and SPI. The web app uses the demo’s lib (`EPD_DEMO_LIB`) so if the demo works, the app should too.

**Demo in this repo (Pi 5 ready)**  
The repo includes the 13.3" E demo under `13.3inch_e-Paper_E/` with a **Pi 5–compatible** `lib/epdconfig.py` (no `.so` files; uses rpi-lgpio and dual SPI). On the Pi:

```bash
# One-time: enable SPI (raspi-config → SPI → Yes), then on Pi 5:
sudo apt install -y python3-rpi-lgpio && sudo apt remove -y python3-rpi.gpio
sudo apt install -y python3-pil python3-numpy python3-spidev

# Run the demo (from repo root on the Pi, e.g. ~/epaper)
./run_demo.sh
# Or manually:
# cd 13.3inch_e-Paper_E/RaspberryPi/python/examples && python3 epd_13in3E_test.py
```

You need `pic/Font.ttc` and `pic/13in3E.bmp` in `13.3inch_e-Paper_E/RaspberryPi/python/pic/` (copy from the [Waveshare zip](https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch_e-Paper_E.zip) if missing). See `13.3inch_e-Paper_E/RaspberryPi/python/README_Pi5.md` for full steps. If the display stays blank, try `export EPD_SPI_DEVICE=1` before running.

**Alternative: demo outside the repo**  
Download the zip from Waveshare, unzip, then copy this repo’s epdconfig into the demo’s `lib/` and run from there (see [docs/waveshare-official-demo.md](docs/waveshare-official-demo.md)).

**What to expect:**

- The demo runs Init → Clear → draws “hello world” and shapes → displays a BMP → Clear → Sleep.
- Each refresh takes about **19 seconds** (you’ll see “e-Paper busy H” for ~20s during Write DRF).
- If you see “Display Done!!” and images appear on the screen, the hardware path is working.
- If only **half** the display updates (e.g. left side), check **CS_S** wiring to **physical pin 26** (see troubleshooting below).

**If the demo works:** The web app should work too (it uses the same demo lib). If the demo fails, fix hardware/wiring before using the app.

**Pi 5, website-only flow:** To follow the [Waveshare wiki](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi) and only add what’s needed for Pi 5, see **[docs/waveshare-official-demo.md](docs/waveshare-official-demo.md)** (Pi 5 section at the top + same steps with Pi 5 notes).

### Checking logs

**When the app runs as a service** (after `enable-boot.sh`), logs go to systemd. On the Pi:

```bash
# Last 50 lines of the epaper service
sudo journalctl -u epaper -n 50 --no-pager

# Follow logs in real time
sudo journalctl -u epaper -f

# Since last boot
sudo journalctl -u epaper -b --no-pager
```

**When you run the app manually** (`python3 app/main.py`), logs print to the terminal (stderr). The subprocess script output appears as `[display_image] ...` in those logs.

**System / kernel messages** (e.g. OOM, USB, crashes):

```bash
# Last 30 kernel lines
dmesg | tail -30

# Errors in this boot
sudo journalctl -b -p err --no-pager
```

**Service status** (is it running?):

```bash
sudo systemctl status epaper
```

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
| `scripts/display_image.py` | Standalone script using the **demo’s** lib (`epd13in3E`). App calls it via subprocess for upload and clear so the display uses the exact same code as the working demo. |
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
| `EPD_SPI_DEVICE` | `0` | SPI device (0 or 1). Many 13.3" HATs need `1`; the systemd service sets `EPD_SPI_DEVICE=1`. |
| `EPD_SPI_SPEED_HZ` | `4000000` | SPI clock (Hz). Try 2000000 or 1000000 if image is corrupt. |
| `EPD_DEMO_LIB` | `~/13.3inch_e-Paper_E/RaspberryPi/python/lib` | Path to the **demo’s** `lib` (must contain `epd13in3E.py` and `epdconfig.py`). The app runs `scripts/display_image.py` in a subprocess using this lib so display uses the exact same code as the working demo. |

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

**If the Pi turns off or reboots when you run the demo or update the display**, the 5 V supply is sagging under load (brownout). The 13.3" panel draws a lot of current during refresh. Fix it by:

- **Power supply:** Use a **5 V, 2.5–3 A** supply (e.g. official Raspberry Pi USB‑C PSU or a known-good adapter). Avoid laptop USB or cheap chargers.
- **USB cable:** Use a **short, good-quality** cable. Long or thin cables drop voltage when current spikes and can cause brownouts.
- **Connection:** Ensure the power plug is fully seated in the Pi and in the wall/adapter.

A 3 A supply is enough for a Pi Zero 2 W + this display; if it still shuts off, the cable or the plug connection is the usual cause.

### Display shows nothing (software runs, no image)

If the app or `./scripts/run_epd_demo.sh` reports success and you see “Display Done!!” but the panel stays blank, work through this list:

1. **Hardware**
   - **Power:** Use a 3.3V/5V supply that can deliver enough current (e.g. 1A+). Avoid powering only from USB if the Pi is under load.
   - **Connection:** HAT must be firmly on the 40-pin header (pins aligned). If using a cable, follow the [manual pin table](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi): VCC→3.3V, GND→GND, DIN→MOSI(19), CLK→SCLK(23), CS_M→CE0(24), CS_S→CE1(26), DC→22, RST→11, BUSY→18, PWR→12.
   - **FPC:** Don’t bend the display cable; ensure the connector is fully seated on the driver board.

2. **SPI and config**
   - **SPI enabled:** `ls /dev/spi*` should show at least `/dev/spidev0.0` (and often `spidev0.1`). If not, run `sudo raspi-config` → Interface Options → SPI → Enable, then reboot.
   - **config.txt (non–Pi 5):** On Pi Zero 2 W and similar, install.sh adds `gpio=7=op,dl` and `gpio=8=op,dl`. **On Pi 5**, the kernel reserves GPIO 7/8 for SPI; our epdconfig uses dual SpiDev (spidev0.0 + spidev0.1) and does not touch those pins, so no config.txt change is needed.

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

6. **Pi 5: `RuntimeError: Cannot determine SOC peripheral base address`**
   - On Raspberry Pi 5, the classic RPi.GPIO library is not supported. Use the drop-in replacement: `sudo apt install python3-rpi-lgpio` and `sudo apt remove python3-rpi.gpio`, then run the demo or app again. `install.sh` does this automatically when it detects a Pi 5.

7. **Pi 5: `lgpio.error: 'GPIO not allocated'` on CS pins (7/8)**
   - With SPI enabled (`dtparam=spi=on`), the **kernel** reserves GPIO 7 and 8 for `/dev/spidev0.0` and `/dev/spidev0.1`, so userspace cannot allocate them. The repo’s **epdconfig** detects Pi 5 and uses **dual SPI** (both spidev0.0 and spidev0.1): it does not call `GPIO.setup` on 7/8 and switches which SPI device it writes to when the driver selects CS_M or CS_S. Ensure you are using `config/epdconfig_13in3e.py` (copied to the demo’s `lib/epdconfig.py` or installed via `install.sh`). You do not need to remove any config.txt lines; the kernel keeps owning 7/8 for SPI.

8. **Run the official demo**
   - Download the [Waveshare 13.3" E demo](https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch_e-Paper_E.zip), unzip, then from `13.3inch_e-Paper_E/RaspberryPi/python/examples/` run `python3 epd_13in3E_test.py` (with their lib on `PYTHONPATH`). If the **official** demo also shows nothing, the issue is hardware or wiring; if it works, the issue is our epdconfig or driver usage.

---

## Prerequisites

- Raspberry Pi (e.g. Pi Zero 2 W or Pi 5) with Raspberry Pi OS (64-bit)
- Waveshare 13.3" E Ink Spectra 6 (E6) display with HAT+ Driver HAT
- SPI enabled (done by `install.sh`)
- Wall power (no battery)

---

## API

See **[API.md](API.md)** for full details.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI (upload form + Clear button) |
| POST | `/upload` | Form upload (redirect) |
| POST | `/clear` | Clear display (Init → Clear → Sleep, ~20–25s). Redirect. |
| POST | `/api/clear` | Clear display; returns JSON `{"ok": true, "message": "..."}` |
| POST | `/api/photos` | Upload image — `multipart/form-data` with field `image` or `file`; returns JSON `{"ok": true, "message": "..."}` or `{"ok": false, "error": "..."}` |
| GET | `/health` | Liveness check |

Examples:  
`curl -X POST -F "image=@photo.jpg" http://<pi-ip>:8080/api/photos`  
`curl -X POST http://<pi-ip>:8080/api/clear` (clear display)
