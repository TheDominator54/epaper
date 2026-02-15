# 13.3" E-Paper (E) demo on Raspberry Pi 5

Minimal repo to run the [Waveshare 13.3" E Ink HAT+ (E)](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi) demo on a **Raspberry Pi 5**. Follow the official wiki for hardware; this adds the Pi 5–specific steps.

## Hardware

- Plug the HAT onto the Pi’s 40-pin header (pin 1 to pin 1), or wire per the [Waveshare pin table](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Hardware_connection).
- **Pi 5:** Use the official 5 V 5 A USB‑C PSU.

## On the Pi (one-time setup)

**1. Enable SPI** (per Waveshare: “Raspberry Pi Preparation”)

```bash
sudo raspi-config
```

Choose **Interface Options → SPI → Yes**. Finish and reboot:

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

The repo already includes `pic/` (Font.ttc and 13in3E.bmp) so no extra download is needed.

## Run the demo

From the repo root on the Pi:

```bash
cd ~/epaper
./check_demo.sh   # optional: verify SPI, deps, and files
./run_demo.sh
```

If the display stays blank, try:

```bash
EPD_SPI_DEVICE=1 ./run_demo.sh
```

## Pi 5 and config.txt

Per Waveshare you would add `gpio=7=op,dl` and `gpio=8=op,dl` to `/boot/firmware/config.txt`. **On Pi 5 do not add these:** the kernel reserves GPIO 7 and 8 for SPI. The demo’s `lib/epdconfig.py` is already set up for Pi 5 (dual SPI, no GPIO 7/8).

## Reference

- [13.3inch e-Paper HAT+ (E) Manual — Raspberry Pi](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi)
