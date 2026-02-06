#!/usr/bin/env python3
"""
Waveshare 13.3" E (E6) display test — manufacturer demo sequence.

Uses the same driver and epdconfig as the main app. Run from repo root with:

  export PYTHONPATH="$HOME/epaper/lib/e-Paper/RaspberryPi_JetsonNano/python/lib"
  python3 scripts/test_epd_demo.py

Or: ./scripts/run_epd_demo.sh (sets PYTHONPATH and runs this script).

Sequence: Init -> Clear -> draw test image -> display -> Clear -> Sleep.
If you see "Display Done!!" and no errors, the hardware path is working.
"""

import os
import sys

# Ensure we use the repo's lib (epdconfig + waveshare_epd)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO_ROOT, "lib", "e-Paper", "RaspberryPi_JetsonNano", "python", "lib")
if os.path.isdir(LIB) and LIB not in sys.path:
    sys.path.insert(0, LIB)

# Driver module name (must match EPD_DRIVER / waveshare_epd)
EPD_DRIVER = os.environ.get("EPD_DRIVER", "epd13in3e")

def main():
    import time
    from PIL import Image, ImageDraw

    print("13.3\" e-Paper (E) demo test...")
    print("Using PYTHONPATH (or sys.path):", LIB)

    mod = __import__(f"waveshare_epd.{EPD_DRIVER}", fromlist=["EPD", "EPD_WIDTH", "EPD_HEIGHT"])
    EPD = getattr(mod, "EPD")
    EPD_WIDTH = getattr(mod, "EPD_WIDTH", 1200)
    EPD_HEIGHT = getattr(mod, "EPD_HEIGHT", 1600)

    epd = EPD()
    print(f"EPD size: {EPD_WIDTH}x{EPD_HEIGHT}")

    try:
        print("Init...")
        epd.Init()
        print("Clear...")
        epd.Clear()

        # Draw a simple test image (RGB, 7-color panel will quantize)
        print("Draw test image...")
        Himage = Image.new("RGB", (epd.width, epd.height), epd.WHITE)
        draw = ImageDraw.Draw(Himage)
        # Shapes so we see something even without a font
        draw.rectangle((20, 20, 200, 120), outline=epd.BLACK, width=4)
        draw.rectangle((220, 20, 400, 120), fill=epd.RED)
        draw.rectangle((420, 20, 600, 120), fill=epd.BLUE)
        draw.ellipse((620, 20, 800, 120), outline=epd.BLACK, width=2)
        draw.line((20, 200, 400, 200), fill=epd.BLACK, width=2)
        draw.text((30, 220), "13.3\" E test (no Font.ttc)", fill=epd.BLACK)

        print("Display buffer...")
        epd.display(epd.getbuffer(Himage))
        print("Wait 3s...")
        time.sleep(3)

        print("Clear again...")
        epd.Clear()
        print("Sleep...")
        epd.Sleep()

        print("Demo finished successfully. Check the display for the test pattern.")
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        try:
            epd.Sleep()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
