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


def parse_multipart_form(rfile, content_type, content_length):
    """Parse multipart/form-data. Returns (photo_bytes or None, fields_dict)."""
    m = re.search(r'boundary=([^;\s]+)', content_type)
    if not m:
        return None, {}
    boundary = m.group(1).strip().encode("latin-1")
    if not boundary.startswith(b"--"):
        boundary = b"--" + boundary
    body = rfile.read(int(content_length or 0))
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


HTML_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>e-Paper Photo</title>
<style>
body{font-family:system-ui;max-width:420px;margin:2rem auto;padding:1rem;background:#111;color:#ddd;}
h1{font-size:1.2rem;}
input[type="file"],input[type="url"]{margin:0.5rem 0;width:100%;padding:0.5rem;background:#2a2a2a;border:1px solid #444;border-radius:6px;color:#ddd;}
input[type="url"]{font-size:1rem;}
input[type="range"]{width:100%;margin:0.25rem 0;}
button{padding:0.6rem 1rem;margin:0.25rem 0.25rem 0.25rem 0;cursor:pointer;border:none;border-radius:6px;font-size:1rem;}
.btn-display{background:#07c;color:#fff;}
.btn-clear{background:#444;color:#fff;}
.msg{margin-top:1rem;padding:0.5rem;border-radius:6px;font-size:0.9rem;}
.msg.ok{background:#162;}
.msg.err{background:#622;}
.section{margin-bottom:1.25rem;}
label{font-size:0.85rem;color:#999;}
.controls{background:#222;padding:0.75rem;border-radius:8px;margin:0.75rem 0;}
.controls label{display:block;margin-bottom:0.25rem;}
.controls .row{display:flex;align-items:center;gap:0.5rem;margin:0.35rem 0;}
#preview{max-width:100%;display:block;margin:0.5rem 0;border-radius:6px;background:#222;}
.preview-wrap{display:none;}
.preview-wrap.show{display:block;}
.preview-caption{font-size:0.75rem;color:#666;margin-bottom:0.25rem;}
</style></head><body>
<h1>e-Paper Photo Display</h1>
<div class="section">
  <label>Upload image</label>
  <form id="formFile" method="post" action="/display" enctype="multipart/form-data">
    <input type="file" name="photo" id="fileIn" accept="image/*" required><br>
    <div class="preview-wrap" id="previewWrap">
      <p class="preview-caption">Preview (display 1200\u00d71600, rotated 90\u00b0 CCW)</p>
      <canvas id="preview" width="400" height="300"></canvas>
      <div class="controls">
        <div class="row"><label>Rotate</label><button type="button" id="rotL">\u21b6 Left</button><button type="button" id="rotR">Right \u21b7</button></div>
        <label>Crop in: <span id="cropPct">100</span>%</label>
        <input type="range" id="cropSl" min="25" max="100" value="100" step="5">
        <div class="row"><button type="button" id="fillBtn" class="btn-display">Crop to fill screen</button></div>
        <input type="hidden" name="rotation" id="rotVal" value="0">
        <input type="hidden" name="crop" id="cropVal" value="1">
        <input type="hidden" name="fill" id="fillVal" value="0">
      </div>
    </div>
    <button type="submit" class="btn-display">Display on e-paper</button>
  </form>
</div>
<div class="section">
  <label>Or paste image URL</label>
  <form id="formUrl" method="post" action="/display_url">
    <input type="url" name="url" placeholder="https://example.com/photo.jpg" required><br>
    <div class="controls">
      <div class="row"><label>Rotate</label><button type="button" id="rotL2">\u21b6 Left</button><button type="button" id="rotR2">Right \u21b7</button></div>
      <label>Crop in: <span id="cropPct2">100</span>%</label>
      <input type="range" id="cropSl2" min="25" max="100" value="100" step="5">
      <div class="row"><button type="button" id="fillBtn2" class="btn-display">Crop to fill screen</button></div>
      <input type="hidden" name="rotation" id="rotVal2" value="0">
      <input type="hidden" name="crop" id="cropVal2" value="1">
      <input type="hidden" name="fill" id="fillVal2" value="0">
    </div>
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
var DISP_W = 1200, DISP_H = 1600, ASPECT = DISP_W / DISP_H;
var rot = 0, crop = 1, fillMode = false, imgEl = null;
function setRot(d){ rot = (rot + d + 360) % 360; syncRotCrop(); drawPreview(); }
function setCrop(v){ crop = Math.max(0.25, Math.min(1, v)); syncRotCrop(); drawPreview(); }
function setFill(v){ fillMode = !!v; document.getElementById("fillVal").value = document.getElementById("fillVal2").value = fillMode ? "1" : "0"; document.getElementById("fillBtn").textContent = document.getElementById("fillBtn2").textContent = fillMode ? "Fill screen (on)" : "Crop to fill screen"; drawPreview(); }
function syncRotCrop(){
  document.getElementById("rotVal").value = document.getElementById("rotVal2").value = rot;
  document.getElementById("cropVal").value = document.getElementById("cropVal2").value = crop;
  document.getElementById("cropPct").textContent = document.getElementById("cropPct2").textContent = Math.round(crop * 100);
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
  c.width = 400; c.height = 300;
  var ctx = c.getContext("2d");
  ctx.fillStyle = "#222";
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.save();
  ctx.translate(200, 150);
  ctx.rotate(-90 * Math.PI / 180);
  ctx.scale(0.25, 0.25);
  ctx.drawImage(off, 0, 0, DISP_W, DISP_H, -DISP_W/2, -DISP_H/2, DISP_W, DISP_H);
  ctx.restore();
}
document.getElementById("fileIn").onchange = function(){
  var f = this.files[0];
  if (!f) { document.getElementById("previewWrap").classList.remove("show"); return; }
  document.getElementById("previewWrap").classList.add("show");
  imgEl = new Image();
  imgEl.onload = function(){ rot = 0; crop = 1; fillMode = false; setFill(false); document.getElementById("cropSl").value = document.getElementById("cropSl2").value = 100; syncRotCrop(); drawPreview(); };
  imgEl.src = URL.createObjectURL(f);
};
document.getElementById("rotL").onclick = function(){ setRot(-90); };
document.getElementById("rotR").onclick = function(){ setRot(90); };
document.getElementById("rotL2").onclick = function(){ setRot(-90); };
document.getElementById("rotR2").onclick = function(){ setRot(90); };
document.getElementById("cropSl").oninput = function(){ setCrop(this.value / 100); document.getElementById("cropSl2").value = this.value; };
document.getElementById("cropSl2").oninput = function(){ setCrop(this.value / 100); document.getElementById("cropSl").value = this.value; };
document.getElementById("fillBtn").onclick = function(){ setFill(!fillMode); };
document.getElementById("fillBtn2").onclick = function(){ setFill(!fillMode); };
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
                data, form = parse_multipart_form(self.rfile, ct, cl)
                if not data:
                    self.send_redirect("/?display=err")
                    return
                rotation = int(form.get("rotation") or 0) % 360
                fill = form.get("fill", "").lower() in ("1", "on", "true", "yes")
                try:
                    crop = float(form.get("crop") or "1")
                except (TypeError, ValueError):
                    crop = 1.0
                crop = max(0.25, min(1.0, crop))
                image = Image.open(io.BytesIO(data))
                image = apply_transform(image, rotation=rotation, crop=crop, fill=fill)
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
        rotation = int((params.get("rotation") or ["0"])[0] or 0) % 360
        fill = ((params.get("fill") or [""])[0] or "").lower() in ("1", "on", "true", "yes")
        try:
            crop = float((params.get("crop") or ["1"])[0] or "1")
        except (TypeError, ValueError):
            crop = 1.0
        crop = max(0.25, min(1.0, crop))
        try:
            data = fetch_image(url)
            image = Image.open(io.BytesIO(data))
            image = apply_transform(image, rotation=rotation, crop=crop, fill=fill)
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
        form = {}
        if ct.startswith("multipart/form-data"):
            data, form = parse_multipart_form(self.rfile, ct, str(cl))
        elif ct.startswith("image/"):
            data = self.rfile.read(cl) if cl else b""
        if not data:
            self._send_json(400, {"ok": False, "error": "Send image as multipart form field 'photo' or raw body with Content-Type: image/..."})
            return
        rotation = int(form.get("rotation") or 0) % 360
        fill = form.get("fill", "").lower() in ("1", "on", "true", "yes")
        try:
            crop = float(form.get("crop") or "1")
        except (TypeError, ValueError):
            crop = 1.0
        crop = max(0.25, min(1.0, crop))
        try:
            image = Image.open(io.BytesIO(data))
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
