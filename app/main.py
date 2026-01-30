"""
StellarEars e-ink display client.
Listens for POST /update with JSON body (same shape as StellarEars /status).
Updates the display only when StellarEars pushes a state change. No polling.
3 icons in 1 row (no text): Mute+Session (3 states), Battery (5 states), Connection (2 states).
Uses full refresh on every update. Runs on the Pi. SPI required.
"""
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from waveshare_epd import epd2in13_V4
from PIL import Image, ImageDraw

# Config from environment
EPD_LISTEN_HOST = os.environ.get("EPD_LISTEN_HOST", "0.0.0.0")
EPD_LISTEN_PORT = int(os.environ.get("EPD_LISTEN_PORT", "9090"))

# Display: 122 x 250 (W x H). Hardware shows buffer as 122=vertical, 250=horizontal (landscape).
# We lay out 3 icons along the 250 axis so they appear as 3 columns in portrait (cable at bottom).
EPD_W, EPD_H = 122, 250
NUM_COLS = 3


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


def _draw_icon_rotated(image, box, draw_fn, *args):
    """Draw icon in a tile rotated 90° so it runs along the column height; paste into image at box."""
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    # Tile: use column height as "width" so icon utilizes the tall dimension; then rotate -90 to fit column
    tile = Image.new("1", (bh, bw), 255)  # (250, 40) for default column
    draw_tile = ImageDraw.Draw(tile)
    rotated_box = (0, 0, bh, bw)  # (0, 0, 250, 40)
    draw_fn(draw_tile, rotated_box, *args)
    rotated = tile.rotate(-90, expand=True)  # 250x40 -> 40x250
    image.paste(rotated, (x1, y1))


def render_display(image, state):
    """Draw 3 icons along the long axis so they appear as 3 columns in portrait. image is 122x250 (W x H)."""
    img_w, img_h = image.size
    # Bands along the 250 axis → 3 vertical columns when display shows 122=vertical, 250=horizontal
    band_h = img_h // 3
    boxes = [
        (0, 0, img_w, band_h),
        (0, band_h, img_w, 2 * band_h),
        (0, 2 * band_h, img_w, img_h),
    ]
    mute_session, battery_level, connection = state
    _draw_icon_rotated(image, boxes[0], draw_mute_session_icon, mute_session)
    _draw_icon_rotated(image, boxes[1], draw_battery_icon, battery_level)
    _draw_icon_rotated(image, boxes[2], draw_connection_icon, connection == "success")


# Shared display state (used by request handler)
_epd = None
_image = None
_last_state = None
_display_lock = threading.Lock()


def _apply_state(state):
    """Update display if state changed. Call with display_state_from_status(result). Holds _display_lock."""
    global _last_state
    if state == _last_state:
        return
    _epd.init()
    render_display(_image, state)
    _epd.display(_epd.getbuffer(_image))
    _epd.sleep()
    _last_state = state


def _apply_state_background(state):
    """Run _apply_state in a daemon thread so the HTTP handler can return immediately."""
    def run():
        with _display_lock:
            _apply_state(state)
    t = threading.Thread(target=run, daemon=True)
    t.start()


class UpdateHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/update":
            self.send_response(404)
            self.end_headers()
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            status = json.loads(body) if body else None
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        state = display_state_from_status(status)
        _apply_state_background(state)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}\n')

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # quiet by default; set to super().log_message to enable


def main():
    global _epd, _image
    _epd = epd2in13_V4.EPD()
    _epd.init()
    _image = Image.new("1", (EPD_W, EPD_H), 255)
    server = HTTPServer((EPD_LISTEN_HOST, EPD_LISTEN_PORT), UpdateHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
