# Running the official Waveshare 13.3" E demo

Step-by-step from the [13.3inch e-Paper HAT+ (E) Manual](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Raspberry_Pi). Use this to confirm the display works with the manufacturer’s software before debugging the epaper app.

---

## 1. Hardware

- Plug the HAT firmly onto the Pi’s **40-pin GPIO header** (pin 1 to pin 1: Pi’s 3.3V pin aligns with the HAT’s VCC).
- If using a cable, follow the [manual pin table](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT+_(E)_Manual#Hardware_connection): VCC→3.3V, GND→GND, DIN→MOSI(19), CLK→SCLK(23), CS_M→CE0(24), CS_S→CE1(26), DC→22, RST→11, BUSY→18, PWR→12.

---

## 2. Raspberry Pi preparation

### 2.1 Enable SPI

The manual sometimes says “disable”; for the display you need **SPI enabled**.

```bash
sudo raspi-config
# Interface Options → SPI → Yes (enable) → Finish
sudo reboot
```

### 2.2 config.txt

Add the two GPIO lines for the HAT:

```bash
sudo nano /boot/firmware/config.txt
# or, on older images:
# sudo nano /boot/config.txt
```

At the **end** of the file add:

```
gpio=7=op,dl
gpio=8=op,dl
```

Save (Ctrl+O, Enter) and exit (Ctrl+X), then reboot:

```bash
sudo reboot
```

---

## 3. Install Python libraries

From the manual (“Run python demo” → “Install function library”):

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-numpy python3-spidev
```

---

## 4. Download the demo

**Option A – Waveshare (recommended)**

```bash
cd ~
wget "https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch_e-Paper_E.zip" -O 13.3inch_e-Paper_E.zip
unzip 13.3inch_e-Paper_E.zip -d 13.3inch_e-Paper_E
cd 13.3inch_e-Paper_E/RaspberryPi
```

**Option B – 7z (if unzip fails)**

```bash
sudo apt-get install -y p7zip-full
cd ~
wget "https://files.waveshare.com/wiki/13.3inch%20e-Paper%20HAT%2B/13.3inch_e-Paper_E.zip" -O 13.3inch_e-Paper_E.zip
7z x 13.3inch_e-Paper_E.zip -O./13.3inch_e-Paper_E
cd 13.3inch_e-Paper_E/RaspberryPi
```

**Option C – GitHub**

```bash
cd ~
git clone https://github.com/waveshareteam/e-Paper.git e-Paper-waveshare
cd e-Paper-waveshare/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi
```

---

## 5. Run the Python demo

From the `RaspberryPi` directory (so that `python/examples/` and `python/lib/` exist):

```bash
# You should be in ~/13.3inch_e-Paper_E/RaspberryPi (or the GitHub path)
cd python/examples
python3 epd_13in3E_test.py
```

The script adds `../lib` to `sys.path`, so it loads `epd13in3E` and `epdconfig` from the demo’s `python/lib/`. It will Init, Clear, draw “hello world” and shapes, display a BMP, then Clear and Sleep.

---

## 6. If you get `No module named 'epdconfig'` or `'NoneType' ... DEV_ModuleInit`

The demo’s `epdconfig.py` expects compiled `DEV_Config_64_b.so` / `DEV_Config_32_b.so`. If those are missing or wrong for your Pi:

- **Option 1:** Copy this repo’s **Python-only** epdconfig into the demo’s lib so the demo uses it:

  ```bash
  # From the RaspberryPi directory of the demo
  cp /path/to/epaper/config/epdconfig_13in3e.py python/lib/epdconfig.py
  cd python/examples
  python3 epd_13in3E_test.py
  ```

  Replace `/path/to/epaper` with your epaper repo path (e.g. `~/epaper`).

- **Option 2:** If the demo needs a font/image file and you see “No such file”, ensure you’re in `python/examples/` and that the `pic/` folder (with `Font.ttc` and `13in3E.bmp`) is at `python/pic/` (one level up from `examples/`).

---

## 7. Summary

| Step | Action |
|------|--------|
| 1 | HAT on 40-pin header, pin 1 aligned |
| 2 | Enable SPI, add `gpio=7=op,dl` and `gpio=8=op,dl`, reboot |
| 3 | `apt install` python3-pil python3-numpy python3-spidev |
| 4 | Download and unzip 13.3" E demo, `cd .../RaspberryPi` |
| 5 | `cd python/examples` and run `python3 epd_13in3E_test.py` |
| 6 | If epdconfig fails, use this repo’s `config/epdconfig_13in3e.py` as `python/lib/epdconfig.py` |

If the **official** demo shows an image, the hardware and wiring are good; you can then compare with the epaper app (SPI device, speed, epdconfig). If the official demo also shows nothing, the issue is hardware, power, or wiring.
