#!/usr/bin/env python3
"""Living Photos depth server - computes depth maps for the DynaFrame plugin
"Living Photos" on a stronger machine in your home network (e.g. Unraid).

Model: Depth Anything V2 Small (Apache-2.0), ONNX export by fabio-sim.

    GET  /health                 -> {"ok": true, "model": ..., "threads": n}
    POST /depth?size=518  (JPEG) -> PNG, grayscale, bright = near

Run (Docker, no own image needed):
    docker run -d --name living-photos-depth --restart unless-stopped \
      -p 8765:8765 -v /mnt/user/appdata/living-photos-depth:/data \
      python:3.12-slim sh -c "pip install --no-cache-dir onnxruntime numpy pillow && \
      python -c \"import urllib.request as u; u.urlretrieve('https://raw.githubusercontent.com/Archonw/Jans-DynaframePro-Store/main/plugin_packs/living-photos/depth-server/server.py', '/data/server.py')\" && \
      python /data/server.py"

Settings via environment: PORT (8765), DATA (/data), THREADS (all cores).
"""

import hashlib
import io
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

VERSION = "1.0.0"
MODEL_FILE = "depth_anything_v2_vits_dynamic.onnx"
MODEL_SHA256 = "46c4e8eeda3a27f34701831b6a2ec7753d7b38779b215acb5633424703deed8f"
MODEL_URL = "https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/" + MODEL_FILE
DATA = os.environ.get("DATA", "/data")
PORT = int(os.environ.get("PORT", "8765"))
THREADS = int(os.environ.get("THREADS", "0")) or (os.cpu_count() or 4)
MEAN = np.array((0.485, 0.456, 0.406), dtype=np.float32)
STD = np.array((0.229, 0.224, 0.225), dtype=np.float32)
MAX_BODY = 25 * 1024 * 1024

lock = threading.Lock()
stats = {"count": 0, "seconds": 0.0}


def model_path():
    path = os.path.join(DATA, MODEL_FILE)
    if os.path.isfile(path):
        return path
    os.makedirs(DATA, exist_ok=True)
    print(f"Downloading model from {MODEL_URL} ...", flush=True)
    temp = path + ".part"
    urllib.request.urlretrieve(MODEL_URL, temp)
    sha = hashlib.sha256()
    with open(temp, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha.update(chunk)
    if sha.hexdigest() != MODEL_SHA256:
        os.remove(temp)
        raise SystemExit("Model checksum mismatch")
    os.replace(temp, path)
    return path


options = ort.SessionOptions()
options.intra_op_num_threads = THREADS
session = ort.InferenceSession(model_path(), options, providers=["CPUExecutionProvider"])
INPUT = session.get_inputs()[0].name


def depth_png(data, size):
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    w, h = image.size
    scale = size / max(w, h)
    tw = max(112, int(round(w * scale / 14)) * 14)
    th = max(112, int(round(h * scale / 14)) * 14)
    pixels = np.asarray(image.resize((tw, th), Image.BICUBIC), dtype=np.float32) / 255.0
    batch = ((pixels - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    started = time.time()
    with lock:
        raw = session.run(None, {INPUT: batch})[0]
    stats["count"] += 1
    stats["seconds"] += time.time() - started
    raw = np.squeeze(raw).astype(np.float32)
    low, high = np.percentile(raw, 1), np.percentile(raw, 99)
    norm = np.clip((raw - low) / max(1e-6, high - low), 0, 1)
    out = io.BytesIO()
    Image.fromarray((norm * 255).astype(np.uint8), "L").save(out, "PNG")
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def send(self, status, body, kind):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        self.send(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            average = stats["seconds"] / stats["count"] if stats["count"] else 0
            self.send_json(200, {"ok": True, "service": "living-photos-depth", "version": VERSION,
                                 "model": "Depth Anything V2 Small", "threads": THREADS,
                                 "count": stats["count"], "averageSeconds": round(average, 2)})
        else:
            self.send_json(404, {"ok": False})

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if parsed.path != "/depth" or not 0 < length <= MAX_BODY:
            self.send_json(400, {"ok": False, "error": "POST /depth with an image"})
            return
        data = self.rfile.read(length)
        try:
            size = int((parse_qs(parsed.query).get("size") or ["518"])[0])
        except ValueError:
            size = 518
        try:
            self.send(200, depth_png(data, max(196, min(1036, size))), "image/png")
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)[:200]})


if __name__ == "__main__":
    print(f"Living Photos depth server {VERSION} on port {PORT}, {THREADS} threads", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
