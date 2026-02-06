# Python-only epdconfig for Waveshare 13.3" E Ink HAT+ (E).
# Same API as the demo's epdconfig but uses spidev + RPi.GPIO instead of DEV_Config*.so.
# Pin layout per Waveshare 13.3inch e-Paper HAT+ (E) manual.

import time

import RPi.GPIO as GPIO
import spidev

# Pin definitions (BCM) for 13.3" E HAT+
EPD_CS_M_PIN = 8
EPD_CS_S_PIN = 7
EPD_DC_PIN = 25
EPD_RST_PIN = 17
EPD_BUSY_PIN = 24
EPD_PWR_PIN = 18

_spi = None


def _digital_write(pin: int, value: int) -> None:
    GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)


def _digital_read(pin: int) -> int:
    return 1 if GPIO.input(pin) else 0


def digital_write(pin: int, value: int) -> None:
    _digital_write(pin, value)


def digital_read(pin: int) -> int:
    return _digital_read(pin)


def spi_writebyte(value: int) -> None:
    _spi.writebytes([value & 0xFF])


def spi_writebyte2(buf, length: int) -> None:
    if hasattr(buf, "__getitem__"):
        data = list(buf)[:length]
    else:
        data = list(buf)[:length]
    _spi.writebytes(data)


def delay_ms(ms: float) -> None:
    time.sleep(ms / 1000.0)


def module_init() -> None:
    global _spi
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(EPD_RST_PIN, GPIO.OUT)
    GPIO.setup(EPD_DC_PIN, GPIO.OUT)
    GPIO.setup(EPD_CS_M_PIN, GPIO.OUT)
    GPIO.setup(EPD_CS_S_PIN, GPIO.OUT)
    GPIO.setup(EPD_PWR_PIN, GPIO.OUT)
    GPIO.setup(EPD_BUSY_PIN, GPIO.IN)

    _digital_write(EPD_PWR_PIN, 1)

    _spi = spidev.SpiDev()
    _spi.open(0, 0)
    _spi.max_speed_hz = 4_000_000
    _spi.mode = 0


def module_exit() -> None:
    global _spi
    if _spi is not None:
        _spi.close()
        _spi = None
    _digital_write(EPD_RST_PIN, 0)
    _digital_write(EPD_DC_PIN, 0)
    _digital_write(EPD_CS_M_PIN, 0)
    _digital_write(EPD_CS_S_PIN, 0)
    _digital_write(EPD_PWR_PIN, 0)
