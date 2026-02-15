# 13.3" E-Paper (E) demo on Raspberry Pi 5

Minimal repo to run the [Waveshare 13.3" E Ink HAT+ (E)](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi) demo on a **Raspberry Pi 5**. Follow the official wiki for hardware; this adds the Pi 5–specific steps.

## Robust plan (using venv) — recommended

This uses a virtual environment so **spidev** comes from pip (avoids Bookworm/system spidev issues) while **RPi.GPIO** (rpi-lgpio) and **PIL/numpy** stay from apt. Do the following **on the Pi**, in order.

1. **Hardware** — HAT on 40-pin header (pin 1 to pin 1). Use the official 5 V 5 A USB‑C PSU.
2. **Repo** — `cd ~ && gh repo clone TheDominator54/epaper` (or `cd ~/epaper && git pull`). Then:
   ```bash
   cd ~/epaper
   chmod +x run_demo.sh check_demo.sh setup_venv.sh
   ```
3. **Enable SPI** — `sudo raspi-config` → Interface Options → SPI → **Yes** → Finish → **Reboot**.
4. **After reboot: system packages** (no venv yet):
   ```bash
   sudo apt update
   sudo apt install -y python3-venv python3-rpi-lgpio python3-pil python3-numpy
   sudo apt remove -y python3-rpi.gpio
   ```
   Do **not** add `gpio=7=op,dl` or `gpio=8=op,dl` to `/boot/firmware/config.txt` on Pi 5.
5. **Create venv and install spidev** (in repo root):
   ```bash
   cd ~/epaper
   ./setup_venv.sh
   ```
   This creates `.venv` with `--system-site-packages` and installs **spidev** via pip.
6. **Check** — `./check_demo.sh`. It will use `.venv` if present. Fix any missing item. If it warns about SPI permissions, use `sudo ./run_demo.sh` or `sudo usermod -aG spi $USER` and re-login.
7. **Run** — `./run_demo.sh` (or `sudo ./run_demo.sh` if needed). The script uses `.venv/bin/python` automatically when `.venv` exists.

If the display stays blank or you get SPI errors, see **Run the demo** and **If it still doesn’t work** below.

## Next steps (without venv)

If you prefer not to use a venv: follow **Install the repo** and **On the Pi (one-time setup)** below, then run `./check_demo.sh` and `./run_demo.sh`. On Bookworm, if you see spidev/SPI issues, use the **venv** flow above.

## Install the repo (gh)

On the Pi, install [GitHub CLI](https://cli.github.com/) if needed, then clone the repo:

```bash
sudo apt install -y gh
gh auth login
gh repo clone TheDominator54/epaper
cd epaper
chmod +x run_demo.sh check_demo.sh setup_venv.sh
```

For a **robust, venv-based setup** (recommended on Pi 5 / Bookworm), follow **Robust plan (using venv)** above. Otherwise do the one-time setup below and run the demo.

## Hardware

- Plug the HAT onto the Pi’s 40-pin header (pin 1 to pin 1), or wire per the [Waveshare pin table](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Hardware_connection).
- **Pi 5:** Use the official 5 V 5 A USB‑C PSU.

## On the Pi (one-time setup)

**1. Enable SPI** (per Waveshare: “Raspberry Pi Preparation”)

```bash
sudo raspi-config
```

Choose **Interface Options → SPI → Yes** (the wiki text sometimes says “disable” by mistake — you must **enable** SPI). Finish and reboot:

```bash
sudo reboot
```

**2. Pi 5: use rpi-lgpio instead of RPi.GPIO**

RPi.GPIO does not support Pi 5. Install the drop-in replacement:

```bash
sudo apt update
sudo apt install -y python3-rpi-lgpio
sudo apt remove -y python3-rpi.gpio
```

**3. Install Python libraries** (per Waveshare: “Run python demo”)

```bash
sudo apt install -y python3-pil python3-numpy python3-spidev
```

The repo already includes `pic/` (Font.ttc and 13in3E.bmp) so no extra download is needed. The bundled **13in3E.bmp** is 1200×1600; `check_demo.sh` verifies this (replacements must be 1200×1600 or 1600×1200).

## Run the demo

From the repo root on the Pi:

```bash
cd ~/epaper
./check_demo.sh   # optional: verify SPI, deps, and files (uses .venv if present)
./run_demo.sh     # uses .venv/bin/python when .venv exists
```

**If you see "Permission denied"** opening `/dev/spidev0.0`: run `sudo ./run_demo.sh`, or add your user to the `spi` group and re-login: `sudo usermod -aG spi $USER`.

If the display stays blank, try (on Pi 4 or if not using Pi 5, this picks SPI device 1; on Pi 5 the demo uses both devices automatically):

```bash
EPD_SPI_DEVICE=1 ./run_demo.sh
```

**If it still doesn’t work:** (1) Make sure you have the latest repo (`gh repo sync` or `git pull`) — the Pi 5 epdconfig was fixed so that when the driver selects **both** panel halves (CS_ALL), the same commands are sent to both SPI devices; previously only one half received init. (2) Verify SPI: `ls /dev/spi*` should show `spidev0.0` and `spidev0.1`. (3) On Bookworm, if you see spidev/SPI errors, the [Raspberry Pi forum](https://forums.raspberrypi.com/viewtopic.php?t=389293) suggests using a venv with system packages and pip-installed spidev: `python3 -m venv --system-site-packages .venv`, `source .venv/bin/activate`, `pip install spidev`, then run `./run_demo.sh` from the venv. (4) If the demo **hangs at “e-Paper busy”**: check wiring and SPI; Waveshare’s FAQ suggests shortening the reset low time if the driver board has a power-off switch (see `epd13in3E.py` `Reset()`).

## Pi 5 and config.txt

Per Waveshare you would add `gpio=7=op,dl` and `gpio=8=op,dl` to `/boot/firmware/config.txt`. **On Pi 5 do not add these:** the kernel reserves GPIO 7 and 8 for SPI. The demo’s `lib/epdconfig.py` is already set up for Pi 5 (dual SPI, no GPIO 7/8).

## Reference

- [13.3inch e-Paper HAT+ (E) Manual — Raspberry Pi](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi)

## Verified for Pi 5 (what was fixed)

1. **DC pin** — The display needs DC low for commands and DC high for data (per Waveshare wiki). The 13.3" E Python driver did not set DC (the original .so did). The driver now sets `EPD_DC_PIN` before every `SendCommand` (0) and `SendData`/`SendData2` (1), matching the working 2.13" driver pattern.
2. **CS_ALL = both halves** — When the driver calls `CS_ALL(0)` it selects **both** panel halves; the same command must go to both. The Pi 5 epdconfig now tracks `_main_selected` and `_secondary_selected` and sends each SPI byte to both `spidev0.0` and `spidev0.1` when both are selected, and to only the selected device when only one half is selected (Clear/display image data).
3. **Pi 5 GPIO** — rpi-lgpio is used; GPIO 7/8 are not allocated (kernel keeps them for SPI). Dual SpiDev (0,0) and (0,1) used with the above selection logic.
4. **Pins** — DC=25, RST=17, BUSY=24, PWR=18, CS_M=BCM 8 (CE0), CS_S=BCM 7 (CE1), matching the [Waveshare pin table](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Hardware_connection).
5. **SPI mode** — CPOL=0, CPHA=0 (mode 0) per wiki; epdconfig sets `mode = 0`. **Pi 5 detection** — `_is_pi5()` reads `/proc/device-tree/model` (e.g. "Raspberry Pi 5 Model B Rev 1.0"); dual-SPI is used only when "Raspberry Pi 5" is in that string.
