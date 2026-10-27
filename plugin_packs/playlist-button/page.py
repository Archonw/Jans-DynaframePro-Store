"""Einstellungen und Plugin-Seite des Playlist Button.

Alle Einstellungen liegen in data/settings.json (bleibt bei Updates) und werden
auf der eigenen Plugin-Seite (Advanced Settings) bearbeitet, wie bei Fußball
Live. Beim ersten Start nach dem Update werden die Werte der alten
Plugins-Seite (manifest.json) uebernommen, damit z.B. der GPIO-Pin erhalten bleibt.
"""
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PLUGIN_DIR = Path(__file__).resolve().parent
DATA_DIR = PLUGIN_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
STUDIO_DIR = PLUGIN_DIR / "studio"
DFR_DATA_DIR = Path(os.environ.get("DFR_DATA_DIR", Path.home() / ".local" / "share" / "dfr"))
THEME_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
LANGUAGES = ("de", "en", "es")

SETTINGS = {
    "Language":             {"kind": "choice", "default": "de", "options": list(LANGUAGES)},
    "GpioPin":              {"kind": "pin", "default": ""},
    "LongPressSeconds":     {"kind": "float", "default": 1.5, "min": 0.5, "max": 10},
    "OverlayTimeoutSeconds": {"kind": "float", "default": 10, "min": 2, "max": 300},
    "OnlyEnabledPlaylists": {"kind": "bool", "default": True},
    "ShowFolderPlaylists":  {"kind": "bool", "default": True},
    "FolderCacheSeconds":   {"kind": "float", "default": 30, "min": 0, "max": 3600},
    "VisibleLines":         {"kind": "int", "default": 8, "min": 1, "max": 30},
    "AnchorLine":           {"kind": "int", "default": 4, "min": 1, "max": 30},
    "FontSize":             {"kind": "int", "default": 32, "min": 10, "max": 150},
    "BackgroundColor":      {"kind": "color", "default": "#000000"},
    "BackgroundOpacity":    {"kind": "int", "default": 65, "min": 0, "max": 100},
    "OverlayFileName":      {"kind": "file", "default": "playlist-menu-overlay.json"},
}

_lock = threading.Lock()


def _number(raw, default):
    try:
        value = float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return value if value == value else None  # NaN


def coerce(name, raw):
    spec = SETTINGS[name]
    kind, default = spec["kind"], spec["default"]
    if raw is None:
        return default
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        return True if text in ("true", "1", "yes", "on") else False if text in ("false", "0", "no", "off") else default
    if kind in ("int", "float"):
        value = _number(raw, default)
        if value is None:
            return default
        value = max(spec["min"], min(spec["max"], value))
        return int(round(value)) if kind == "int" else round(value, 2)
    if kind == "choice":
        value = str(raw).strip().lower()
        return value if value in spec["options"] else default
    if kind == "pin":
        text = str(raw).strip()
        value = _number(text, None) if text else None
        if value is None or value != int(value) or not 0 <= value <= 27:
            return ""
        return str(int(value))
    if kind == "color":
        match = HEX_COLOR.match(str(raw).strip())
        if not match:
            return default
        value = match.group(1)
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        return "#" + value[:6].upper()
    if kind == "file":
        value = os.path.basename(str(raw).strip())
        if not value:
            return default
        return value if value.lower().endswith(".json") else value + ".json"
    return str(raw)[:200]


def _read():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}


def _write(stored):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS_FILE.with_suffix(".json.tmp")
    with open(temp, "w", encoding="utf-8") as stream:
        json.dump(stored, stream, indent=1, ensure_ascii=False)
    temp.replace(SETTINGS_FILE)


def migrate(plugin):
    """Erster Start mit der eigenen Seite: Werte der alten Plugins-Seite uebernehmen."""
    with _lock:
        if _read() is not None:
            return
        stored = {}
        for name in SETTINGS:
            if name == "Language":
                continue
            try:
                raw = plugin.get_setting(name, None)
            except Exception:
                raw = None
            if raw is not None and raw != "":
                stored[name] = coerce(name, raw)
        try:
            _write(stored)
        except OSError as exc:
            plugin.log(f"Could not write settings.json: {exc}", level="error")
            return
    if stored:
        plugin.log(f"Settings taken over from the previous version: {', '.join(sorted(stored))}")


def settings():
    with _lock:
        stored = _read() or {}
    return {name: coerce(name, stored.get(name)) for name in SETTINGS}


def save(changes):
    changed = []
    with _lock:
        stored = _read() or {}
        for name, raw in (changes or {}).items():
            if name not in SETTINGS:
                continue
            if SETTINGS[name]["kind"] in ("int", "float") and _number(raw, None) is None:
                continue  # leeres oder ungueltiges Zahlenfeld: alten Wert behalten
            value = coerce(name, raw)
            if stored.get(name) != value:
                stored[name] = value
                changed.append(name)
        if changed:
            _write(stored)
    return changed


# --------------------------------------------------------------------------
# Die Seite
# --------------------------------------------------------------------------

def _theme_id():
    try:
        with open(DFR_DATA_DIR / "webui_theme.json", "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return ""
    if not isinstance(stored, dict):
        return ""
    value = next((str(v) for k, v in stored.items() if k.lower() == "themeid" and v), "")
    return value if THEME_ID.match(value) else ""


def _page_html():
    html = (STUDIO_DIR / "index.html").read_text(encoding="utf-8")
    identifier = _theme_id()
    css = f'@import url("/themes/{identifier}/theme.css") layer(frame-theme);' if identifier else ""
    if identifier:
        html = html.replace("<html", f'<html data-theme="{identifier}"', 1)
    return html.replace('<link rel="stylesheet"', f'<style id="frameTheme">{css}</style>\n  <link rel="stylesheet"', 1)


STUDIO_FILES = {
    "/studio.css": ("studio.css", "text/css; charset=utf-8"),
    "/studio.js": ("studio.js", "application/javascript; charset=utf-8"),
}

_hooks = {"state": lambda: {}, "changed": lambda changed: None, "show": lambda: {}}


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.1, weil der Proxy der Weboberflaeche Verbindungen offen haelt.
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _send(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return {}
        return body if isinstance(body, dict) else {}

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        try:
            if path in ("/", "/index.html"):
                self._send(_page_html().encode("utf-8"), "text/html; charset=utf-8")
                return
            asset = STUDIO_FILES.get(path)
            if asset:
                self._send((STUDIO_DIR / asset[0]).read_bytes(), asset[1])
                return
            if path == "/api/state":
                payload = {"success": True, "settings": settings(), "theme": {"id": _theme_id()}}
                payload.update(_hooks["state"]())
                self._json(payload)
                return
            self._json({"success": False, "error": "Not found"}, 404)
        except Exception as exc:
            self._json({"success": False, "error": str(exc)}, 500)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        body = self._body()
        try:
            if path == "/api/settings":
                changed = save(body)
                if changed:
                    _hooks["changed"](changed)
                self._json({"success": True, "changed": changed, "settings": settings()})
                return
            if path == "/api/show":
                self._json(_hooks["show"]())
                return
            self._json({"success": False, "error": "Not found"}, 404)
        except Exception as exc:
            self._json({"success": False, "error": str(exc)}, 500)


_server = None


def start(plugin, state=None, changed=None, show=None):
    """Seite auf Loopback starten und beim Host anmelden. Wirft nie."""
    global _server
    if state:
        _hooks["state"] = state
    if changed:
        _hooks["changed"] = changed
    if show:
        _hooks["show"] = show
    try:
        _server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=_server.serve_forever, name="settings-page", daemon=True).start()
        url = f"http://127.0.0.1:{_server.server_address[1]}/"
        plugin.register_advanced_settings_page(url)
        plugin.log(f"Plugin page at {url}")
    except Exception as exc:
        try:
            plugin.log(f"Plugin page not available: {exc}", level="warning")
        except Exception:
            pass


def stop(plugin):
    global _server
    try:
        plugin.unregister_advanced_settings_page()
    except Exception:
        pass
    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass
        _server = None
