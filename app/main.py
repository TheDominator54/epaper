"""
E-paper image server.
Web server that accepts image uploads and displays them on a Waveshare 13.3" E Ink Spectra 6 (E6)
1600×1200 display. Runs on Raspberry Pi (bare metal). SPI required.
"""
import gc
import importlib
import os
import threading
from pathlib import Path

from flask import Flask, request, redirect, url_for, render_template_string, jsonify
from PIL import Image

# Config from environment
EPD_LISTEN_HOST = os.environ.get("EPD_LISTEN_HOST", "0.0.0.0")
EPD_LISTEN_PORT = int(os.environ.get("EPD_LISTEN_PORT", "8080"))
EPD_DRIVER_NAME = os.environ.get("EPD_DRIVER", "epd13in3e")

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
CURRENT_IMAGE = UPLOAD_DIR / "current.png"

app = Flask(__name__)
# No upload size limit; any resolution/format is resized and converted for the display
app.config["MAX_CONTENT_LENGTH"] = None

# Load EPD driver dynamically
try:
    _epd_module = importlib.import_module(f"waveshare_epd.{EPD_DRIVER_NAME}")
except Exception as e:
    raise RuntimeError(
        f"Failed to import EPD driver '{EPD_DRIVER_NAME}'. "
        "Set EPD_DRIVER to your driver module name (e.g. epd13in3e). "
        f"Error: {e}"
    ) from e

# Get driver class (common patterns: EPD or epd class in module)
EPDClass = getattr(_epd_module, "EPD", getattr(_epd_module, "epd", None))
if EPDClass is None:
    raise RuntimeError(f"EPD driver {EPD_DRIVER_NAME} has no EPD or epd class.")

_epd = EPDClass()
EPD_WIDTH = getattr(_epd_module, "EPD_WIDTH", getattr(_epd, "width", 1600))
EPD_HEIGHT = getattr(_epd_module, "EPD_HEIGHT", getattr(_epd, "height", 1200))

_display_lock = threading.Lock()


def _image_to_display_format(image: Image.Image) -> Image.Image:
    """Resize to EPD size and convert to 1-bit for typical drivers."""
    im = image.convert("RGB").resize((EPD_WIDTH, EPD_HEIGHT), Image.Resampling.LANCZOS)
    return im.convert("1")


def _update_display(image_path: Path) -> None:
    """Load image from path, send to EPD. Runs with _display_lock held."""
    with _display_lock:
        img = Image.open(image_path)
        img = _image_to_display_format(img)
        gc.collect()
        _epd.init()
        try:
            buf = _epd.getbuffer(img)
            del img
            gc.collect()
            _epd.display(buf)
        except TypeError:
            # Some drivers take image directly
            _epd.display(img)
        _epd.sleep()


def _update_display_background(image_path: Path) -> None:
    """Run _update_display in a daemon thread."""
    t = threading.Thread(target=_update_display, args=(image_path,), daemon=True)
    t.start()


INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>E-paper upload</title>
  <style>
    body { font-family: sans-serif; max-width: 40em; margin: 2em auto; padding: 0 1em; }
    form { margin: 1em 0; }
    input[type="file"] { margin: 0.5em 0; }
    button { padding: 0.5em 1em; }
    .msg { margin: 1em 0; padding: 0.5em; background: #eee; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>E-paper image server</h1>
  <p>Upload an image to display on the 13.3" E Ink panel ({{ width }}×{{ height }}). Any file size, resolution, and image format (JPEG, PNG, BMP, GIF, WebP, etc.) are accepted and will be scaled to fit.</p>
  <form method="post" action="/upload" enctype="multipart/form-data">
    <input type="file" name="image" required>
    <button type="submit">Upload and display</button>
  </form>
  {% if message %}
  <p class="msg">{{ message }}</p>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def index():
    message = request.args.get("message", "")
    return render_template_string(
        INDEX_HTML, width=EPD_WIDTH, height=EPD_HEIGHT, message=message
    )


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("image")
    success, message = _process_uploaded_file(f)
    if success:
        return redirect(url_for("index", message=message))
    return redirect(url_for("index", message=message), code=400)


def _process_uploaded_file(f) -> tuple[bool, str]:
    """Validate upload, save to CURRENT_IMAGE, start display update. Returns (success, message)."""
    if not f or f.filename == "":
        return False, "No file selected"
    try:
        img = Image.open(f.stream)
        img.verify()
    except Exception as e:
        return False, f"Invalid image: {e}"
    f.stream.seek(0)
    f.save(CURRENT_IMAGE)
    _update_display_background(CURRENT_IMAGE)
    return True, "Image uploaded; display updating."


@app.route("/api/photos", methods=["POST"])
def api_photos():
    """
    Upload an image to display on the e-paper. Accepts multipart/form-data with field 'image' or 'file'.
    Returns JSON: { "ok": true, "message": "..." } or { "ok": false, "error": "..." } with 4xx on failure.
    """
    f = request.files.get("image") or request.files.get("file")
    success, message = _process_uploaded_file(f)
    if success:
        return jsonify({"ok": True, "message": message}), 200
    return jsonify({"ok": False, "error": message}), 400


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    app.run(host=EPD_LISTEN_HOST, port=EPD_LISTEN_PORT, threaded=True)
