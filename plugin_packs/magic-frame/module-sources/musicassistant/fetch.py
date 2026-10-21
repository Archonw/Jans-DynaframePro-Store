"""Music Assistant für Dynaframe's Magic Mirror.

Nachbau von MMM-MusicAssistant (egeekial, MIT). Music Assistant spricht nur
über seine WebSocket-API (ws://<server>:8095/ws). Ein kleiner WebSocket-Client
aus der Standardbibliothek reicht dafür: verbinden, mit dem Token anmelden,
players/all und player_queues/all abfragen, wieder trennen. Das Modul holt
nur, solange die Szene läuft, dann alle 10 Sekunden.
"""

import base64
import json
import os
import socket
import ssl
import struct
import time
import uuid
from urllib.parse import quote, urlparse

TIMEOUT = 6
AUTH_SCHEMA = 28   # ab dieser Schema-Version verlangt Music Assistant einen Token


class Closed(Exception):
    pass


class WebSocket:
    """Gerade genug RFC 6455 für Textnachrichten."""

    def __init__(self, url):
        parts = urlparse(url)
        secure = parts.scheme in ("wss", "https")
        host, port = parts.hostname, parts.port or (443 if secure else 80)
        sock = socket.create_connection((host, port), TIMEOUT)
        sock.settimeout(TIMEOUT)
        if secure:
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        self.sock, self.buffer = sock, b""
        key = base64.b64encode(os.urandom(16)).decode()
        path = parts.path or "/"
        sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                      "User-Agent: DynaframeMagicMirror-MusicAssistant/1.0\r\n\r\n").encode())
        while b"\r\n\r\n" not in self.buffer:
            self._fill()
        head, self.buffer = self.buffer.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0]
        if b" 101" not in status:
            raise ConnectionError(status.decode("latin-1", "replace"))

    def _fill(self):
        chunk = self.sock.recv(65536)
        if not chunk:
            raise Closed()
        self.buffer += chunk

    def _take(self, size):
        while len(self.buffer) < size:
            self._fill()
        out, self.buffer = self.buffer[:size], self.buffer[size:]
        return out

    def _send(self, opcode, data):
        header = bytes([0x80 | opcode])
        size = len(data)
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", size)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", size)
        mask = os.urandom(4)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def send(self, text):
        self._send(0x1, text.encode())

    def recv(self):
        message = b""
        while True:
            first, second = self._take(2)
            opcode, size = first & 0x0F, second & 0x7F
            if size == 126:
                size = struct.unpack(">H", self._take(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self._take(8))[0]
            mask = self._take(4) if second & 0x80 else None
            data = self._take(size)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                raise Closed()
            if opcode == 0x9:
                self._send(0xA, data)
                continue
            if opcode in (0x0, 0x1, 0x2):
                message += data
                if first & 0x80:
                    return message.decode("utf-8", "replace")

    def close(self):
        try:
            self._send(0x8, b"")
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class Client:
    def __init__(self, ws):
        self.ws = ws

    def command(self, name, args=None):
        message_id = uuid.uuid4().hex
        self.ws.send(json.dumps({"command": name, "message_id": message_id, "args": args or {}}))
        partial = []
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("message_id") != message_id:
                continue   # Ereignisse anderer Spieler
            if msg.get("error_code"):
                raise RuntimeError(str(msg.get("details") or msg.get("error_code")))
            result = msg.get("result")
            if msg.get("partial"):
                partial.extend(result or [])
                continue
            return partial + (result or []) if partial else result


# --------------------------------------------------------------------------
# Aus Spielern und Warteschlangen wird "läuft gerade" (wie MaState.js)
# --------------------------------------------------------------------------

def resolve_queue(players, queues, wanted):
    by_id = {q.get("queue_id"): q for q in queues}
    want = str(wanted or "").strip().lower()

    def queue_for(player):
        if not player:
            return None
        return by_id.get(player.get("active_source") or player.get("player_id")) or by_id.get(player.get("player_id"))

    pinned = None
    if want:
        pinned = next((p for p in players if str(p.get("player_id") or "").lower() == want), None) or \
            next((p for p in players if str(p.get("display_name") or p.get("name") or "").lower() == want), None)
    pinned_queue = queue_for(pinned)
    if pinned_queue and pinned_queue.get("state") == "playing":
        return pinned_queue
    playing = next((q for q in queues if q.get("state") == "playing" and q.get("active") is not False), None)
    # anders als das Original: ohne bevorzugten Player auch einen pausierten zeigen
    paused = next((q for q in queues if q.get("state") == "paused" and q.get("current_item")), None)
    return playing or pinned_queue or paused


def meta(item, media, radio):
    title = artist = album = ""
    if media:
        title = media.get("name") or ""
        if media.get("version"):
            title = f"{title} ({media['version']})"
        artist = ", ".join(a.get("name") for a in media.get("artists") or [] if isinstance(a, dict) and a.get("name"))
        album = ((media.get("album") or {}).get("name")) or ""
    stream = ((item or {}).get("streamdetails") or {}).get("stream_title")
    if (radio or not title) and stream:
        if " - " in stream:
            first, rest = stream.split(" - ", 1)
            artist = artist or first.strip()
            title = rest.strip()
        elif not title:
            title = stream
    if not title and item:
        title = item.get("name") or ""
    return title, artist, album


def pick_image(item, media):
    for image in ((item or {}).get("image"), (media or {}).get("image"), ((media or {}).get("album") or {}).get("image")):
        if image:
            return image
    return None


def image_url(image, size, schema, base):
    if not isinstance(image, dict):
        return ""
    if schema >= 31 and image.get("proxy_id"):
        return f"{base}/imageproxy/{image['proxy_id']}?size={size}"
    if image.get("remotely_accessible") and image.get("path"):
        return image["path"]
    if not image.get("path"):
        return ""
    return (f"{base}/imageproxy?path={quote(quote(image['path'], safe=''), safe='')}"
            f"&provider={quote(str(image.get('provider') or ''), safe='')}&size={size}")


def now_playing(players, queues, wanted, schema, base, size):
    queue = resolve_queue(players, queues, wanted)
    if not queue or queue.get("state") not in ("playing", "paused"):
        return {"state": "idle"}
    item = queue.get("current_item") or {}
    media = item.get("media_item") or None
    radio = (media or {}).get("media_type") == "radio" or \
        ((item.get("streamdetails") or {}).get("media_type") == "radio")
    title, artist, album = meta(item, media, radio)
    player = next((p for p in players if p.get("player_id") == queue.get("queue_id")), {})
    out = {
        "state": queue["state"],
        "player": player.get("display_name") or player.get("name") or queue.get("display_name") or "",
        "title": title, "artist": artist, "album": "" if radio else album, "radio": bool(radio),
        "duration": item.get("duration") or 0,
        "elapsed": queue.get("elapsed_time") or 0,
        "elapsedAt": queue.get("elapsed_time_last_updated") or time.time(),
        "image": image_url(pick_image(item, media), size, schema, base),
        "next": None,
    }
    following = queue.get("next_item")
    if following:
        n_title, n_artist, _ = meta(following, following.get("media_item"), False)
        out["next"] = {"title": n_title, "artist": n_artist}
    return out


def fetch(config, ctx):
    SourceError = ctx["SourceError"]
    server = str(config.get("server") or "").strip().rstrip("/")
    if not server:
        raise SourceError("no-key")
    if "://" not in server:
        server = "http://" + server
    if urlparse(server).port is None and urlparse(server).scheme == "http" and not urlparse(server).path.strip("/"):
        server += ":8095"   # Standard-Port von Music Assistant
    ws_url = "ws" + server[4:] if server.startswith("http") else server
    ws_url = ws_url if ws_url.rstrip("/").endswith("/ws") else ws_url + "/ws"
    base = server[:-3] if server.endswith("/ws") else server
    try:
        ws = WebSocket(ws_url)
    except (OSError, ConnectionError, Closed) as exc:
        raise SourceError("unreachable", str(exc)) from exc
    try:
        info = json.loads(ws.recv())
        schema = int(info.get("schema_version") or 0)
        client = Client(ws)
        if schema >= AUTH_SCHEMA:
            if not config.get("token"):
                raise SourceError("no-key")
            try:
                client.command("auth", {"token": config["token"]})
            except RuntimeError as exc:
                raise SourceError("key", str(exc)) from exc
        players = client.command("players/all") or []
        queues = client.command("player_queues/all") or []
    except (OSError, Closed, ValueError) as exc:
        raise SourceError("unreachable", str(exc)) from exc
    except RuntimeError as exc:
        raise SourceError("format", str(exc)) from exc
    finally:
        ws.close()
    size = 512 if config.get("layout") == "background" or config.get("cover") == "large" else 256
    out = now_playing(players, queues, config.get("player"), schema, base, size)
    out["players"] = sorted({str(p.get("display_name") or p.get("name") or "") for p in players} - {""})[:30]
    return out
