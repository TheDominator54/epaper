# 13.3" E-Paper HAT+ (E) – Raspberry Pi 5 C demo

This repo runs the **Raspberry Pi 5** C demo for the [13.3inch e-Paper HAT+ (E)](https://www.waveshare.com/wiki/13.3inch_e-Paper_HAT%2B_(E)). The demo is a **self-contained copy** in `demo/` (driver, GUI, fonts, and sample app) so you can remove the vendor `13.3inch_e-Paper_E` folder and use this as a stripped-down base for custom code. Built with **wiringPi** (Pi5).

## Enable SPI

Open the Raspberry Pi terminal and enter the configuration interface:

```
sudo raspi-config
```

Select **Interface Options → SPI → Yes** to enable the SPI interface.

Restart Raspberry Pi:

```
sudo reboot
```

## config.txt file setting

Use the command

```
sudo nano /boot/config.txt
```

or

```
sudo nano /boot/firmware/config.txt
```

Open the corresponding config.txt file

Add at the end

```
gpio=7=op,dl
gpio=8=op,dl
```

Press Ctrl+O (letter O) to save

Press Ctrl+X to exit

Restart Raspberry Pi:

```
sudo reboot
```

## Install wiringPi (Pi5)

```
git clone https://github.com/WiringPi/WiringPi
cd WiringPi
./build
gpio -v
```

# Run gpio -v and corresponding version will appear. If it does not appear, there is an installation error.

## Build (Pi5)

From the repo root:

```bash
./build.sh
```

This builds the C demo in `demo/` with **wiringPi** (Pi5). To build manually or for Pi4 (BCM2835):

```bash
cd demo
sudo make clean
# Pi5 (default)
sudo make -j4 USELIB=USE_WIRINGPI_LIB
# Pi4
# sudo make -j4 USELIB=USE_BCM2835_LIB
```

## Run demo

```bash
./run_demo.sh
```

Or run directly: `sudo ./demo/epd`
