#!/usr/bin/env python3
"""
Display an image on the 13.3" E panel using the **exact same code path as the
Waveshare demo**: same lib dir, same "import epd13in3E", same Init/Clear/display/Sleep.

Call from the app via subprocess so the display runs with the demo's lib and epdconfig.
Usage: display_image.py <image_path>   OR   display_image.py --clear

Requires: EPD_DEMO_LIB or default ~/13.3inch_e-Paper_E/RaspberryPi/python/lib
          (that dir must contain epd13in3E.py and epdconfig.py)
Env: EPD_SPI_DEVICE=1 (recommended for 13.3" E HAT)
"""
import os
import sys

def log(msg):
    print(msg, flush=True)

def main():
    clear_only = "--clear" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--clear"]
    if clear_only:
        image_path = None
    elif not args:
        log("Usage: display_image.py <image_path>  or  display_image.py --clear")
        sys.exit(1)
    else:
        image_path = os.path.abspath(args[0])
        if not os.path.isfile(image_path):
            log("Error: not a file: %s" % image_path)
            sys.exit(1)

    libdir = os.environ.get("EPD_DEMO_LIB", os.path.expanduser("~/13.3inch_e-Paper_E/RaspberryPi/python/lib"))
    libdir = os.path.normpath(libdir)
    log("EPD_DEMO_LIB=%s" % libdir)
    if not os.path.isdir(libdir):
        log("Error: EPD_DEMO_LIB is not a directory: %s" % libdir)
        sys.exit(1)
    if libdir not in sys.path:
        sys.path.insert(0, libdir)

    log("Importing epd13in3E from demo lib (exact demo code path)")
    import epd13in3E
    import time
    from PIL import Image

    log("epd13in3E.EPD()")
    epd = epd13in3E.EPD()
    log("epd.Init()")
    epd.Init()
    log("epd.Clear()")
    epd.Clear()
    log("epd.Clear() done")

    sleep_fn = getattr(epd, "Sleep", getattr(epd, "sleep"))
    if clear_only:
        log("Clear-only: epd.sleep()")
        sleep_fn()
        log("Clear finished successfully")
        return

    log("Opening image: %s" % image_path)
    Himage = Image.open(image_path).convert("RGB")
    log("Resize to (%d, %d)" % (epd.width, epd.height))
    Himage = Himage.resize((epd.width, epd.height), Image.Resampling.LANCZOS)
    log("epd.getbuffer(Himage)")
    buf = epd.getbuffer(Himage)
    log("epd.display(buf) (~19s)")
    epd.display(buf)
    log("epd.sleep()")
    sleep_fn()
    log("Display update finished successfully")

if __name__ == "__main__":
    main()
