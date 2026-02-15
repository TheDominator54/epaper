# 13.3" E-Paper (E) Python demo — Pi 5 ready

This demo is set up for **Raspberry Pi 5** (and works on Pi Zero 2 W / Pi 4). The `lib/epdconfig.py` in this folder is the Pi 5–compatible version: it uses **rpi-lgpio** and **dual SPI** (spidev0.0 + spidev0.1) so the kernel keeps GPIO 7/8; no `.so` files or config.txt CS lines are required on Pi 5.

## On the Pi (one-time)

1. **Enable SPI**  
   `sudo raspi-config` → Interface Options → SPI → Yes → reboot.

2. **Pi 5 only: GPIO library**  
   ```bash
   sudo apt install -y python3-rpi-lgpio
   sudo apt remove -y python3-rpi.gpio
   ```

3. **Other deps**  
   ```bash
   sudo apt update
   sudo apt install -y python3-pil python3-numpy python3-spidev
   ```

4. **Pic assets** (if you don’t have them)  
   The test script expects `pic/Font.ttc` and `pic/13in3E.bmp`. If missing, copy the `pic` folder from the [Waveshare 13.3" E demo zip](https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch_e-Paper_E.zip) into `RaspberryPi/python/` (so `python/pic/` exists).

## Run the demo

From the **repo root** on the Pi (e.g. `~/epaper`):

```bash
./run_demo.sh
```

Or from this folder: `cd examples && python3 epd_13in3E_test.py`

If the display stays blank, try:

```bash
export EPD_SPI_DEVICE=1
python3 epd_13in3E_test.py
```

Optional env: `EPD_SPI_SPEED_HZ`, `EPD_PWR_DELAY_SEC` (see `lib/epdconfig.py`).

## config.txt (non–Pi 5)

On Pi Zero 2 W / Pi 4 you can add at the end of `/boot/firmware/config.txt` (or `/boot/config.txt`):

```
gpio=7=op,dl
gpio=8=op,dl
```

On **Pi 5** do **not** add these; the kernel reserves GPIO 7/8 for SPI.
