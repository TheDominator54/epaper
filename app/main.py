"""
StellarEars e-ink display client.
Polls GET <STELLAREARS_STATUS_URL>/status; updates only when state changes.
3 icons in 1 row (no text): Mute+Session (3 states), Battery (5 states), Connection (2 states).
Uses partial refresh after first full display. Runs on the Pi. SPI required.
"""
import json
import os
import time
import urllib.request
import urllib.error

from waveshare_epd import epd2in13_V4
from PIL import Image, ImageDraw

# Config from environment
STELLAREARS_STATUS_URL = os.environ.get("STELLAREARS_STATUS_URL", "http://127.0.0.1:8080")
EPD_POLL_INTERVAL = int(os.environ.get("EPD_POLL_INTERVAL", "30"))

STATUS_PATH = "/status"

# Display: 122 x 250 (W x H). 1 row, 3 columns.
EPD_W, EPD_H = 122, 250
NUM_COLS = 3
COL_W = EPD_W // NUM_COLS


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
    Single hashable state for redraw-only-when-changed.
    Returns (mute_session, battery_level, connection).
    - mute_session: "muted" | "unmuted" | "active" (session_will_upload)
    - battery_level: 0..4 (0-20, 21-40, 41-60, 61-80, 81-100); None -> 0
    - connection: "success" | "error"
    """
    if status is None:
        return ("unmuted", 0, "error")
    muted = bool(status.get("muted", False))
    session_will_upload = bool(status.get("session_will_upload", False))
    last_upload = status.get("last_upload")
    last_http = status.get("last_http")
    battery_percent = status.get("battery_percent")

    if session_will_upload:
        mute_session = "active"
    elif muted:
        mute_session = "muted"
    else:
        mute_session = "unmuted"

    if battery_percent is None:
        battery_level = 0
    else:
        pct = max(0, min(100, float(battery_percent)))
        if pct <= 20:
            battery_level = 0
        elif pct <= 40:
            battery_level = 1
        elif pct <= 60:
            battery_level = 2
        elif pct <= 80:
            battery_level = 3
        else:
            battery_level = 4

    success = (
        last_upload == "ACCEPTED" or (last_http is not None and 200 <= last_http < 300)
    )
    connection = "success" if success else "error"

    return (mute_session, battery_level, connection)


def _box_center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def draw_mute_session_icon(draw, box, state):
    """3 states: muted (speaker+X), unmuted (speaker), active (speaker + arc/active)."""
    x1, y1, x2, y2 = box
    cx, cy = _box_center(box)
    bw, bh = x2 - x1, y2 - y1
    w = min(20, bw - 6)
    h = min(50, bh - 10)
    sp_left = cx - w // 2
    sp_top = cy - h // 2
    draw.rectangle([sp_left, sp_top, sp_left + w, sp_top + h], outline=0, fill=255)
    cone_w = min(6, bw // 2 - w // 2 - 2)
    draw.polygon(
        [
            (sp_left + w, cy),
            (sp_left + w + cone_w, cy - h // 3),
            (sp_left + w + cone_w, cy + h // 3),
        ],
        outline=0,
        fill=0,
    )
    if state == "muted":
        m = 2
        draw.line(
            [(sp_left - m, sp_top - m), (sp_left + w + cone_w + m, sp_top + h + m)],
            fill=0,
            width=2,
        )
        draw.line(
            [(sp_left + w + cone_w + m, sp_top - m), (sp_left - m, sp_top + h + m)],
            fill=0,
            width=2,
        )
    elif state == "active":
        # Arc or ring around speaker = "active session will upload"
        r = max(w, h) // 2 + 6
        draw.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, fill=0, width=2)


def draw_battery_icon(draw, box, level):
    """5 states: level 0..4 = 0-20%, 21-40%, 41-60%, 61-80%, 81-100%."""
    x1, y1, x2, y2 = box
    cx, cy = _box_center(box)
    bw, bh = x2 - x1, y2 - y1
    w = min(28, bw - 6)
    h = min(55, bh - 10)
    left = cx - w // 2
    top = cy - h // 2
    draw.rectangle([left, top, left + w, top + h], outline=0, fill=255)
    nub_w, nub_h = min(8, w - 4), 3
    draw.rectangle([cx - nub_w // 2, top - nub_h, cx + nub_w // 2, top], outline=0, fill=255)
    # 5 segments bottom-to-top
    seg_h = (h - 4) / 5
    for i in range(5):
        if i < level:
            y0 = int(top + h - 2 - (i + 1) * seg_h)
            y1_fill = int(top + h - 2 - i * seg_h)
            draw.rectangle([left + 2, y0, left + w - 2, y1_fill], outline=0, fill=0)


def draw_connection_icon(draw, box, success):
    """2 states: success (check), error (X)."""
    x1, y1, x2, y2 = box
    cx, cy = _box_center(box)
    bw, bh = x2 - x1, y2 - y1
    s = min(18, bw // 2 - 4, bh // 2 - 4)
    w = 2
    if success:
        draw.line([(cx - s, cy), (cx - s // 3, cy + s)], fill=0, width=w)
        draw.line([(cx - s // 3, cy + s), (cx + s, cy - s)], fill=0, width=w)
    else:
        draw.line([(cx - s, cy - s), (cx + s, cy + s)], fill=0, width=w)
        draw.line([(cx + s, cy - s), (cx - s, cy + s)], fill=0, width=w)


def render_display(image, state):
    """Draw 3 icons in 1 row. image is 122x250 (W x H)."""
    draw = ImageDraw.Draw(image)
    img_w, img_h = image.size
    col_w = img_w // 3
    boxes = [
        (0, 0, col_w, img_h),
        (col_w, 0, 2 * col_w, img_h),
        (2 * col_w, 0, img_w, img_h),
    ]
    mute_session, battery_level, connection = state
    draw_mute_session_icon(draw, boxes[0], mute_session)
    draw_battery_icon(draw, boxes[1], battery_level)
    draw_connection_icon(draw, boxes[2], connection == "success")


def main():
    epd = epd2in13_V4.EPD()
    epd.init()
    # Full buffer size: 122 x 250
    image = Image.new("1", (EPD_W, EPD_H), 255)
    last_state = None
    first_display = True

    while True:
        status = fetch_status()
        state = display_state_from_status(status)
        if state != last_state:
            epd.init()
            render_display(image, state)
            if first_display:
                epd.display(epd.getbuffer(image))
                first_display = False
            else:
                epd.displayPartial(epd.getbuffer(image))
            epd.sleep()
            last_state = state
        time.sleep(EPD_POLL_INTERVAL)


if __name__ == "__main__":
    main()
