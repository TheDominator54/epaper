#!/usr/bin/env python3
"""
Standalone script for Waveshare 13.3" e-Paper HAT+ (E) on Raspberry Pi 5.
Run from repo root. No extra installs; uses same deps as the demo.

  python3 display_photo.py              → start webserver (Web UI + API)
  python3 display_photo.py <image_url>  → fetch from URL and display
  python3 display_photo.py --clear       → clear screen (CLI)

  API (when server is running):
    POST /api/upload  → body: multipart form field "photo" or raw image (Content-Type: image/...). Returns JSON.
    POST /api/clear   → clear screen. Returns JSON.
    GET /api/status   → health + current limits. Returns JSON.
"""
import io
import ipaddress
import json
import os
import re
import socket
import sys
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Run from repo root: lib is python/lib
_this_dir = os.path.dirname(os.path.realpath(__file__))
_libdir = os.path.join(_this_dir, "python", "lib")
if os.path.exists(_libdir):
    sys.path.insert(0, _libdir)

import epd13in3E
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

EPD_WIDTH = 1200
EPD_HEIGHT = 1600
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_FORM_BYTES = 256 * 1024
MAX_FETCH_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
FETCH_TIMEOUT_SECONDS = 30
ALLOWED_ROTATIONS = {0, 90, 180, 270}
ALLOW_PRIVATE_URLS = os.environ.get("EPAPER_ALLOW_PRIVATE_URLS", "").lower() in ("1", "true", "yes")

# One EPD instance, init on first use
_epd = None

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def parse_content_length(raw_value):
    if raw_value in (None, ""):
        return 0
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError("Invalid Content-Length header")
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
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError("Could not resolve URL host") from e
    for info in infos:
        ip_text = info[4][0]
        if _blocked_ip(ip_text):
            if ALLOW_PRIVATE_URLS:
                raise ValueError("URL host resolved to a blocked local address")
            raise ValueError("URL host must resolve to a public IP address")


def load_image_from_bytes(data):
    if not data:
        raise ValueError("No image data provided")
    try:
        image = Image.open(io.BytesIO(data))
        if (image.width * image.height) > MAX_IMAGE_PIXELS:
            raise ValueError("Image is too large")
        image.load()
    except UnidentifiedImageError as e:
        raise ValueError("Invalid image format") from e
    except ValueError:
        raise
    except (Image.DecompressionBombError, OSError) as e:
        raise ValueError("Image file is invalid or too large") from e
    return image


def sniff_image_content_type(data):
    image = load_image_from_bytes(data)
    fmt = (image.format or "JPEG").upper()
    if fmt in ("JPEG", "JPG"):
        return "image/jpeg"
    if fmt == "PNG":
        return "image/png"
    if fmt == "GIF":
        return "image/gif"
    if fmt == "WEBP":
        return "image/webp"
    return "image/jpeg"


def get_epd():
    global _epd
    if _epd is None:
        _epd = epd13in3E.EPD()
        _epd.Init()
    return _epd


def fetch_image(url):
    import urllib.request
    validate_remote_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "e-Paper/1.0"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as r:
        header_len = r.headers.get("Content-Length")
        if header_len:
            try:
                declared_len = int(header_len)
            except ValueError:
                raise ValueError("Invalid response Content-Length")
            if declared_len > MAX_FETCH_BYTES:
                raise ValueError("Remote image is too large")
        chunks = []
        total = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FETCH_BYTES:
                raise ValueError("Remote image is too large")
            chunks.append(chunk)
        return b"".join(chunks)


DISPLAY_ASPECT = EPD_WIDTH / EPD_HEIGHT  # 1200/1600 = 0.75 (portrait)


def apply_transform(image, rotation=0, crop=1.0, fill=False):
    """Apply rotation (degrees CW), then center crop (1.0 = no crop) or fill (crop to 3:4 to fill display)."""
    if rotation and rotation % 360 != 0:
        image = image.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
    w, h = image.size
    if fill:
        # Crop to display aspect (3:4) from center so image fills the screen
        if w / h > DISPLAY_ASPECT:
            ch, cw = h, max(1, int(h * DISPLAY_ASPECT))
        else:
            cw, ch = w, max(1, int(w / DISPLAY_ASPECT))
        left = (w - cw) // 2
        top = (h - ch) // 2
        image = image.crop((left, top, left + cw, top + ch))
    elif crop < 1.0 and crop > 0:
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
    new_w = int(w * scale)
    new_h = int(h * scale)
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
    """Draw text wrapped and centered on a 1200x1600 white image. Returns RGB Image."""
    canvas = Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    max_w = EPD_WIDTH - 80
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()
    line_height = font_size + font_size // 4
    lines = []
    for para in (text or "").strip().split("\n"):
        words = para.split()
        current = []
        for word in words:
            trial = " ".join(current + [word]) if current else word
            w, _ = _text_size(draw, trial, font)
            if w > max_w and current:
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
    m = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))', content_type, flags=re.IGNORECASE)
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
        # Get name from Content-Disposition: form-data; name="..."
        name_m = re.search(rb'name=["\']([^"\']+)["\']', head)
        if not name_m:
            continue
        name = name_m.group(1).decode("latin-1")
        if name == "photo" and (b"filename=" in head or len(payload) > 0):
            photo = payload
        else:
            # Text field: payload can contain trailing \\r\\n and next boundary (e.g. 270\\r\\n--)
            val = payload.decode("utf-8", errors="replace").strip()
            if "\r\n" in val:
                val = val.split("\r\n")[0].strip()
            if "\n" in val:
                val = val.split("\n")[0].strip()
            # Drop any trailing boundary fragment (e.g. "--" or "--boundary")
            val = val.split("--")[0].strip()
            fields[name] = val
    return photo, fields


API_DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>API Docs – e-Paper Photo</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; background: #1a1a1a; color: #e0e0e0; line-height: 1.5; }
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.1rem; margin-top: 1.5rem; color: #aaa; }
    p, li { color: #ccc; }
    code { background: #333; padding: 0.15em 0.4em; border-radius: 4px; font-size: 0.9em; }
    pre { background: #252525; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.85rem; }
    .method { color: #7af; }
    .path { color: #afa; }
    table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; }
    th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #333; }
    th { color: #888; font-weight: 600; }
    a { color: #7af; }
  </style>
</head>
<body>
  <h1>e-Paper Photo API</h1>
  <p>JSON responses use <code>{"ok": true|false, "message"?: "...", "error"?: "..."}</code>.</p>

  <h2>POST /api/upload</h2>
  <p>Display an image on the e-paper. Refresh takes ~19s.</p>
  <p><strong>Request:</strong></p>
  <ul>
    <li><strong>Multipart form:</strong> <code>photo</code> (file, required). Optional: <code>rotation</code> (0|90|180|270), <code>crop</code> (0.25–1.0, center crop %), <code>fill</code> (1|on|true to crop to 3:4 and fill screen).</li>
    <li><strong>Raw image:</strong> Body = image bytes, <code>Content-Type: image/jpeg</code> (or image/png, etc.). No form fields in this case.</li>
    <li><strong>Limits:</strong> upload body max 12MB; image must be a valid raster format.</li>
  </ul>
  <p><strong>Example (curl, multipart):</strong></p>
  <pre>curl -X POST -F "photo=@/path/to/image.jpg" -F "rotation=90" -F "crop=0.8" -F "fill=0" http://localhost:5000/api/upload</pre>
  <p><strong>Example (curl, raw image):</strong></p>
  <pre>curl -X POST -H "Content-Type: image/jpeg" --data-binary @image.jpg http://localhost:5000/api/upload</pre>
  <p><strong>Success:</strong> <code>200 {"ok": true, "message": "Display updating (~19s)"}</code></p>
  <p><strong>Error:</strong> <code>400</code> or <code>500</code> with <code>{"ok": false, "error": "..."}</code></p>

  <h2>POST /api/clear</h2>
  <p>Clear the e-paper display.</p>
  <p><strong>Request:</strong> No body.</p>
  <p><strong>Example:</strong></p>
  <pre>curl -X POST http://localhost:5000/api/clear</pre>
  <p><strong>Success:</strong> <code>200 {"ok": true, "message": "Screen cleared"}</code></p>

  <h2>GET /api/status</h2>
  <p>Check service health and current limits.</p>
  <p><strong>Example:</strong></p>
  <pre>curl http://localhost:5000/api/status</pre>
  <p><strong>Success:</strong> <code>200 {"ok": true, "service": "epaper", ...}</code></p>

  <h2>POST /display_text</h2>
  <p>Display text on the e-paper (wrapped and centered). Web UI uses this for the text source.</p>
  <p><strong>Request:</strong> <code>application/x-www-form-urlencoded</code> with <code>text</code> (required) and optional <code>font_size</code> (default 72, range 12–200).</p>
  <p><strong>Example:</strong></p>
  <pre>curl -X POST -d "text=Hello%20world" -d "font_size=72" http://localhost:5000/display_text</pre>
  <p>Redirects to <code>/?display=ok</code> or <code>/?display=err</code>.</p>

  <h2>GET /preview?url=...</h2>
  <p>Proxy an image from a URL. Use to load an image in the browser for preview.</p>
  <p><strong>Query:</strong></p>
  <table>
    <tr><th>Param</th><th>Description</th></tr>
    <tr><td><code>url</code></td><td>Image URL (required, encoded).</td></tr>
  </table>
  <p><strong>Example:</strong></p>
  <pre>GET /preview?url=https%3A%2F%2Fexample.com%2Fphoto.jpg</pre>
  <p>Returns the image bytes with appropriate <code>Content-Type</code>. Only <code>http/https</code> URLs are accepted.</p>

  <p style="margin-top: 2rem;"><a href="/">← Back to Web UI</a></p>
</body>
</html>
"""


HTML_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>e-Paper Photo Display</title>
<style>
*{box-sizing:border-box;}
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:480px;margin:0 auto;padding:1.5rem 1.25rem;background:#0d0d0d;color:#e8e8e8;line-height:1.5;font-size:15px;}
h1{font-size:1.5rem;font-weight:600;margin:0 0 0.5rem;letter-spacing:-0.02em;}
.subtitle{color:#888;font-size:0.9rem;margin-bottom:1.5rem;}
.card{background:#161616;border:1px solid #252525;border-radius:10px;padding:1.15rem;margin-bottom:1.25rem;}
.card-title{font-size:0.8rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#888;margin-bottom:0.6rem;}
label{font-size:0.85rem;color:#999;display:block;margin-bottom:0.35rem;}
input[type="file"],input[type="url"],input[type="number"],textarea{width:100%;padding:0.65rem 0.75rem;margin:0.25rem 0;background:#222;border:1px solid #333;border-radius:8px;color:#e0e0e0;font-size:1rem;}
input:focus,textarea:focus{outline:none;border-color:#0a7ea4;}
input[type="url"]::placeholder,textarea::placeholder{color:#555;}
input[type="range"]{width:100%;height:6px;margin:0.4rem 0;accent-color:#0a7ea4;}
button{padding:0.6rem 1rem;border-radius:8px;font-size:0.95rem;font-weight:500;cursor:pointer;border:none;transition:opacity 0.15s,background 0.15s;}
button:hover:not(:disabled){opacity:0.92;}
button:disabled{opacity:0.5;cursor:not-allowed;}
.btn-primary{background:#0a7ea4;color:#fff;}
.btn-secondary{background:#2a2a2a;color:#ddd;border:1px solid #3a3a3a;}
.btn-ori{padding:0.5rem 1rem;font-size:0.9rem;background:#252525;color:#aaa;border:1px solid #353535;}
.btn-ori.active{background:#0a7ea4;color:#fff;border-color:#0a7ea4;}
.orientation-row{display:flex;gap:0.5rem;margin-top:0.35rem;}
.source-row{display:flex;flex-wrap:wrap;align-items:center;gap:0.6rem;margin-top:0.5rem;}
.source-row input[type="file"]{flex:0 0 auto;max-width:100%;}
.source-row input[type="url"]{flex:1;min-width:140px;}
.source-row .divider{color:#555;font-size:0.85rem;}
.text-row{display:flex;align-items:center;gap:0.6rem;margin-top:0.6rem;}
#fontSize{width:4.5em;}
.controls{background:#1c1c1c;border-radius:8px;padding:1rem;margin:1rem 0;}
.controls .row{display:flex;align-items:center;gap:0.5rem;margin:0.4rem 0;}
#preview{max-width:100%;display:block;margin:0.75rem 0;border-radius:8px;background:#1a1a1a;box-shadow:0 2px 8px rgba(0,0,0,0.3);}
.preview-wrap{display:none;margin-top:1rem;}
.preview-wrap.show{display:block;}
.preview-caption{font-size:0.8rem;color:#666;margin-bottom:0.5rem;}
#displayBtn{margin-top:1rem;width:100%;padding:0.75rem;font-size:1rem;}
.actions{margin-top:1.25rem;display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;}
.footer{margin-top:1.5rem;padding-top:1rem;border-top:1px solid #222;font-size:0.8rem;color:#666;}
.footer a{color:#5a9bb8;}
.msg{padding:0.75rem 1rem;border-radius:8px;font-size:0.9rem;margin-top:1rem;display:none;}
.msg.show{display:block;}
.msg.ok{background:rgba(40,80,40,0.4);color:#9c9;}
.msg.err{background:rgba(80,40,40,0.4);color:#c99;}
</style></head><body>
<header>
  <h1>e-Paper Photo Display</h1>
  <p class="subtitle">Send images or text to your 13.3\u201d display</p>
</header>

<div class="card">
  <div class="card-title">Preview orientation</div>
  <div class="orientation-row">
    <button type="button" id="oriPortrait" class="btn-ori" onclick="epaperOrientation(\u0027portrait\u0027)">Portrait</button>
    <button type="button" id="oriLandscape" class="btn-ori active" onclick="epaperOrientation(\u0027landscape\u0027)">Landscape</button>
  </div>
  <p class="preview-caption">Portrait = tall; Landscape = wide.</p>
</div>

<div class="card">
  <div class="card-title">Image (file or URL)</div>
  <div class="source-row">
    <input type="file" id="fileIn" accept="image/*">
    <span class="divider">or</span>
    <input type="url" id="urlIn" placeholder="Paste image URL">
    <button type="button" id="loadBtn" class="btn-primary" onclick="epaperLoadImage()">Load image</button>
  </div>
</div>

<div class="card">
  <div class="card-title">Or type text</div>
  <textarea id="textIn" placeholder="Type your message here..." rows="3"></textarea>
  <div class="text-row">
    <label>Font size</label>
    <input type="number" id="fontSize" min="24" max="200" value="72">
    <button type="button" id="loadTextBtn" class="btn-primary" onclick="epaperLoadText()">Load text</button>
  </div>
</div>

<div class="preview-wrap" id="previewWrap">
  <div class="card">
    <div class="card-title">Preview &amp; adjust</div>
    <p class="preview-caption">Display 1200\u00d71600.</p>
    <canvas id="preview" width="400" height="300"></canvas>
    <div class="controls">
      <div class="row"><label>Rotate</label><button type="button" id="rotL" class="btn-secondary" onclick="epaperRotate(-90)">\u21b6 Left</button><button type="button" id="rotR" class="btn-secondary" onclick="epaperRotate(90)">Right \u21b7</button></div>
      <label>Crop in: <span id="cropPct">100</span>%</label>
      <input type="range" id="cropSl" min="25" max="100" value="100" step="5" oninput="epaperCrop(this.value)">
      <div class="row"><button type="button" id="fillBtn" class="btn-secondary" onclick="epaperFill()">Crop to fill screen</button></div>
    </div>
    <button type="button" id="displayBtn" class="btn-primary" disabled onclick="epaperDisplay()">Display on e-paper</button>
  </div>
</div>

<div class="actions">
  <form method="post" action="/clear" style="display:inline;">
    <button type="submit" class="btn-secondary">Clear screen</button>
  </form>
</div>

<div class="footer">
  Display refresh takes about 19 seconds. <a href="/api/docs">API docs</a>
</div>
<div id="msg" class="msg"></div>
<script>
console.log("[epaper] script start");
(function(){
  var q = new URLSearchParams(location.search);
  var m = document.getElementById("msg");
  if (!m) return;
  if (q.get("display") === "ok") { m.className = "msg ok show"; m.textContent = "Display updating. Refresh takes ~19s."; }
  if (q.get("display") === "err") { m.className = "msg err show"; m.textContent = "Display failed. Check the image or try again."; }
  if (q.get("clear") === "ok") { m.className = "msg ok show"; m.textContent = "Screen cleared."; }
  if (q.get("clear") === "err") { m.className = "msg err show"; m.textContent = "Clear failed."; }
})();
var DISP_W = 1200, DISP_H = 1600, ASPECT = DISP_W / DISP_H;
var rot = 0, crop = 1, fillMode = false, imgEl = null, currentFile = null, currentUrl = null, currentText = null, currentFontSize = 72;
var previewOrientation = "landscape";
function setRot(d){ rot = (rot + d + 360) % 360; syncRotCrop(); drawPreview(); }
function setCrop(v){ var n = Number(v); if (!isFinite(n)) n = 1; crop = Math.max(0.25, Math.min(1, n)); syncRotCrop(); drawPreview(); }
function setFill(v){ fillMode = !!v; var fb = document.getElementById("fillBtn"); if (fb) fb.textContent = fillMode ? "Fill screen (on)" : "Crop to fill screen"; drawPreview(); }
function syncRotCrop(){ var cp = document.getElementById("cropPct"); if (cp) cp.textContent = Math.round(crop * 100); }
function showPreview(){ var pw = document.getElementById("previewWrap"); var db = document.getElementById("displayBtn"); if (pw) pw.classList.add("show"); if (db) db.disabled = false; }
function loadImage(src, isBlobUrl){
  if (imgEl && isBlobUrl && imgEl.src && imgEl.src.indexOf("blob:") === 0) URL.revokeObjectURL(imgEl.src);
  imgEl = new Image();
  imgEl.onload = function(){ rot = 0; crop = 1; fillMode = false; setFill(false); var cs = document.getElementById("cropSl"); if (cs) cs.value = 100; syncRotCrop(); drawPreview(); showPreview(); };
  imgEl.onerror = function(){ alert("Failed to load image"); };
  imgEl.src = src;
}
function renderTextToCanvas(text, fontSize){
  var c = document.createElement("canvas");
  c.width = DISP_W; c.height = DISP_H;
  var ctx = c.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, DISP_W, DISP_H);
  ctx.fillStyle = "#000";
  ctx.font = fontSize + "px sans-serif";
  ctx.textBaseline = "top";
  var maxW = DISP_W - 80, lineHeight = fontSize + Math.floor(fontSize/4), lines = [];
  var paras = (text || "").trim().split("\n");
  for (var p = 0; p < paras.length; p++) {
    var words = paras[p].split(/\\s+/);
    var cur = [];
    for (var i = 0; i < words.length; i++) {
      var trial = (cur.length ? cur.join(" ") + " " : "") + words[i];
      var m = ctx.measureText(trial);
      if (m.width > maxW && cur.length) { lines.push(cur.join(" ")); cur = [words[i]]; } else cur.push(words[i]);
    }
    if (cur.length) lines.push(cur.join(" "));
  }
  if (!lines.length) lines = [""];
  var totalH = lines.length * lineHeight;
  var y = (DISP_H - totalH) / 2;
  for (var j = 0; j < lines.length; j++) {
    var m2 = ctx.measureText(lines[j]);
    ctx.fillText(lines[j], (DISP_W - m2.width) / 2, y);
    y += lineHeight;
  }
  return c.toDataURL("image/png");
}
function drawPreview(){
  if (!imgEl || !imgEl.complete) return;
  var w = imgEl.naturalWidth, h = imgEl.naturalHeight;
  var rw = (rot % 180 === 0) ? w : h, rh = (rot % 180 === 0) ? h : w;
  var cw, ch, sx, sy;
  if (fillMode) {
    if (rw / rh > ASPECT) { ch = rh; cw = Math.max(1, rh * ASPECT); } else { cw = rw; ch = Math.max(1, rw / ASPECT); }
    sx = (rw - cw) / 2; sy = (rh - ch) / 2;
  } else {
    cw = Math.max(1, Math.floor(rw * crop)); ch = Math.max(1, Math.floor(rh * crop));
    sx = (rw - cw) / 2; sy = (rh - ch) / 2;
  }
  var temp = document.createElement("canvas");
  temp.width = rw; temp.height = rh;
  var tctx = temp.getContext("2d");
  tctx.translate(rw/2, rh/2);
  tctx.rotate(-rot * Math.PI / 180);
  tctx.translate(-w/2, -h/2);
  tctx.drawImage(imgEl, 0, 0, w, h);
  var scale = Math.min(DISP_W / cw, DISP_H / ch);
  var dw = cw * scale, dh = ch * scale;
  var dx = (DISP_W - dw) / 2, dy = (DISP_H - dh) / 2;
  var off = document.createElement("canvas");
  off.width = DISP_W; off.height = DISP_H;
  var octx = off.getContext("2d");
  octx.fillStyle = "#fff";
  octx.fillRect(0, 0, DISP_W, DISP_H);
  octx.drawImage(temp, sx, sy, cw, ch, dx, dy, dw, dh);
  var c = document.getElementById("preview");
  if (!c) return;
  var previewScale = 0.25;
  if (previewOrientation === "portrait") {
    c.width = 300; c.height = 400;
    var ctx = c.getContext("2d");
    ctx.fillStyle = "#222";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(off, 0, 0, DISP_W, DISP_H, 0, 0, 300, 400);
  } else {
    c.width = 400; c.height = 300;
    var ctx = c.getContext("2d");
    ctx.fillStyle = "#222";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.save();
    ctx.translate(200, 150);
    ctx.rotate(-90 * Math.PI / 180);
    ctx.scale(previewScale, previewScale);
    ctx.drawImage(off, 0, 0, DISP_W, DISP_H, -DISP_W/2, -DISP_H/2, DISP_W, DISP_H);
    ctx.restore();
  }
}
function setPreviewOrientation(ori){
  previewOrientation = ori;
  var op = document.getElementById("oriPortrait"), ol = document.getElementById("oriLandscape");
  if (op) op.classList.toggle("active", ori === "portrait");
  if (ol) ol.classList.toggle("active", ori === "landscape");
  drawPreview();
}
window.epaperOrientation = function(ori){ console.log("[epaper] orientation", ori); setPreviewOrientation(ori); };
window.epaperLoadImage = function(){
  console.log("[epaper] Load image");
  var fileInput = document.getElementById("fileIn");
  var urlInput = document.getElementById("urlIn");
  var f = fileInput && fileInput.files && fileInput.files.length > 0 ? fileInput.files[0] : null;
  var u = (urlInput && urlInput.value) ? String(urlInput.value).trim() : "";
  if (f) {
    currentFile = f; currentUrl = null; currentText = null;
    loadImage(URL.createObjectURL(f), true);
  } else if (u) {
    currentFile = null; currentUrl = u; currentText = null;
    var btn = document.getElementById("loadBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Loading..."; }
    fetch("/preview?url=" + encodeURIComponent(u)).then(function(r){ if (!r.ok) throw new Error(); return r.blob(); }).then(function(blob){ loadImage(URL.createObjectURL(blob), true); if (btn) { btn.disabled = false; btn.textContent = "Load image"; } }).catch(function(){ if (btn) { btn.disabled = false; btn.textContent = "Load image"; } alert("Failed to load image"); });
  } else { alert("Choose a file or enter a URL"); }
};
window.epaperLoadText = function(){
  console.log("[epaper] Load text");
  var textIn = document.getElementById("textIn");
  var fontSizeIn = document.getElementById("fontSize");
  var text = textIn ? textIn.value.trim() : "";
  if (!text) { alert("Enter some text"); return; }
  var fs = fontSizeIn ? parseInt(fontSizeIn.value, 10) : 72;
  fs = Math.max(24, Math.min(200, fs || 72));
  currentFile = null; currentUrl = null; currentText = text; currentFontSize = fs;
  loadImage(renderTextToCanvas(text, fs), true);
};
window.epaperRotate = function(d){ console.log("[epaper] rotate", d); setRot(d); };
window.epaperCrop = function(v){ console.log("[epaper] crop", v); setCrop(Number(v) / 100); };
window.epaperFill = function(){ console.log("[epaper] fill"); setFill(!fillMode); };
window.epaperDisplay = function(){
  console.log("[epaper] display");
  var btn = document.getElementById("displayBtn");
  var oldBtnText = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = "Sending..."; }
  function restoreButton(){ if (btn) { btn.disabled = false; btn.textContent = oldBtnText || "Display on e-paper"; } }
  function fail(){ restoreButton(); alert("Display failed. Check your input and try again."); }
  function done(r){ r.text().then(function(html){ document.open(); document.write(html); document.close(); }).catch(fail); }
  if (currentFile) {
    var fd = new FormData();
    fd.append("photo", currentFile);
    fd.append("rotation", String(rot));
    fd.append("crop", String(crop));
    fd.append("fill", fillMode ? "1" : "0");
    fetch("/display", { method: "POST", body: fd }).then(done).catch(fail);
  } else if (currentUrl) {
    var body = "url=" + encodeURIComponent(currentUrl) + "&rotation=" + rot + "&crop=" + crop + "&fill=" + (fillMode ? "1" : "0");
    fetch("/display_url", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: body }).then(done).catch(fail);
  } else if (currentText) {
    var body = "text=" + encodeURIComponent(currentText) + "&font_size=" + currentFontSize;
    fetch("/display_text", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: body }).then(done).catch(fail);
  } else {
    fail();
  }
};
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))

    def _path_only(self):
        return self.path.split("?")[0]

    def do_GET(self):
        path = self._path_only()
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif path == "/api/status":
            self._api_status()
        elif path == "/preview":
            self._preview_proxy()
        elif path == "/api/docs":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(API_DOCS_HTML.encode("utf-8"))
        else:
            self.send_error(404)

    def _preview_proxy(self):
        qs = self.path.split("?", 1)[-1] if "?" in self.path else ""
        params = parse_qs(qs)
        url = (params.get("url") or [None])[0]
        if not url or not url.strip():
            self.send_error(400, "Missing url")
            return
        url = url.strip()
        try:
            data = fetch_image(url)
            ct = sniff_image_content_type(data)
            self.send_response(200)
            self.send_header("Content-type", ct)
            self.send_header("Content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except ValueError as e:
            print("Preview proxy error:", e)
            self.send_error(400, str(e))
        except Exception as e:
            print("Preview proxy error:", e)
            self.send_error(502, "Failed to fetch image")

    def do_POST(self):
        path = self._path_only()
        # API: JSON responses
        if path == "/api/upload":
            self._api_upload()
            return
        if path == "/api/clear":
            self._api_clear()
            return

        # Web UI: redirects
        if path == "/display_url":
            self._display_url_redirect()
            return
        if path == "/display_text":
            self._display_text_redirect()
            return
        if path == "/display":
            ct = self.headers.get("Content-type", "")
            cl = self.headers.get("Content-length", "0")
            if not ct.startswith("multipart/form-data"):
                self.send_redirect("/?display=err")
                return
            try:
                data, form = parse_multipart_form(self.rfile, ct, cl)
                if not data:
                    self.send_redirect("/?display=err")
                    return
                rotation = parse_rotation(form.get("rotation"))
                fill = is_truthy(form.get("fill"))
                crop = parse_crop(form.get("crop"))
                image = load_image_from_bytes(data)
                image = apply_transform(image, rotation=rotation, crop=crop, fill=fill)
                show_image_on_epd(image)
                self.send_redirect("/?display=ok")
            except ValueError as e:
                print("Display error:", e)
                self.send_redirect("/?display=err")
            except Exception as e:
                print("Display error:", e)
                self.send_redirect("/?display=err")
            return

        if path == "/clear":
            try:
                clear_epd()
                self.send_redirect("/?clear=ok")
            except Exception as e:
                print("Clear error:", e)
                self.send_redirect("/?clear=err")
            return

        self.send_error(404)

    def _display_url_redirect(self):
        try:
            cl = parse_content_length(self.headers.get("Content-length", "0"))
            body = read_limited_body(self.rfile, cl, MAX_FORM_BYTES).decode("utf-8", errors="replace")
        except ValueError as e:
            print("Display from URL parse error:", e)
            self.send_redirect("/?display=err")
            return
        params = parse_qs(body)
        url = (params.get("url") or [None])[0]
        if not url or not url.strip():
            self.send_redirect("/?display=err")
            return
        url = url.strip()
        rotation = parse_rotation((params.get("rotation") or ["0"])[0])
        fill = is_truthy((params.get("fill") or [""])[0])
        crop = parse_crop((params.get("crop") or ["1"])[0])
        try:
            data = fetch_image(url)
            image = load_image_from_bytes(data)
            image = apply_transform(image, rotation=rotation, crop=crop, fill=fill)
            show_image_on_epd(image)
            self.send_redirect("/?display=ok")
        except ValueError as e:
            print("Display from URL error:", e)
            self.send_redirect("/?display=err")
        except Exception as e:
            print("Display from URL error:", e)
            self.send_redirect("/?display=err")

    def _display_text_redirect(self):
        try:
            cl = parse_content_length(self.headers.get("Content-length", "0"))
            body = read_limited_body(self.rfile, cl, MAX_FORM_BYTES).decode("utf-8", errors="replace")
        except ValueError as e:
            print("Display text parse error:", e)
            self.send_redirect("/?display=err")
            return
        params = parse_qs(body)
        text = (params.get("text") or [""])[0] or ""
        font_size = parse_font_size((params.get("font_size") or ["72"])[0])
        if not text.strip():
            self.send_redirect("/?display=err")
            return
        try:
            image = render_text_to_image(text.strip(), font_size=font_size)
            show_image_on_epd(image)
            self.send_redirect("/?display=ok")
        except Exception as e:
            print("Display text error:", e)
            self.send_redirect("/?display=err")

    def _send_json(self, status, body):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _api_upload(self):
        ct = self.headers.get("Content-type", "")
        try:
            cl = parse_content_length(self.headers.get("Content-length", "0"))
        except ValueError as e:
            self._send_json(400, {"ok": False, "error": str(e)})
            return
        if cl <= 0:
            self._send_json(400, {"ok": False, "error": "Request body is empty"})
            return
        if cl > MAX_UPLOAD_BYTES:
            self._send_json(413, {"ok": False, "error": "Image upload exceeds 12MB limit"})
            return
        data = None
        form = {}
        if ct.startswith("multipart/form-data"):
            try:
                data, form = parse_multipart_form(self.rfile, ct, str(cl))
            except ValueError as e:
                self._send_json(400, {"ok": False, "error": str(e)})
                return
        elif ct.startswith("image/"):
            try:
                data = read_limited_body(self.rfile, cl, MAX_UPLOAD_BYTES)
            except ValueError as e:
                self._send_json(400, {"ok": False, "error": str(e)})
                return
        else:
            self._send_json(400, {"ok": False, "error": "Unsupported Content-Type; use multipart/form-data or image/*"})
            return
        if not data:
            self._send_json(400, {"ok": False, "error": "Send image as multipart form field 'photo' or raw body with Content-Type: image/..."})
            return
        rotation = parse_rotation(form.get("rotation"))
        fill = is_truthy(form.get("fill"))
        crop = parse_crop(form.get("crop"))
        try:
            image = load_image_from_bytes(data)
        except ValueError as e:
            self._send_json(400, {"ok": False, "error": str(e)})
            return
        try:
            image = apply_transform(image, rotation=rotation, crop=crop, fill=fill)
            show_image_on_epd(image)
            self._send_json(200, {"ok": True, "message": "Display updating (~19s)"})
        except Exception as e:
            print("Display error:", e)
            self._send_json(500, {"ok": False, "error": str(e)})

    def _api_clear(self):
        try:
            clear_epd()
            self._send_json(200, {"ok": True, "message": "Screen cleared"})
        except Exception as e:
            print("Clear error:", e)
            self._send_json(500, {"ok": False, "error": str(e)})

    def _api_status(self):
        self._send_json(200, {
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
        })

    def send_redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


def run_server():
    port = 5000
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("e-Paper photo server: http://localhost:%s" % port)
    print("  Web UI: upload photo, Clear screen button")
    print("  API: POST /api/upload (multipart 'photo' or raw image), POST /api/clear, GET /api/status")
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
        # URL: fetch and display
        url = sys.argv[1]
        print("Fetching image...")
        data = fetch_image(url)
        image = load_image_from_bytes(data)
        print("Displaying (refresh ~19s)...")
        show_image_on_epd(image)
        get_epd().sleep()
        print("Done.")
        return

    # No args: run webserver
    run_server()


if __name__ == "__main__":
    main()
