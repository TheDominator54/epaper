"""
E-paper image server.
Web server that accepts image uploads and displays them on a Waveshare 13.3" E Ink Spectra 6 (E6)
1600×1200 display. Runs on Raspberry Pi (bare metal). SPI required.
"""
import gc
import importlib
import logging
import os
import sys
import threading
from pathlib import Path

from flask import Flask, request, redirect, url_for, render_template_string, jsonify
from PIL import Image

_log_level = getattr(
    logging,
    os.environ.get("LOG_LEVEL", "INFO").strip().upper(),
    logging.INFO,
)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("epaper")

# Config from environment
EPD_LISTEN_HOST = os.environ.get("EPD_LISTEN_HOST", "0.0.0.0")
EPD_LISTEN_PORT = int(os.environ.get("EPD_LISTEN_PORT", "8080"))
EPD_DRIVER_NAME = os.environ.get("EPD_DRIVER", "epd13in3e")
# Many 13.3" E HATs need SPI device 1; set before driver/epdconfig load
if "EPD_SPI_DEVICE" not in os.environ and EPD_DRIVER_NAME == "epd13in3e":
    os.environ.setdefault("EPD_SPI_DEVICE", "1")
    logger.info("Defaulting EPD_SPI_DEVICE=1 for 13.3\" E (set EPD_SPI_DEVICE=0 to override)")

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
CURRENT_IMAGE = UPLOAD_DIR / "current.png"

app = Flask(__name__)
# No upload size limit; any resolution/format is resized and converted for the display
app.config["MAX_CONTENT_LENGTH"] = None

# Load EPD driver dynamically
logger.info("Loading EPD driver: EPD_DRIVER=%s", EPD_DRIVER_NAME)
try:
    _epd_module = importlib.import_module(f"waveshare_epd.{EPD_DRIVER_NAME}")
    logger.info("Imported module: %s", _epd_module.__name__)
except Exception as e:
    logger.exception("Failed to import EPD driver %s", EPD_DRIVER_NAME)
    raise RuntimeError(
        f"Failed to import EPD driver '{EPD_DRIVER_NAME}'. "
        "Set EPD_DRIVER to your driver module name (e.g. epd13in3e). "
        f"Error: {e}"
    ) from e

# Get driver class (common patterns: EPD or epd class in module)
EPDClass = getattr(_epd_module, "EPD", None) or getattr(_epd_module, "epd", None)
if EPDClass is None:
    logger.error("Module %s has no EPD or epd class", _epd_module.__name__)
    raise RuntimeError(f"EPD driver {EPD_DRIVER_NAME} has no EPD or epd class.")

_epd = EPDClass()
EPD_WIDTH = getattr(_epd_module, "EPD_WIDTH", None) or getattr(_epd, "width", 1600)
EPD_HEIGHT = getattr(_epd_module, "EPD_HEIGHT", None) or getattr(_epd, "height", 1200)
logger.info(
    "EPD instance created: %dx%d (EPD_SPI_DEVICE=%s)",
    EPD_WIDTH,
    EPD_HEIGHT,
    os.environ.get("EPD_SPI_DEVICE", "0"),
)

_display_lock = threading.Lock()


def _epd_method(*names: str):
    """Return the first EPD method that exists. Avoids getattr default being evaluated."""
    for name in names:
        fn = getattr(_epd, name, None)
        if fn is not None:
            return fn
    raise RuntimeError(f"EPD object has none of: {names}")


def _image_to_display_format(image: Image.Image) -> Image.Image:
    """Resize to EPD size. 13.3" E driver expects RGB and does 7-color quantization in getbuffer()."""
    im = image.convert("RGB").resize((EPD_WIDTH, EPD_HEIGHT), Image.Resampling.LANCZOS)
    return im


def _update_display(image_path: Path) -> None:
    """Load image from path, send to EPD. Runs with _display_lock held."""
    logger.info("Display update starting: path=%s", image_path)
    try:
        logger.info("Display update: waiting for display lock")
        with _display_lock:
            logger.info("Display update: lock acquired, loading image")
            img = Image.open(image_path)
            logger.info("Image opened: size=%s mode=%s", img.size, img.mode)
            img = _image_to_display_format(img)
            logger.info("Image resized to EPD format: %dx%d RGB", EPD_WIDTH, EPD_HEIGHT)
            gc.collect()
            logger.info("Calling EPD Init()")
            init_fn = _epd_method("Init", "init")
            init_fn()
            clear_fn = getattr(_epd, "Clear", None)
            if clear_fn is not None:
                logger.info("Calling EPD Clear() (per demo sequence, ~19s)")
                clear_fn()
                logger.info("EPD Clear() finished")
            logger.info("Getting buffer from image")
            try:
                buf = _epd.getbuffer(img)
                del img
                gc.collect()
                logger.info("Buffer obtained (%s bytes), calling display() (~19s)", len(buf) if buf is not None else "?")
                _epd.display(buf)
                logger.info("EPD display() finished")
            except TypeError:
                logger.warning("getbuffer/display(buf) failed with TypeError, trying display(image)")
                _epd.display(img)
                logger.info("EPD display(image) finished")
            logger.info("Calling EPD Sleep()")
            sleep_fn = _epd_method("Sleep", "sleep")
            sleep_fn()
            logger.info("Display update finished successfully")
    except Exception as e:
        logger.exception("Display update failed: %s", e)
        raise


def _update_display_background(image_path: Path) -> None:
    """Run _update_display in a daemon thread."""
    logger.info("Starting background thread to update display from %s", image_path)
    t = threading.Thread(target=_update_display, args=(image_path,), daemon=True)
    t.start()


def _run_clear() -> None:
    """Run EPD Init -> Clear -> Sleep (same as demo clear). Uses _display_lock."""
    logger.info("Clear display: starting (Init -> Clear -> Sleep)")
    try:
        logger.info("Clear: waiting for display lock")
        with _display_lock:
            logger.info("Clear: display lock acquired")
            logger.info("Clear: calling EPD Init()")
            init_fn = _epd_method("Init", "init")
            init_fn()
            logger.info("Clear: EPD Init() done")
            clear_fn = getattr(_epd, "Clear", None)
            if clear_fn is None:
                logger.warning("Clear: EPD has no Clear method, skipping")
                return
            logger.info("Clear: calling EPD Clear() (full panel refresh, ~19s)")
            clear_fn()
            logger.info("Clear: EPD Clear() done")
            logger.info("Clear: calling EPD Sleep()")
            sleep_fn = _epd_method("Sleep", "sleep")
            sleep_fn()
            logger.info("Clear display: finished successfully")
    except Exception as e:
        logger.exception("Clear display failed: %s", e)
        raise


def _run_clear_background() -> None:
    """Run _run_clear in a daemon thread."""
    logger.info("Starting background thread for clear display")
    t = threading.Thread(target=_run_clear, daemon=True)
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
  <form method="post" action="/clear" style="margin-top: 1em;">
    <button type="submit">Clear display</button>
  </form>
  <p style="margin-top: 1em; font-size: 0.9em; color: #666;">Clear runs Init → Clear → Sleep (like the demo). Takes ~20–25s.</p>
  {% if message %}
  <p class="msg">{{ message }}</p>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def index():
    message = request.args.get("message", "")
    logger.debug("GET / message=%r", message[:50] if message else "")
    return render_template_string(
        INDEX_HTML, width=EPD_WIDTH, height=EPD_HEIGHT, message=message
    )


@app.route("/upload", methods=["POST"])
def upload():
    logger.info("POST /upload received")
    f = request.files.get("image")
    success, message = _process_uploaded_file(f)
    logger.info("POST /upload result: success=%s message=%s", success, message)
    if success:
        return redirect(url_for("index", message=message))
    return redirect(url_for("index", message=message), code=400)


@app.route("/clear", methods=["POST"])
def clear():
    """Run EPD clear (Init -> Clear -> Sleep) in background, same as demo."""
    logger.info("POST /clear received, starting clear in background")
    _run_clear_background()
    return redirect(url_for("index", message="Clear started; display updating (~20–25s)."))


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Run EPD clear in background. Returns JSON { "ok": true, "message": "..." }."""
    logger.info("POST /api/clear received")
    _run_clear_background()
    return jsonify({"ok": True, "message": "Clear started; display updating (~20–25s)."}), 200


def _process_uploaded_file(f) -> tuple[bool, str]:
    """Validate upload, save to CURRENT_IMAGE, start display update. Returns (success, message)."""
    if not f or f.filename == "":
        logger.warning("Upload rejected: no file selected")
        return False, "No file selected"
    logger.info("Processing upload: filename=%s", f.filename)
    try:
        img = Image.open(f.stream)
        img.verify()
        logger.info("Image validated: size=%s mode=%s", img.size, img.mode)
    except Exception as e:
        logger.warning("Invalid image: %s", e)
        return False, f"Invalid image: {e}"
    f.stream.seek(0)
    f.save(CURRENT_IMAGE)
    logger.info("Saved to %s, starting display update", CURRENT_IMAGE)
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
    logger.debug("GET /health")
    return "ok", 200


if __name__ == "__main__":
    logger.info(
        "Starting server: host=%s port=%s upload_dir=%s",
        EPD_LISTEN_HOST,
        EPD_LISTEN_PORT,
        UPLOAD_DIR,
    )
    app.run(host=EPD_LISTEN_HOST, port=EPD_LISTEN_PORT, threaded=True)
