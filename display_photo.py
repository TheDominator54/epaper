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
"""
import io
import json
import os
import re
import sys
from urllib.parse import parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

# Run from repo root: lib is python/lib
_this_dir = os.path.dirname(os.path.realpath(__file__))
_libdir = os.path.join(_this_dir, "python", "lib")
if os.path.exists(_libdir):
    sys.path.insert(0, _libdir)

import epd13in3E
from PIL import Image

EPD_WIDTH = 1200
EPD_HEIGHT = 1600

# One EPD instance, init on first use
_epd = None


def get_epd():
    global _epd
    if _epd is None:
        _epd = epd13in3E.EPD()
        _epd.Init()
    return _epd


def fetch_image(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "e-Paper/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


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


def parse_multipart_photo(rfile, content_type, content_length):
    """Parse multipart/form-data and return bytes of the first file named 'photo'. No cgi module."""
    # Get boundary from Content-Type: multipart/form-data; boundary=----...
    m = re.search(r'boundary=([^;\s]+)', content_type)
    if not m:
        return None
    boundary = m.group(1).strip().encode("latin-1")
    if not boundary.startswith(b"--"):
        boundary = b"--" + boundary
    body = rfile.read(int(content_length or 0))
    parts = body.split(boundary)
    for part in parts:
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        head, _, payload = part.partition(b"\r\n\r\n")
        if b'name="photo"' not in head and b"name='photo'" not in head:
            continue
        # payload may end with \r\n
        return payload.rstrip(b"\r\n")
    return None


HTML_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>e-Paper Photo</title>
<style>
body{font-family:system-ui;max-width:420px;margin:2rem auto;padding:1rem;background:#111;color:#ddd;}
h1{font-size:1.2rem;}
input[type="file"],input[type="url"]{margin:0.5rem 0;width:100%;padding:0.5rem;background:#2a2a2a;border:1px solid #444;border-radius:6px;color:#ddd;}
input[type="url"]{font-size:1rem;}
button{padding:0.6rem 1rem;margin:0.25rem 0.25rem 0.25rem 0;cursor:pointer;border:none;border-radius:6px;font-size:1rem;}
.btn-display{background:#07c;color:#fff;}
.btn-clear{background:#444;color:#fff;}
.msg{margin-top:1rem;padding:0.5rem;border-radius:6px;font-size:0.9rem;}
.msg.ok{background:#162;}
.msg.err{background:#622;}
.section{margin-bottom:1.25rem;}
label{font-size:0.85rem;color:#999;}
</style></head><body>
<h1>e-Paper Photo Display</h1>
<div class="section">
  <label>Upload image</label>
  <form method="post" action="/display" enctype="multipart/form-data">
    <input type="file" name="photo" accept="image/*" required><br>
    <button type="submit" class="btn-display">Display on e-paper</button>
  </form>
</div>
<div class="section">
  <label>Or paste image URL</label>
  <form method="post" action="/display_url">
    <input type="url" name="url" placeholder="https://example.com/photo.jpg" required><br>
    <button type="submit" class="btn-display">Display from URL</button>
  </form>
</div>
<form method="post" action="/clear" style="display:inline;">
  <button type="submit" class="btn-clear">Clear screen</button>
</form>
<p style="color:#666;font-size:0.85rem;">Refresh takes ~19s.</p>
<div id="msg" class="msg" style="display:none;"></div>
<script>
(function(){
  var q = new URLSearchParams(location.search);
  var m = document.getElementById("msg");
  if (q.get("display") === "ok") { m.className = "msg ok"; m.style.display = "block"; m.textContent = "Display updating (~19s)."; }
  if (q.get("display") === "err") { m.className = "msg err"; m.style.display = "block"; m.textContent = "Display failed."; }
  if (q.get("clear") === "ok") { m.className = "msg ok"; m.style.display = "block"; m.textContent = "Screen cleared."; }
  if (q.get("clear") === "err") { m.className = "msg err"; m.style.display = "block"; m.textContent = "Clear failed."; }
})();
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
        else:
            self.send_error(404)

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
        if path == "/display":
            ct = self.headers.get("Content-type", "")
            cl = self.headers.get("Content-length", "0")
            if not ct.startswith("multipart/form-data"):
                self.send_redirect("/?display=err")
                return
            try:
                data = parse_multipart_photo(self.rfile, ct, cl)
                if not data:
                    self.send_redirect("/?display=err")
                    return
                image = Image.open(io.BytesIO(data))
                show_image_on_epd(image)
                self.send_redirect("/?display=ok")
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
        cl = int(self.headers.get("Content-length", "0") or 0)
        body = self.rfile.read(cl).decode("utf-8", errors="replace")
        params = parse_qs(body)
        url = (params.get("url") or [None])[0]
        if not url or not url.strip():
            self.send_redirect("/?display=err")
            return
        url = url.strip()
        try:
            data = fetch_image(url)
            image = Image.open(io.BytesIO(data))
            show_image_on_epd(image)
            self.send_redirect("/?display=ok")
        except Exception as e:
            print("Display from URL error:", e)
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
        cl = int(self.headers.get("Content-length", "0") or 0)
        data = None
        if ct.startswith("multipart/form-data"):
            data = parse_multipart_photo(self.rfile, ct, str(cl))
        elif ct.startswith("image/"):
            data = self.rfile.read(cl) if cl else b""
        if not data:
            self._send_json(400, {"ok": False, "error": "Send image as multipart form field 'photo' or raw body with Content-Type: image/..."})
            return
        try:
            image = Image.open(io.BytesIO(data))
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

    def send_redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


def run_server():
    port = 5000
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("e-Paper photo server: http://localhost:%s" % port)
    print("  Web UI: upload photo, Clear screen button")
    print("  API: POST /api/upload (multipart 'photo' or raw image), POST /api/clear")
    print("  From another device: http://<pi-ip>:%s" % port)
    server.serve_forever()


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
        image = Image.open(io.BytesIO(data))
        print("Displaying (refresh ~19s)...")
        show_image_on_epd(image)
        get_epd().sleep()
        print("Done.")
        return

    # No args: run webserver
    run_server()


if __name__ == "__main__":
    main()
