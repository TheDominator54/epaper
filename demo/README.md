# 13.3" E-Paper demo (self-contained)

Stripped-down C demo for Raspberry Pi 5. Build from repo root: `../build.sh`. Run: `../run_demo.sh` or `sudo ./epd`.

## Layout

| Path | Role |
|------|------|
| `examples/main.c` | Entry point, runs `EPD_13in3e_test()` |
| `examples/EPD_13in3e_test.c` | Demo sequence: init, clear, show image, draw shapes/text |
| `examples/ImageData.c` | Sample image data (e.g. `Image6color`) |
| `lib/Config/` | GPIO/SPI (DEV_Config) – BCM2835 or wiringPi |
| `lib/e-Paper/` | Display driver (EPD_13in3e) |
| `lib/GUI/` | Drawing (Paint, BMP) |
| `lib/Fonts/` | Font data |

For a custom app (e.g. image from web): keep `lib/` as-is, replace or extend `examples/` and wire your image buffer into `EPD_13IN3E_Display()`.
