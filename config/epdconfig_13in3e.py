# Python-only epdconfig for Waveshare 13.3" E Ink HAT+ (E).
# Same API as the demo's epdconfig but uses spidev + RPi.GPIO instead of DEV_Config*.so.
# Pin layout per Waveshare 13.3inch e-Paper HAT+ (E) manual (BCM: CS_M=8/CE0, CS_S=7/CE1).
#
# On Raspberry Pi 5 with SPI enabled, the kernel reserves GPIO 7 and 8 for spidev0.0/0.1,
# so we cannot allocate them with lgpio. We use two SpiDev handles (CE0 + CE1) and
# switch which one we write to when the driver selects CS_M or CS_S (kernel asserts CS per transfer).

import os
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

# Optional: EPD_SPI_BUS, EPD_SPI_DEVICE (default 0,0). If display stays blank, try 0,1 per Waveshare FAQ.
# EPD_SPI_SPEED_HZ: default 1000000 to reduce peak current (avoid brownout). 4000000 if power is solid.
# EPD_PWR_DELAY_SEC: seconds to wait after PWR on before SPI init (spreads inrush). Default 2.
_spi = None
# Pi 5: kernel owns GPIO 7/8; we use two SPI devices and switch on CS_M/CS_S selection.
_spi_m = None
_spi_s = None
_use_pi5_dual_spi = False


def _is_pi5() -> bool:
    try:
        with open("/proc/device-tree/model", "rb") as f:
            model = f.read().rstrip(b"\x00").decode("utf-8", errors="replace")
            return "Raspberry Pi 5" in model
    except Exception:
        return False


def _digital_write(pin: int, value: int) -> None:
    GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)


def _digital_read(pin: int) -> int:
    return 1 if GPIO.input(pin) else 0


def digital_write(pin: int, value: int) -> None:
    global _spi
    if _use_pi5_dual_spi and value:
        if pin == EPD_CS_M_PIN:
            _spi = _spi_m
        elif pin == EPD_CS_S_PIN:
            _spi = _spi_s
    if not _use_pi5_dual_spi or pin not in (EPD_CS_M_PIN, EPD_CS_S_PIN):
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
    global _spi, _spi_m, _spi_s, _use_pi5_dual_spi
    _use_pi5_dual_spi = _is_pi5()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(EPD_RST_PIN, GPIO.OUT)
    GPIO.setup(EPD_DC_PIN, GPIO.OUT)
    if not _use_pi5_dual_spi:
        GPIO.setup(EPD_CS_M_PIN, GPIO.OUT)
        GPIO.setup(EPD_CS_S_PIN, GPIO.OUT)
    GPIO.setup(EPD_PWR_PIN, GPIO.OUT)
    GPIO.setup(EPD_BUSY_PIN, GPIO.IN)

    _digital_write(EPD_PWR_PIN, 1)
    pwr_delay = float(os.environ.get("EPD_PWR_DELAY_SEC", "2"))
    if pwr_delay > 0:
        time.sleep(pwr_delay)

    bus = int(os.environ.get("EPD_SPI_BUS", "0"))
    device = int(os.environ.get("EPD_SPI_DEVICE", "0"))
    speed_hz = int(os.environ.get("EPD_SPI_SPEED_HZ", "1000000"))
    if _use_pi5_dual_spi:
        # Kernel owns CE0/CE1 (GPIO 8/7); use both SPI devices and switch on CS_M/CS_S selection.
        _spi_m = spidev.SpiDev()
        _spi_m.open(bus, 0)
        _spi_m.max_speed_hz = speed_hz
        _spi_m.mode = 0
        _spi_s = spidev.SpiDev()
        _spi_s.open(bus, 1)
        _spi_s.max_speed_hz = speed_hz
        _spi_s.mode = 0
        _spi = _spi_m
    else:
        _spi = spidev.SpiDev()
        _spi.open(bus, device)
        _spi.max_speed_hz = speed_hz
        _spi.mode = 0


def module_exit() -> None:
    global _spi, _spi_m, _spi_s
    if _use_pi5_dual_spi:
        if _spi_m is not None:
            _spi_m.close()
            _spi_m = None
        if _spi_s is not None:
            _spi_s.close()
            _spi_s = None
        _spi = None
    elif _spi is not None:
        _spi.close()
        _spi = None
    _digital_write(EPD_RST_PIN, 0)
    _digital_write(EPD_DC_PIN, 0)
    if not _use_pi5_dual_spi:
        _digital_write(EPD_CS_M_PIN, 0)
        _digital_write(EPD_CS_S_PIN, 0)
    _digital_write(EPD_PWR_PIN, 0)
