#!/usr/bin/env python3
"""
Standalone script for Waveshare 13.3" e-Paper HAT+ (E) on Raspberry Pi 5.
Run from repo root. No extra installs; uses same deps as the demo.

  python3 display_photo.py              -> start webserver (Web UI + API)
  python3 display_photo.py <image_url>  -> fetch from URL and display
  python3 display_photo.py --clear      -> clear screen (CLI)

  API (when server is running):
    GET  /api/status
    POST /api/preview/source
    POST /api/preview/transform
    GET  /api/preview/image
    POST /api/display
    POST /api/clear
"""

import io
import ipaddress
import json
import os
import re
import socket
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# Run from repo root: lib is python/lib
_THIS_DIR = os.path.dirname(os.path.realpath(__file__))
_LIB_DIR = os.path.join(_THIS_DIR, "python", "lib")
if os.path.exists(_LIB_DIR):
    sys.path.insert(0, _LIB_DIR)

import epd13in3E
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

EPD_WIDTH = 1200
EPD_HEIGHT = 1600
DISPLAY_ASPECT = EPD_WIDTH / EPD_HEIGHT

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_FORM_BYTES = 256 * 1024
MAX_FETCH_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
FETCH_TIMEOUT_SECONDS = 30
ALLOWED_ROTATIONS = {0, 90, 180, 270}
ALLOWED_ORIENTATIONS = {"portrait", "landscape"}
PREVIEW_MAX_WIDTH = 1000
PREVIEW_MAX_HEIGHT = 1000

ALLOW_PRIVATE_URLS = os.environ.get("EPAPER_ALLOW_PRIVATE_URLS", "").lower() in (
    "1",
    "true",
    "yes",
)

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

# One EPD instance, init on first use
_epd = None


@dataclass
class PreviewState:
    rotation: int = 0
    crop: float = 1.0
    fill: bool = False
    orientation: str = "landscape"


_preview_lock = threading.Lock()
_preview_source = None
_preview_state = PreviewState()
_preview_display = None
_preview_png = None
_preview_version = 0


def parse_content_length(raw_value):
    if raw_value in (None, ""):
        return 0
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as e:
        raise ValueError("Invalid Content-Length header") from e
    if value < 0:
        raise ValueError("Invalid Content-Length header")
    return value


def read_limited_body(rfile, content_length, max_bytes):
    if content_length > max_bytes:
        raise ValueError("Request body is too large")
    remaining = content_length
    chunks = []
    while remaining > 0:
        chunk = rfile.read(min(65536, remaining))
        if not chunk:
            raise ValueError("Unexpected end of request body")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def parse_rotation(value):
    try:
        rotation = int(value or 0) % 360
    except (TypeError, ValueError):
        return 0
    return rotation if rotation in ALLOWED_ROTATIONS else 0


def parse_crop(value):
    try:
        crop = float(value or "1")
    except (TypeError, ValueError):
        crop = 1.0
    return max(0.25, min(1.0, crop))


def parse_font_size(value):
    try:
        size = int(value or "72")
    except (TypeError, ValueError):
        size = 72
    return max(12, min(200, size))


def parse_orientation(value):
    s = str(value or "").strip().lower()
    return s if s in ALLOWED_ORIENTATIONS else "landscape"


def is_truthy(value):
    return str(value or "").strip().lower() in ("1", "on", "true", "yes")


def _blocked_ip(ip_text):
    ip = ipaddress.ip_address(ip_text)
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if not ALLOW_PRIVATE_URLS and ip.is_private:
        return True
    return False


def validate_remote_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are supported")
    if not parsed.hostname:
        raise ValueError("URL must include a host")
    if parsed.username or parsed.password:
        raise ValueError("URL auth credentials are not supported")

    try:
        infos = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as e:
        raise ValueError("Could not resolve URL host") from e

    for info in infos:
        ip_text = info[4][0]
        if _blocked_ip(ip_text):
            raise ValueError("URL host must resolve to a public IP address")


def get_epd():
    global _epd
    if _epd is None:
        _epd = epd13in3E.EPD()
        _epd.Init()
    return _epd


def fetch_image(url):
    import urllib.request

    validate_remote_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "e-Paper/2.0"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as response:
        header_len = response.headers.get("Content-Length")
        if header_len:
            try:
                declared_len = int(header_len)
            except ValueError as e:
                raise ValueError("Invalid response Content-Length") from e
            if declared_len > MAX_FETCH_BYTES:
                raise ValueError("Remote image is too large")

        chunks = []
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FETCH_BYTES:
                raise ValueError("Remote image is too large")
            chunks.append(chunk)
        return b"".join(chunks)


def load_image_from_bytes(data):
    if not data:
        raise ValueError("No image data provided")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image is too large")
        image.load()
    except UnidentifiedImageError as e:
        raise ValueError("Invalid image format") from e
    except (Image.DecompressionBombError, OSError) as e:
        raise ValueError("Image file is invalid or too large") from e
    return image


def apply_transform(image, rotation=0, crop=1.0, fill=False):
    """Apply rotation (degrees CW), then center crop or fill crop to display ratio."""
    if rotation and rotation % 360 != 0:
        image = image.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)

    w, h = image.size
    if fill:
        if w / h > DISPLAY_ASPECT:
            ch, cw = h, max(1, int(h * DISPLAY_ASPECT))
        else:
            cw, ch = w, max(1, int(w / DISPLAY_ASPECT))
        left = (w - cw) // 2
        top = (h - ch) // 2
        image = image.crop((left, top, left + cw, top + ch))
    elif 0 < crop < 1.0:
        cw = max(1, int(w * crop))
        ch = max(1, int(h * crop))
        left = (w - cw) // 2
        top = (h - ch) // 2
        image = image.crop((left, top, left + cw, top + ch))

    return image


def format_for_display(image):
    if image.mode != "RGB":
        image = image.convert("RGB")
    w, h = image.size
    scale = min(EPD_WIDTH / w, EPD_HEIGHT / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), (255, 255, 255))
    canvas.paste(image, ((EPD_WIDTH - new_w) // 2, (EPD_HEIGHT - new_h) // 2))
    return canvas


def show_image_on_epd(image):
    epd = get_epd()
    formatted = format_for_display(image)
    epd.display(epd.getbuffer(formatted))


def clear_epd():
    get_epd().Clear()


def _text_size(draw, s, font):
    bbox = draw.textbbox((0, 0), s, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def render_text_to_image(text, font_size=72):
    canvas = Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    max_w = EPD_WIDTH - 80

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
        )
    except (OSError, IOError):
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                font_size,
            )
        except (OSError, IOError):
            font = ImageFont.load_default()

    line_height = font_size + font_size // 4
    lines = []
    for para in (text or "").strip().split("\n"):
        words = para.split()
        current = []
        for word in words:
            trial = " ".join(current + [word]) if current else word
            width, _ = _text_size(draw, trial, font)
            if width > max_w and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))

    if not lines:
        lines = [""]

    total_h = len(lines) * line_height
    y = (EPD_HEIGHT - total_h) // 2
    for line in lines:
        line_w, _ = _text_size(draw, line, font)
        x = (EPD_WIDTH - line_w) // 2
        draw.text((x, y), line, fill=(0, 0, 0), font=font)
        y += line_height

    return canvas


def parse_multipart_form(rfile, content_type, content_length):
    """Parse multipart/form-data. Returns (photo_bytes or None, fields_dict)."""
    m = re.search(
        r'boundary=(?:"([^"]+)"|([^;\s]+))',
        content_type,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, {}

    boundary_token = (m.group(1) or m.group(2) or "").strip()
    if not boundary_token:
        return None, {}

    boundary = boundary_token.encode("latin-1")
    if not boundary.startswith(b"--"):
        boundary = b"--" + boundary

    length = parse_content_length(content_length)
    body = read_limited_body(rfile, length, MAX_UPLOAD_BYTES)

    parts = body.split(boundary)
    photo = None
    fields = {}

    for part in parts:
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue

        head, _, payload = part.partition(b"\r\n\r\n")
        payload = payload.rstrip(b"\r\n")

        name_m = re.search(rb'name=["\']([^"\']+)["\']', head)
        if not name_m:
            continue

        name = name_m.group(1).decode("latin-1")
        if name == "photo" and (b"filename=" in head or len(payload) > 0):
            photo = payload
        else:
            fields[name] = payload.decode("utf-8", errors="replace").strip()

    return photo, fields


def _encode_preview_png(image):
    to_show = image
    if to_show.width > PREVIEW_MAX_WIDTH or to_show.height > PREVIEW_MAX_HEIGHT:
        scale = min(PREVIEW_MAX_WIDTH / to_show.width, PREVIEW_MAX_HEIGHT / to_show.height)
        to_show = to_show.resize(
            (max(1, int(to_show.width * scale)), max(1, int(to_show.height * scale))),
            Image.Resampling.LANCZOS,
        )

    buf = io.BytesIO()
    to_show.save(buf, format="PNG")
    return buf.getvalue(), to_show.width, to_show.height


def _rebuild_preview_locked():
    global _preview_display, _preview_png, _preview_version

    transformed = apply_transform(
        _preview_source,
        rotation=_preview_state.rotation,
        crop=_preview_state.crop,
        fill=_preview_state.fill,
    )
    display_image = format_for_display(transformed)

    if _preview_state.orientation == "landscape":
        ui_image = display_image.rotate(90, expand=True)
    else:
        ui_image = display_image

    png, width, height = _encode_preview_png(ui_image)

    _preview_display = display_image
    _preview_png = png
    _preview_version += 1

    return {
        "rotation": _preview_state.rotation,
        "crop": _preview_state.crop,
        "fill": _preview_state.fill,
        "orientation": _preview_state.orientation,
        "preview_width": width,
        "preview_height": height,
        "preview_url": f"/api/preview/image?v={_preview_version}",
        "version": _preview_version,
    }


def set_preview_source(image, orientation="landscape"):
    global _preview_source, _preview_state
    with _preview_lock:
        _preview_source = image.convert("RGB")
        _preview_state = PreviewState(orientation=parse_orientation(orientation))
        return _rebuild_preview_locked()


def update_preview_state(rotation=None, crop=None, fill=None, orientation=None):
    with _preview_lock:
        if _preview_source is None:
            raise ValueError("No preview source loaded")

        if rotation is not None:
            _preview_state.rotation = parse_rotation(rotation)
        if crop is not None:
            _preview_state.crop = parse_crop(crop)
        if fill is not None:
            _preview_state.fill = bool(fill)
        if orientation is not None:
            _preview_state.orientation = parse_orientation(orientation)

        return _rebuild_preview_locked()


def get_preview_png():
    with _preview_lock:
        if _preview_png is None:
            return None
        return _preview_png


def display_preview_buffer():
    with _preview_lock:
        if _preview_display is None:
            raise ValueError("No preview image available")
        image = _preview_display.copy()
    show_image_on_epd(image)


API_DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>API Docs - e-Paper Photo</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 780px; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }
    pre, code { background: #f3f4f6; border-radius: 6px; }
    code { padding: 0.1rem 0.3rem; }
    pre { padding: 0.9rem; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>e-Paper Photo API</h1>
  <p>All responses are JSON except <code>GET /api/preview/image</code>.</p>

  <h2>GET /api/status</h2>
  <pre>curl http://localhost:5000/api/status</pre>

  <h2>POST /api/preview/source</h2>
  <p>Set source image from one of:</p>
  <ul>
    <li>Multipart form with file field <code>photo</code></li>
    <li>JSON: <code>{"mode":"url","url":"https://..."}</code></li>
    <li>JSON: <code>{"mode":"text","text":"hello","font_size":72}</code></li>
  </ul>

  <h2>POST /api/preview/transform</h2>
  <p>Update preview transform:</p>
  <pre>{"rotation":90,"crop":0.85,"fill":false,"orientation":"landscape"}</pre>

  <h2>GET /api/preview/image</h2>
  <p>Returns PNG bytes for current preview buffer.</p>

  <h2>POST /api/display</h2>
  <p>Push current preview buffer to e-paper display.</p>

  <h2>POST /api/clear</h2>
  <p>Clear the e-paper display.</p>

  <p><a href="/">Back to UI</a></p>
</body>
</html>
"""


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>e-Paper Display Control</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --ink: #10233d;
      --muted: #4f637d;
      --border: #d8e1ee;
      --accent: #0f78c8;
      --accent-ink: #ffffff;
      --danger: #b43a2d;
      --ok: #0f7a45;
      --shadow: 0 10px 24px rgba(16, 35, 61, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, #e8f1ff, var(--bg) 55%);
    }
    .wrap { max-width: 1020px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 6px; font-size: 1.9rem; }
    .sub { margin: 0 0 18px; color: var(--muted); }
    .grid { display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      box-shadow: var(--shadow);
    }
    .card h2 { margin: 0 0 10px; font-size: 1.05rem; }
    .stack { display: grid; gap: 10px; }
    .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    input[type="file"], input[type="url"], input[type="number"], textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 11px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 88px; resize: vertical; }
    button {
      border: 1px solid transparent;
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.05s ease, opacity 0.15s ease;
    }
    button:active { transform: translateY(1px); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-primary { background: var(--accent); color: var(--accent-ink); }
    .btn-secondary { background: #eef3fb; color: var(--ink); border-color: var(--border); }
    .btn-danger { background: #fff2f1; color: var(--danger); border-color: #f0cbc7; }
    .btn-ok { background: #eaf8f0; color: var(--ok); border-color: #c6e9d4; }
    .tag {
      display: inline-flex;
      align-items: center;
      font-size: 0.86rem;
      color: var(--muted);
      background: #edf3fb;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 5px 10px;
    }
    .preview-box {
      border: 1px dashed var(--border);
      border-radius: 12px;
      background: linear-gradient(135deg, #f7faff, #eef4ff);
      min-height: 280px;
      display: grid;
      place-items: center;
      padding: 10px;
    }
    #previewImage { max-width: 100%; max-height: 68vh; border-radius: 10px; box-shadow: 0 8px 20px rgba(16, 35, 61, 0.18); }
    #previewEmpty { color: var(--muted); text-align: center; }
    .status {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #f7faff;
      color: var(--muted);
      min-height: 44px;
      display: flex;
      align-items: center;
    }
    .status.ok { background: #eaf8f0; color: var(--ok); border-color: #c6e9d4; }
    .status.err { background: #fff2f1; color: var(--danger); border-color: #f0cbc7; }
    .controls-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .wide { grid-column: 1 / -1; }
    .small { color: var(--muted); font-size: 0.9rem; }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>e-Paper Display Control</h1>
    <p class="sub">Load an image, URL, or text into a preview buffer, tune it, then push to the display.</p>

    <div class="grid">
      <section class="card stack">
        <h2>1) Choose Source</h2>

        <label>Upload file</label>
        <input id="fileInput" type="file" accept="image/*" />
        <button id="loadFileBtn" class="btn-primary">Load File Into Preview</button>

        <label>Or use image URL</label>
        <input id="urlInput" type="url" placeholder="https://example.com/photo.jpg" />
        <button id="loadUrlBtn" class="btn-secondary">Download URL Into Preview</button>

        <label>Or render text</label>
        <textarea id="textInput" placeholder="Type text to render on e-paper"></textarea>
        <div class="row">
          <label for="fontSize">Font size</label>
          <input id="fontSize" type="number" min="12" max="200" value="72" style="width: 90px;" />
          <button id="loadTextBtn" class="btn-secondary">Render Text Into Preview</button>
        </div>

        <div class="status" id="status">Ready.</div>
      </section>

      <section class="card stack">
        <h2>2) Preview & Adjust</h2>

        <div class="row">
          <span class="tag">Frame orientation</span>
          <button id="oriPortraitBtn" class="btn-secondary">Portrait</button>
          <button id="oriLandscapeBtn" class="btn-primary">Landscape</button>
        </div>

        <div class="controls-grid">
          <button id="rotateLeftBtn" class="btn-secondary">Rotate Left 90</button>
          <button id="rotateRightBtn" class="btn-secondary">Rotate Right 90</button>

          <div class="wide">
            <label for="cropSlider">Crop amount: <span id="cropValue">100%</span></label>
            <input id="cropSlider" type="range" min="25" max="100" step="1" value="100" />
            <div class="row" style="margin-top: 8px;">
              <button id="applyCropBtn" class="btn-secondary">Apply Crop</button>
              <button id="fillToggleBtn" class="btn-secondary">Crop To Fill: Off</button>
            </div>
          </div>
        </div>

        <div class="preview-box">
          <img id="previewImage" alt="Preview" style="display:none;" />
          <div id="previewEmpty">No preview loaded yet.</div>
        </div>

        <p class="small">Preview buffer is server-side. "Push To Display" sends exactly this buffered preview to the panel.</p>

        <div class="row">
          <button id="pushBtn" class="btn-ok">Push Preview To Display</button>
          <button id="clearBtn" class="btn-danger">Clear Display</button>
          <a href="/api/docs" class="small">API docs</a>
        </div>
      </section>
    </div>
  </div>

  <script>
    const state = {
      rotation: 0,
      crop: 1,
      fill: false,
      orientation: "landscape",
      hasPreview: false,
      busy: false,
    };

    const el = {
      status: document.getElementById("status"),
      file: document.getElementById("fileInput"),
      url: document.getElementById("urlInput"),
      text: document.getElementById("textInput"),
      fontSize: document.getElementById("fontSize"),
      preview: document.getElementById("previewImage"),
      previewEmpty: document.getElementById("previewEmpty"),
      cropSlider: document.getElementById("cropSlider"),
      cropValue: document.getElementById("cropValue"),
      fillToggle: document.getElementById("fillToggleBtn"),
      oriPortrait: document.getElementById("oriPortraitBtn"),
      oriLandscape: document.getElementById("oriLandscapeBtn"),
      buttons: Array.from(document.querySelectorAll("button")),
    };

    function setBusy(busy) {
      state.busy = busy;
      for (const button of el.buttons) button.disabled = busy;
    }

    function setStatus(message, kind = "") {
      el.status.textContent = message;
      el.status.className = "status" + (kind ? " " + kind : "");
    }

    async function requestJSON(url, options = {}, cfg = {}) {
      const retries = cfg.retries ?? 1;
      const timeoutMs = cfg.timeoutMs ?? 35000;

      for (let attempt = 0; attempt <= retries; attempt += 1) {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), timeoutMs);
        try {
          const response = await fetch(url, { ...options, signal: ctl.signal });
          clearTimeout(timer);

          let payload = null;
          const ct = response.headers.get("content-type") || "";
          if (ct.includes("application/json")) {
            payload = await response.json();
          } else {
            const text = await response.text();
            payload = { ok: false, error: text || "Unexpected response" };
          }

          if (!response.ok || !payload || payload.ok === false) {
            throw new Error((payload && payload.error) || `Request failed (${response.status})`);
          }
          return payload;
        } catch (err) {
          clearTimeout(timer);
          const retryable = err.name === "AbortError" || err instanceof TypeError;
          if (!retryable || attempt >= retries) throw err;
        }
      }
      throw new Error("Request failed");
    }

    function syncUiFromState() {
      const pct = Math.round(state.crop * 100);
      el.cropSlider.value = String(pct);
      el.cropValue.textContent = `${pct}%`;
      el.fillToggle.textContent = `Crop To Fill: ${state.fill ? "On" : "Off"}`;

      if (state.orientation === "portrait") {
        el.oriPortrait.className = "btn-primary";
        el.oriLandscape.className = "btn-secondary";
      } else {
        el.oriPortrait.className = "btn-secondary";
        el.oriLandscape.className = "btn-primary";
      }
    }

    function setPreviewImage(url) {
      if (!url) return;
      el.preview.src = url;
      el.preview.style.display = "block";
      el.previewEmpty.style.display = "none";
      state.hasPreview = true;
    }

    function applyResponse(payload) {
      state.rotation = payload.state.rotation;
      state.crop = payload.state.crop;
      state.fill = payload.state.fill;
      state.orientation = payload.state.orientation;
      syncUiFromState();
      setPreviewImage(payload.state.preview_url + `&cb=${Date.now()}`);
    }

    async function loadFileSource() {
      const file = el.file.files && el.file.files[0];
      if (!file) {
        setStatus("Choose a file first.", "err");
        return;
      }

      const form = new FormData();
      form.append("photo", file);
      form.append("orientation", state.orientation);

      setBusy(true);
      setStatus("Uploading file and generating preview...");
      try {
        const payload = await requestJSON("/api/preview/source", { method: "POST", body: form });
        applyResponse(payload);
        setStatus("Preview loaded from file.", "ok");
      } catch (err) {
        setStatus(err.message || "Failed to load file preview.", "err");
      } finally {
        setBusy(false);
      }
    }

    async function loadUrlSource() {
      const url = (el.url.value || "").trim();
      if (!url) {
        setStatus("Enter a URL first.", "err");
        return;
      }

      setBusy(true);
      setStatus("Downloading image URL and generating preview...");
      try {
        const payload = await requestJSON("/api/preview/source", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "url", url, orientation: state.orientation }),
        });
        applyResponse(payload);
        setStatus("Preview loaded from URL.", "ok");
      } catch (err) {
        setStatus(err.message || "Failed to load URL preview.", "err");
      } finally {
        setBusy(false);
      }
    }

    async function loadTextSource() {
      const text = (el.text.value || "").trim();
      if (!text) {
        setStatus("Enter text first.", "err");
        return;
      }

      const fontSize = Math.max(12, Math.min(200, Number(el.fontSize.value) || 72));

      setBusy(true);
      setStatus("Rendering text and generating preview...");
      try {
        const payload = await requestJSON("/api/preview/source", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: "text",
            text,
            font_size: fontSize,
            orientation: state.orientation,
          }),
        });
        applyResponse(payload);
        setStatus("Preview loaded from text.", "ok");
      } catch (err) {
        setStatus(err.message || "Failed to render text preview.", "err");
      } finally {
        setBusy(false);
      }
    }

    async function updateTransform(changes, message) {
      if (!state.hasPreview) {
        setStatus("Load a source first.", "err");
        return;
      }

      setBusy(true);
      setStatus(message || "Updating preview...");
      try {
        const payload = await requestJSON("/api/preview/transform", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(changes),
        });
        applyResponse(payload);
        setStatus("Preview updated.", "ok");
      } catch (err) {
        setStatus(err.message || "Failed to update preview.", "err");
      } finally {
        setBusy(false);
      }
    }

    async function pushPreviewToDisplay() {
      if (!state.hasPreview) {
        setStatus("Load a source first.", "err");
        return;
      }

      setBusy(true);
      setStatus("Pushing preview buffer to e-paper display (~19s)...");
      try {
        await requestJSON("/api/display", { method: "POST" }, { timeoutMs: 90000, retries: 0 });
        setStatus("Display update started.", "ok");
      } catch (err) {
        setStatus(err.message || "Failed to push preview to display.", "err");
      } finally {
        setBusy(false);
      }
    }

    async function clearDisplay() {
      setBusy(true);
      setStatus("Clearing display...");
      try {
        await requestJSON("/api/clear", { method: "POST" }, { timeoutMs: 90000, retries: 0 });
        setStatus("Display cleared.", "ok");
      } catch (err) {
        setStatus(err.message || "Failed to clear display.", "err");
      } finally {
        setBusy(false);
      }
    }

    document.getElementById("loadFileBtn").addEventListener("click", loadFileSource);
    document.getElementById("loadUrlBtn").addEventListener("click", loadUrlSource);
    document.getElementById("loadTextBtn").addEventListener("click", loadTextSource);

    document.getElementById("oriPortraitBtn").addEventListener("click", () => {
      state.orientation = "portrait";
      syncUiFromState();
      updateTransform({ orientation: "portrait" }, "Switching to portrait preview...");
    });

    document.getElementById("oriLandscapeBtn").addEventListener("click", () => {
      state.orientation = "landscape";
      syncUiFromState();
      updateTransform({ orientation: "landscape" }, "Switching to landscape preview...");
    });

    document.getElementById("rotateLeftBtn").addEventListener("click", () => {
      const next = (state.rotation + 270) % 360;
      updateTransform({ rotation: next }, "Rotating preview...");
    });

    document.getElementById("rotateRightBtn").addEventListener("click", () => {
      const next = (state.rotation + 90) % 360;
      updateTransform({ rotation: next }, "Rotating preview...");
    });

    el.cropSlider.addEventListener("input", () => {
      el.cropValue.textContent = `${el.cropSlider.value}%`;
    });

    document.getElementById("applyCropBtn").addEventListener("click", () => {
      updateTransform({ crop: Number(el.cropSlider.value) / 100 }, "Applying crop...");
    });

    document.getElementById("fillToggleBtn").addEventListener("click", () => {
      updateTransform({ fill: !state.fill }, "Toggling fill crop...");
    });

    document.getElementById("pushBtn").addEventListener("click", pushPreviewToDisplay);
    document.getElementById("clearBtn").addEventListener("click", clearDisplay);

    syncUiFromState();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _path_only(self):
        return self.path.split("?", 1)[0]

    def _send_json(self, status, body):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self, max_bytes=MAX_FORM_BYTES):
        length = parse_content_length(self.headers.get("Content-length", "0"))
        body = read_limited_body(self.rfile, length, max_bytes) if length else b""
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8", errors="strict"))
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON body") from e

    def do_GET(self):
        path = self._path_only()
        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if path == "/api/docs":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(API_DOCS_HTML.encode("utf-8"))
            return

        if path == "/api/status":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "epaper",
                    "display": {"width": EPD_WIDTH, "height": EPD_HEIGHT},
                    "limits": {
                        "max_upload_bytes": MAX_UPLOAD_BYTES,
                        "max_fetch_bytes": MAX_FETCH_BYTES,
                        "max_form_bytes": MAX_FORM_BYTES,
                        "max_image_pixels": MAX_IMAGE_PIXELS,
                    },
                    "allow_private_urls": ALLOW_PRIVATE_URLS,
                    "has_preview": get_preview_png() is not None,
                },
            )
            return

        if path == "/api/preview/image":
            png = get_preview_png()
            if not png:
                self.send_error(404, "No preview available")
                return
            self.send_response(200)
            self.send_header("Content-type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)
            return

        self.send_error(404)

    def do_POST(self):
        path = self._path_only()

        try:
            if path == "/api/preview/source":
                self._api_preview_source()
                return
            if path == "/api/preview/transform":
                self._api_preview_transform()
                return
            if path == "/api/display":
                self._api_display()
                return
            if path == "/api/clear":
                self._api_clear()
                return
        except ValueError as e:
            self._send_json(400, {"ok": False, "error": str(e)})
            return
        except Exception as e:
            print("Unhandled POST error:", e)
            self._send_json(500, {"ok": False, "error": str(e)})
            return

        self.send_error(404)

    def _api_preview_source(self):
        content_type = self.headers.get("Content-type", "")
        orientation = "landscape"

        if content_type.startswith("multipart/form-data"):
            data, form = parse_multipart_form(
                self.rfile,
                content_type,
                self.headers.get("Content-length", "0"),
            )
            if not data:
                raise ValueError("Multipart upload must include field 'photo'")
            orientation = parse_orientation(form.get("orientation"))
            image = load_image_from_bytes(data)
        else:
            payload = self._read_json()
            mode = str(payload.get("mode", "")).strip().lower()
            orientation = parse_orientation(payload.get("orientation"))

            if mode == "url":
                url = str(payload.get("url", "")).strip()
                if not url:
                    raise ValueError("Missing url")
                image = load_image_from_bytes(fetch_image(url))
            elif mode == "text":
                text = str(payload.get("text", ""))
                if not text.strip():
                    raise ValueError("Missing text")
                font_size = parse_font_size(payload.get("font_size"))
                image = render_text_to_image(text.strip(), font_size=font_size)
            else:
                raise ValueError("Invalid source mode. Use multipart file or JSON mode=url|text")

        state = set_preview_source(image, orientation=orientation)
        self._send_json(200, {"ok": True, "state": state})

    def _api_preview_transform(self):
        payload = self._read_json()

        rotation = payload.get("rotation") if "rotation" in payload else None
        crop = payload.get("crop") if "crop" in payload else None
        fill = payload.get("fill") if "fill" in payload else None
        orientation = payload.get("orientation") if "orientation" in payload else None

        if fill is not None:
            fill = fill if isinstance(fill, bool) else is_truthy(fill)

        state = update_preview_state(
            rotation=rotation,
            crop=crop,
            fill=fill,
            orientation=orientation,
        )
        self._send_json(200, {"ok": True, "state": state})

    def _api_display(self):
        display_preview_buffer()
        self._send_json(200, {"ok": True, "message": "Display updating (~19s)"})

    def _api_clear(self):
        clear_epd()
        self._send_json(200, {"ok": True, "message": "Screen cleared"})


def run_server():
    port = 5000
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("e-Paper photo server: http://localhost:%s" % port)
    print("  UI: source -> preview buffer -> display")
    print("  API: /api/preview/source, /api/preview/transform, /api/preview/image, /api/display, /api/clear")
    print("  From another device: http://<pi-ip>:%s" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)


def main():
    if len(sys.argv) >= 2:
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
        image = load_image_from_bytes(data)
        print("Displaying (refresh ~19s)...")
        show_image_on_epd(image)
        get_epd().sleep()
        print("Done.")
        return

    run_server()


if __name__ == "__main__":
    main()
