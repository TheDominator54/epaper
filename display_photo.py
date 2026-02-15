#!/usr/bin/env python3
"""
Standalone script for Waveshare 13.3" e-Paper HAT+ (E) on Raspberry Pi 5.
Fetch a photo from a URL and display it, or clear the screen.
Run from repo root. No extra installs; uses same deps as the demo.

  python3 display_photo.py <image_url>   → fetch and display photo
  python3 display_photo.py --clear       → clear screen
"""
import io
import os
import sys

# Run from repo root: lib is python/lib
_this_dir = os.path.dirname(os.path.realpath(__file__))
_libdir = os.path.join(_this_dir, "python", "lib")
if os.path.exists(_libdir):
    sys.path.insert(0, _libdir)

import epd13in3E
from PIL import Image

EPD_WIDTH = 1200
EPD_HEIGHT = 1600


def fetch_image(url):
    """Fetch image bytes from URL. Uses stdlib only."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "e-Paper/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def format_for_display(image):
    """Resize and letterbox to EPD_WIDTH x EPD_HEIGHT. Returns RGB Image."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    w, h = image.size
    scale = min(EPD_WIDTH / w, EPD_HEIGHT / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), (255, 255, 255))
    canvas.paste(image, ((EPD_WIDTH - new_w) // 2, (EPD_HEIGHT - new_h) // 2))
    return canvas


def main():
    if len(sys.argv) < 2:
        print("Usage:  python3 display_photo.py <image_url>  |  python3 display_photo.py --clear")
        sys.exit(1)

    if sys.argv[1] == "--clear":
        epd = epd13in3E.EPD()
        epd.Init()
        print("Clearing screen...")
        epd.Clear()
        epd.sleep()
        print("Done.")
        return

    url = sys.argv[1]
    print("Fetching image...")
    data = fetch_image(url)
    image = Image.open(io.BytesIO(data))
    print("Formatting for display...")
    formatted = format_for_display(image)

    epd = epd13in3E.EPD()
    epd.Init()
    print("Displaying (refresh ~19s)...")
    epd.display(epd.getbuffer(formatted))
    epd.sleep()
    print("Done.")


if __name__ == "__main__":
    main()
