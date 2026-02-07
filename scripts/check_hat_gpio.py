#!/usr/bin/env python3
"""
Check that the Pi can see the 13.3" E HAT over GPIO and SPI.
Uses the same BCM pins as epdconfig. Run on the Pi (needs RPi.GPIO, gpio group or root).

  python3 scripts/check_hat_gpio.py

Does not drive the display; only checks SPI devices exist and reads the BUSY pin.
"""

import os
import sys

# BCM pins (same as config/epdconfig_13in3e.py)
EPD_CS_M_PIN = 8   # CE0, physical 24
EPD_CS_S_PIN = 7   # CE1, physical 26
EPD_DC_PIN = 25    # physical 22
EPD_RST_PIN = 17   # physical 11
EPD_BUSY_PIN = 24  # physical 18  <-- must be correct or "e-Paper busy" forever
EPD_PWR_PIN = 18   # physical 12


def main():
    print("13.3\" E HAT connection check (GPIO + SPI)")
    print("Pins (BCM): RST={}, DC={}, CS_M={}, CS_S={}, PWR={}, BUSY={}".format(
        EPD_RST_PIN, EPD_DC_PIN, EPD_CS_M_PIN, EPD_CS_S_PIN, EPD_PWR_PIN, EPD_BUSY_PIN,
    ))
    print()

    # 1. SPI devices
    for path in ["/dev/spidev0.0", "/dev/spidev0.1"]:
        if os.path.exists(path):
            print("[OK] {} exists".format(path))
        else:
            print("[--] {} missing (enable SPI: raspi-config -> Interface -> SPI)".format(path))
    print()

    # 2. GPIO
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        print("[FAIL] RPi.GPIO not installed. apt install python3-rpi.gpio")
        sys.exit(1)

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Outputs
        for pin in (EPD_RST_PIN, EPD_DC_PIN, EPD_CS_M_PIN, EPD_CS_S_PIN, EPD_PWR_PIN):
            GPIO.setup(pin, GPIO.OUT)
        GPIO.setup(EPD_BUSY_PIN, GPIO.IN)
    except Exception as e:
        print("[FAIL] GPIO setup: {}".format(e))
        print("       Ensure user is in 'gpio' group: sudo usermod -aG gpio $USER (then log out/in)")
        sys.exit(1)

    try:
        # PWR off first
        GPIO.output(EPD_PWR_PIN, GPIO.LOW)
        GPIO.output(EPD_RST_PIN, GPIO.LOW)
        GPIO.output(EPD_DC_PIN, GPIO.LOW)
        GPIO.output(EPD_CS_M_PIN, GPIO.HIGH)
        GPIO.output(EPD_CS_S_PIN, GPIO.HIGH)

        # Read BUSY with PWR off
        busy_off = GPIO.input(EPD_BUSY_PIN)
        print("BUSY (PWR off): {} (0=low, 1=high)".format(busy_off))

        # PWR on
        GPIO.output(EPD_PWR_PIN, GPIO.HIGH)
        import time
        time.sleep(0.1)
        busy_after_pwr = GPIO.input(EPD_BUSY_PIN)
        print("BUSY (PWR on, 0.1s): {} (0=low, 1=high)".format(busy_after_pwr))

        # Short reset pulse (as driver might do)
        GPIO.output(EPD_RST_PIN, GPIO.LOW)
        time.sleep(0.02)
        GPIO.output(EPD_RST_PIN, GPIO.HIGH)
        time.sleep(0.1)
        busy_after_rst = GPIO.input(EPD_BUSY_PIN)
        print("BUSY (after short RST pulse): {} (0=low, 1=high)".format(busy_after_rst))

        # Cleanup
        GPIO.output(EPD_PWR_PIN, GPIO.LOW)
        GPIO.cleanup()

        print()
        if busy_after_pwr == 0 and busy_after_rst == 0:
            print("BUSY stayed 0 (low). Driver waits for BUSY=1 (high) for 'idle'.")
            print("If the demo hangs at 'e-Paper busy H', BUSY is not going high.")
            print("  -> Check BUSY is wired to Pi physical pin 18 (BCM 24).")
        elif busy_after_pwr == 1 or busy_after_rst == 1:
            print("BUSY read as 1 at least once -> pin is not stuck low. Wiring may be OK.")
        print("Done. Run the demo or app to test full display.")
    except Exception as e:
        print("[FAIL] {}".format(e))
        try:
            GPIO.cleanup()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
