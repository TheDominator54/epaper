"""
StellarEars e-ink display client.
Polls GET <STELLAREARS_STATUS_URL>/status and refreshes the display only when state changes.
Runs on the Pi. Requires SPI enabled.
"""
import json
import os
import time
import urllib.request
import urllib.error

from waveshare_epd import epd2in13_V4
from PIL import Image, ImageDraw, ImageFont

# Config from environment
STELLAREARS_STATUS_URL = os.environ.get("STELLAREARS_STATUS_URL", "http://127.0.0.1:8080")
EPD_POLL_INTERVAL = int(os.environ.get("EPD_POLL_INTERVAL", "30"))

STATUS_PATH = "/status"


def fetch_status():
    """GET StellarEars /status and return parsed JSON, or None on error."""
    url = STELLAREARS_STATUS_URL.rstrip("/") + STATUS_PATH
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def display_state_from_status(status):
    """
    Map API response to a hashable display state so we only redraw when it changes.
    Returns a tuple of values we actually show.
    """
    if status is None:
        return ("error", "?", "?", "?")
    muted = bool(status.get("muted", False))
    saving_speech = bool(status.get("saving_speech", False))
    session_will_upload = bool(status.get("session_will_upload", False))
    last_upload = status.get("last_upload")
    last_http = status.get("last_http")
    battery_percent = status.get("battery_percent")
    # Listening = actively recording speech; Will upload = session has enough to upload
    rec_label = "Live" if saving_speech else ("Will upload" if session_will_upload else "Idle")
    mute_label = "Muted" if muted else "Unmuted"
    if last_upload is not None:
        upload_label = last_upload  # e.g. ACCEPTED, REJECTED
    elif last_http is not None:
        upload_label = f"HTTP {last_http}"
    else:
        upload_label = "--"
    bat_label = f"{int(battery_percent)}%" if battery_percent is not None else "--"
    return (mute_label, rec_label, upload_label, bat_label)


def render_display(epd, status):
    """Draw current status onto the e-ink (four lines: Mute, Rec, Upload, Battery)."""
    width, height = epd.width, epd.height
    image = Image.new("1", (height, width), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    state = display_state_from_status(status)
    mute_label, rec_label, upload_label, bat_label = state
    if status is None:
        line0 = "StellarEars: no API"
        line1, line2, line3 = "Rec: --", "Upload: --", "Battery: --"
    else:
        line0 = f"Mute: {mute_label}"
        line1 = f"Rec: {rec_label}"
        line2 = f"Upload: {upload_label}"
        line3 = f"Battery: {bat_label}"

    y = 8
    for line in (line0, line1, line2, line3):
        draw.text((10, y), line, font=font, fill=0)
        y += 24

    epd.display(epd.getbuffer(image))


def main():
    epd = epd2in13_V4.EPD()
    epd.init()
    last_state = None

    while True:
        status = fetch_status()
        state = display_state_from_status(status)
        if state != last_state:
            epd.init()
            render_display(epd, status)
            epd.sleep()
            last_state = state
        time.sleep(EPD_POLL_INTERVAL)


if __name__ == "__main__":
    main()
