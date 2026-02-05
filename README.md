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

This installs system packages, enables SPI, adds the required **config.txt** lines for the HAT+ (E), installs the 13.3" E driver from Waveshare’s demo, installs Python dependencies, and adds your user to `spi` and `gpio`. **Reboot** after install so SPI, config.txt, and group membership apply.

### 5. Enable the service to run at boot

After rebooting, from the repo directory:

```bash
cd ~/epaper
sudo ./enable-boot.sh
```

This installs the systemd unit, sets your username in the service file, and enables and starts the epaper service. The web server will be available at `http://<pi-ip>:8080` (or your Tailscale IP). Upload an image there to display it on the e-paper (scaled to 1600×1200).

### 6. (Optional) Run the troubleshoot script

```bash
./troubleshoot.sh
```

Use this anytime to check that packages, SPI, the Waveshare lib, and the systemd service are correct.

---

## File paths

| Path | Description |
|------|-------------|
| `app/main.py` | Web server and e-paper update logic. |
| `install.sh` | One-time install: system packages, SPI, config.txt, Waveshare lib, groups. |
| `enable-boot.sh` | Installs systemd unit and enables the service to run at boot. |
| `troubleshoot.sh` | Checks packages, SPI, lib, and service. |
| `epaper.service` | Systemd unit (installed by `enable-boot.sh`). |
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

---

## 13.3" E6 (Spectra 6) driver and config

The **13.3" E (E6)** 1600×1200 driver is provided in Waveshare’s separate demo package, not the main `waveshareteam/e-Paper` repo. The install script:

1. Downloads the demo from [Waveshare’s wiki](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi) (or GitHub [E-paper_Separate_Program/13.3inch_e-Paper_E](https://github.com/waveshare/e-Paper/tree/master/E-paper_Separate_Program/13.3inch_e-Paper_E)).
2. Installs the Python driver into `lib/e-Paper/.../waveshare_epd/` so `EPD_DRIVER=epd13in3e` works.

The manual also requires **config.txt** on the Pi: add `gpio=7=op,dl` and `gpio=8=op,dl` (install.sh does this). Use `/boot/config.txt` or `/boot/firmware/config.txt` depending on your OS. Reboot after install.

If the display does not respond (e.g. “e-Paper busy” or no output): check wiring, that SPI is enabled, and see the [manual FAQ](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi) — e.g. if `ls /dev/spi*` shows SPI occupied, you may need to adjust `lib/e-Paper/.../waveshare_epd/epdconfig.py` (CS/position) per Waveshare’s instructions.

---

## Prerequisites

- Raspberry Pi (e.g. Pi Zero 2 W) with Raspberry Pi OS (64-bit)
- Waveshare 13.3" E Ink Spectra 6 (E6) display with HAT+ Driver HAT
- SPI enabled (done by `install.sh`)
- Wall power (no battery)

---

## API

- **GET /** — Simple upload form and status.
- **POST /upload** — `multipart/form-data` with an image file. The image is scaled to the display resolution and shown on the e-paper. Response: redirect or JSON `{"ok": true}`.
