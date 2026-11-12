#!/usr/bin/env python3
"""Photo Mosaic - der Plugin-Teil des Pakets.

Die Szene "photo-mosaic" setzt ein Foto aus hunderten eigenen kleinen Fotos
zusammen, fährt langsam auf einzelne Kacheln zu und blendet am Ende zum
Original über. Dieses Plugin macht die Vorarbeit, damit der Pi beim Abspielen
nichts rechnen muss:

- Es liest die Fotos einer Quelle (Playlist, ganze Mediendatenbank von
  DynaFrame, Immich) und macht aus bis zu MaxTiles davon kleine Kacheln mit
  ihren Farben (data/tiles, bleibt zwischen den Durchläufen). Die Kacheln
  liegen als wenige große Bögen in data/sheets.
- Für jedes Motiv liefert es das Bild in Bildschirmgröße und die Farben je
  Zelle des Rasters. Welche Kachel wohin kommt, rechnet die Szene selbst
  (das ist im Browser schneller als in Python).
"""

import datetime
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dynaframe_plugin_base import create_plugin  # noqa: E402

import mosaic  # noqa: E402
import sources  # noqa: E402
import own_playlist  # noqa: E402
import texts  # noqa: E402

plugin = create_plugin()

PLUGIN_ID = "PhotoMosaic"
SCENE_ID = "photo-mosaic"            # id in scene.dynamic - nie ändern
PLAYLIST_NAME = "Photo Mosaic"      # in allen Sprachen gleich, englisch (Jans Wunsch, 12.11.2026)
OLD_PLAYLIST_NAMES = ("Foto Mosaik", "Fotomosaik", "Fotomosaico")   # Foto Mosaik bis 0.1.10, die anderen bis 0.1.0
PLAYLIST_NAMES = {"de": PLAYLIST_NAME, "en": PLAYLIST_NAME, "es": PLAYLIST_NAME}
OWN_PLAYLISTS = (PLAYLIST_NAME,) + OLD_PLAYLIST_NAMES
PLUGIN_DIR = Path(plugin.plugin_dir)
DATA_DIR = PLUGIN_DIR / "data"
TILE_DIR = DATA_DIR / "tiles"
UPLOAD_DIR = DATA_DIR / "uploads"
SHEET_DIR = DATA_DIR / "sheets"
TARGET_DIR = DATA_DIR / "targets"

CONNECT_TIMEOUT = 10
KINDS = ("library", "folders", "playlist", "immich_all", "immich_album")
MOTIF_KINDS = ("same", "upload") + KINDS
KEEP_TARGETS = 12
PHOTO_MAX = 40 * 1024 * 1024


def now():
    return time.time()


def as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "ja"}


def as_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def log(text, level="info"):
    plugin.log(text, level=level)


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as exc:
        log(f"Konnte {path.name} nicht lesen: {exc}", "warning")
        return default


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".{threading.get_ident()}.tmp")
    with open(temp, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    temp.replace(path)
    if path.name == "settings.json":
        try:
            os.chmod(path, 0o600)  # enthält den API-Schlüssel
        except OSError:
            pass


def version():
    try:
        return json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))["Version"]
    except (OSError, ValueError, KeyError):
        return "0"


def digest(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


# --------------------------------------------------------------------------
# Einstellungen
# --------------------------------------------------------------------------

SCHEMA = {
    "Language":        {"kind": "choice", "default": "de", "choices": texts.LANGUAGES},
    "TileKind":        {"kind": "choice", "default": "library", "choices": KINDS},
    "TileRef":         {"kind": "ref", "default": ""},
    "MotifKind":       {"kind": "choice", "default": "same", "choices": MOTIF_KINDS},
    "MotifRef":        {"kind": "ref", "default": ""},
    "TileDirs":        {"kind": "dirs", "default": ""},
    "MotifDirs":       {"kind": "dirs", "default": ""},
    "MotifOrder":      {"kind": "choice", "default": "random", "choices": ("random", "newest", "onthisday")},
    "MaxTiles":        {"kind": "int", "default": 1200, "min": 100, "max": 3000},
    "Tiles":           {"kind": "choice", "default": "80", "choices": ("40", "60", "80", "100", "130")},
    "ColorBlend":      {"kind": "int", "default": 30, "min": 0, "max": 70},
    "Ghost":           {"kind": "int", "default": 12, "min": 0, "max": 50},
    "Flow":            {"kind": "choice", "default": "classic", "choices": ("classic", "endless", "tour")},
    "Tempo":           {"kind": "choice", "default": "normal", "choices": ("slow", "normal", "fast")},
    "Captions":        {"kind": "bool", "default": True},
    "ShowCount":       {"kind": "bool", "default": False},
    "PauseSeconds":    {"kind": "int", "default": 3, "min": 0, "max": 120},
    "TourTiles":       {"kind": "int", "default": 5, "min": 0, "max": 100},
    "MinRating":       {"kind": "int", "default": 0, "min": 0, "max": 5},
    "FavoritesOnly":   {"kind": "bool", "default": False},
    "IncludeArchived": {"kind": "bool", "default": False},
    # Weitere Immich-Filter (gelten für Kacheln und Motive aus Immich)
    "People":          {"kind": "ref", "default": ""},
    "Orientation":     {"kind": "choice", "default": "any", "choices": ("any", "landscape", "portrait", "square")},
    "City":            {"kind": "name", "default": ""},
    "State":           {"kind": "name", "default": ""},
    "Country":         {"kind": "name", "default": ""},
    "OnThisDay":       {"kind": "bool", "default": False},
    "LastDays":        {"kind": "int", "default": 0, "min": 0, "max": 36500},
    "TakenAfter":      {"kind": "date", "default": ""},
    "TakenBefore":     {"kind": "date", "default": ""},
    "Make":            {"kind": "name", "default": ""},
    "Model":           {"kind": "name", "default": ""},
    "Lens":            {"kind": "name", "default": ""},
    "Description":     {"kind": "name", "default": ""},
    "OcrText":         {"kind": "name", "default": ""},
    "FileName":        {"kind": "name", "default": ""},
    "WithPeople":      {"kind": "bool", "default": False},
    "CameraOnly":      {"kind": "bool", "default": False},
    "NoScreenshots":   {"kind": "bool", "default": False},
    "NotInAlbum":      {"kind": "bool", "default": False},
    "MinMegapixels":   {"kind": "int", "default": 0, "min": 0, "max": 200},
    "MinFileKB":       {"kind": "int", "default": 0, "min": 0, "max": 100000},
    "SkipAlbums":      {"kind": "ref", "default": ""},
    "SkipTags":        {"kind": "ref", "default": ""},
    "SkipNames":       {"kind": "name", "default": ""},
    # Filter für Fotos aus DynaFrame (Mediendatenbank mit EXIF-Daten)
    "DfMinRating":     {"kind": "int", "default": 0, "min": 0, "max": 5},
    "DfOrientation":   {"kind": "choice", "default": "any", "choices": ("any", "landscape", "portrait", "square")},
    "DfOnThisDay":     {"kind": "bool", "default": False},
    "DfLastDays":      {"kind": "int", "default": 0, "min": 0, "max": 36500},
    "DfAfter":         {"kind": "date", "default": ""},
    "DfBefore":        {"kind": "date", "default": ""},
    "DfPlace":         {"kind": "name", "default": ""},
    "DfMake":          {"kind": "name", "default": ""},
    "DfModel":         {"kind": "name", "default": ""},
    "DfLens":          {"kind": "name", "default": ""},
    "DfText":          {"kind": "name", "default": ""},
    "DfFileName":      {"kind": "name", "default": ""},
    "DfCameraOnly":    {"kind": "bool", "default": False},
    "DfNoScreenshots": {"kind": "bool", "default": False},
    "DfMinMegapixels": {"kind": "int", "default": 0, "min": 0, "max": 200},
    "DfSkipNames":     {"kind": "name", "default": ""},
    "ServerUrl":       {"kind": "url", "default": ""},
    "ApiKey":          {"kind": "secret", "default": ""},
    "WebDavUrl":       {"kind": "url", "default": ""},
    "WebDavUser":      {"kind": "name", "default": ""},
    "WebDavPassword":  {"kind": "secret", "default": ""},
    "Folders":         {"kind": "folders", "default": ""},
    "RefreshHours":    {"kind": "int", "default": 24, "min": 1, "max": 168},
    "PlaylistSeconds": {"kind": "int", "default": 300, "min": 30, "max": 86400},
    "MakePlaylist":        {"kind": "bool", "default": False},
}
SECRETS = [name for name, spec in SCHEMA.items() if spec["kind"] == "secret"]
SCENE_SETTINGS = ("Language", "Tiles", "ColorBlend", "Ghost", "Flow", "Tempo", "Captions", "ShowCount", "MotifKind", "PauseSeconds", "TourTiles")
SETTINGS_FILE = DATA_DIR / "settings.json"
_settings_lock = threading.Lock()


def coerce(name, raw):
    spec = SCHEMA[name]
    kind = spec["kind"]
    if kind == "bool":
        return as_bool(raw, spec["default"])
    if kind == "int":
        return max(spec["min"], min(spec["max"], as_int(raw, spec["default"])))
    if kind == "choice":
        value = str(raw if raw is not None else "").strip()
        return value if value in spec["choices"] else spec["default"]
    if kind == "url":
        return sources.normalize_url(raw)[:300]
    if kind == "ref":
        # Playlist-ID oder Album-IDs von Immich, mehrere mit Komma
        items = raw if isinstance(raw, list) else str(raw or "").split(",")
        chosen = []
        for item in items:
            value = re.sub(r"[^A-Za-z0-9_-]", "", str(item))[:64]
            if value and value not in chosen:
                chosen.append(value)
        return ",".join(chosen[:50])
    if kind == "folders":
        lines = [line.strip() for line in str(raw or "").replace(";", "\n").splitlines()]
        return "\n".join(line for line in lines if line.startswith("/"))[:2000]
    if kind == "dirs":
        items = raw if isinstance(raw, list) else str(raw or "").split("\n")
        chosen = []
        for item in items:
            value = str(item).strip()
            if value.startswith("/") and value not in chosen and "\x00" not in value:
                chosen.append(value[:500])
        return "\n".join(chosen[:200])
    if kind == "date":
        value = str(raw or "").strip()[:10]
        return value if re.match(r"^\d{4}-\d{2}-\d{2}$", value) else ""
    if kind == "name":
        return str(raw or "").strip()[:200]
    return re.sub(r"\s+", "", str(raw or ""))[:400]


def settings():
    stored = read_json(SETTINGS_FILE, {})
    stored = stored if isinstance(stored, dict) else {}
    return {name: coerce(name, stored.get(name, spec["default"])) for name, spec in SCHEMA.items()}


def save_settings(changes):
    with _settings_lock:
        values = settings()
        changed = []
        for name, raw in (changes or {}).items():
            if name not in SCHEMA:
                continue
            value = coerce(name, raw)
            if value != values[name]:
                values[name] = value
                changed.append(name)
        if changed:
            write_json(SETTINGS_FILE, values)
        return changed


def tr(template, **values):
    return texts.t(settings()["Language"], template, **values)


# --------------------------------------------------------------------------
# Die Engine
# --------------------------------------------------------------------------

class EngineError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def engine_base():
    return str(getattr(plugin, "engine_url", "") or "http://localhost:8001").rstrip("/")


def engine_headers():
    headers = {"Content-Type": "application/json", "X-DynaFrame-Plugin": PLUGIN_ID}
    credential = str(getattr(plugin, "plugin_credential", "") or "")
    generation = str(getattr(plugin, "process_generation", "") or "")
    if credential:
        headers["X-Dfr-Plugin-Credential"] = credential
    if generation:
        headers["X-Dfr-Plugin-Generation"] = generation
    return headers


def engine_call(method, path, payload=None):
    try:
        response = requests.request(method, engine_base() + path, json=payload, headers=engine_headers(),
                                    timeout=(CONNECT_TIMEOUT, 120))
    except requests.RequestException as exc:
        raise EngineError(f"{method} {path}: {exc}") from exc
    if response.status_code >= 400:
        raise EngineError(f"{method} {path} lieferte HTTP {response.status_code}", response.status_code)
    body = response.content or b""
    if response.status_code == 204 or not body.strip():
        return None
    try:
        return response.json()
    except ValueError:
        return None


def engine_image(media_id, path=""):
    """Das Vorschaubild der Engine (auf Jans Rahmen 512 x 288)."""
    candidates = []
    if path:
        candidates += [("/media/thumbnail", {"path": path, "purpose": "preview"}),
                       ("/media/thumbnail", {"path": path})]
    if media_id not in (None, "", "None"):
        candidates += [(f"/media/thumbnail/{media_id}", {"purpose": "preview"}),
                       (f"/media/thumbnail/{media_id}", None)]
    failures = []
    for route, params in candidates:
        try:
            response = requests.get(f"{engine_base()}{route}", params=params, headers=engine_headers(),
                                    timeout=(CONNECT_TIMEOUT, 60))
        except requests.RequestException as exc:
            failures.append(f"{route}: {exc}")
            continue
        kind = response.headers.get("Content-Type", "").split(";")[0]
        if response.status_code == 200 and kind.startswith("image/"):
            return response.content
        failures.append(f"{route}: HTTP {response.status_code} {kind}")
    raise sources.SourceError(f"Vorschaubild {media_id}: " + "; ".join(failures))


# ------------------------------------------------------------ WebDAV-Originale

def webdav_dirs():
    seen = []
    for home in (Path.home(), Path("/home/pi")):
        folder = home / ".local/share/dfr/webdav-cache"
        if folder not in seen and folder.is_dir():
            seen.append(folder)
    return seen


_webdav = {"at": 0.0, "index": {}}
_webdav_lock = threading.Lock()


def webdav_cached(path, size):
    """Fotos aus WebDAV (/webdav-media/<Quelle>/...) gibt die Engine nur als
    Vorschaubild mit 512 Pixeln heraus. Das Original legt DynaFrame in
    webdav-cache ab, als <Quelle>-<Hash>.<Endung>; den Hash kennen wir nicht,
    also: gleiche Quelle, gleiche Endung, gleiche Dateigröße (wie Halloween Scare).
    Das Verzeichnis wird nur alle 10 Minuten einmal gelesen."""
    if not path.startswith("/webdav-media/") or not size or size > PHOTO_MAX:
        return None
    with _webdav_lock:
        if now() - _webdav["at"] > 600:
            index = {}
            for folder in webdav_dirs():
                try:
                    entries = list(os.scandir(folder))
                except OSError:
                    continue
                for entry in entries:
                    try:
                        info = entry.stat()
                    except OSError:
                        continue
                    source = entry.name.split("-", 1)[0]
                    key = (source, Path(entry.name).suffix.lower(), info.st_size)
                    old = index.get(key)
                    if old is None or info.st_mtime > old[0]:
                        index[key] = (info.st_mtime, entry.path)
            _webdav.update(at=now(), index=index)
        parts = path.split("/")
        source = parts[2] if len(parts) > 2 else ""
        found = _webdav["index"].get((source, Path(path).suffix.lower(), int(size)))
    return found[1] if found else None


ORIGINAL_DIR = DATA_DIR / "originals"
KEEP_ORIGINALS = 6
_original_lock = threading.Lock()
_original_note = {"at": 0.0}


def webdav_original(path, size):
    """Das Original direkt aus dem WebDAV-Speicher laden (z. B. Nextcloud),
    mit eigenen Zugangsdaten aus den Einstellungen. DynaFrame selbst gibt
    Plugins nur Vorschaubilder, und sein Passwort ist verschlüsselt.
    /webdav-media/<Quelle>/<Pfad> -> <WebDavUrl>/<Pfad>. Die letzten
    Originale bleiben kurz liegen: beim Endlos-Zoom braucht man dasselbe
    Foto erst für die Zoom-Kachel und gleich danach als Motiv."""
    values = settings()
    base, user, password = values["WebDavUrl"], values["WebDavUser"], values["WebDavPassword"]
    if not (base and user and password):
        return None
    parts = path.split("/", 3)
    if len(parts) < 4 or not parts[3]:
        return None
    relative = parts[3]
    name = digest(path) + (Path(relative).suffix.lower() or ".jpg")
    target = ORIGINAL_DIR / name
    with _original_lock:
        if target.is_file():
            os.utime(target)
            return str(target)
        url = base.rstrip("/") + "/" + quote(relative, safe="/")
        try:
            with requests.get(url, auth=(user, password), stream=True, timeout=(CONNECT_TIMEOUT, 120)) as response:
                if response.status_code != 200:
                    raise sources.SourceError(f"HTTP {response.status_code}")
                ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix(".part")
                total = 0
                with open(temp, "wb") as handle:
                    for chunk in response.iter_content(256 * 1024):
                        total += len(chunk)
                        if total > PHOTO_MAX:
                            raise sources.SourceError("zu groß")
                        handle.write(chunk)
                temp.replace(target)
        except Exception as exc:
            try:
                target.with_suffix(".part").unlink()
            except OSError:
                pass
            if now() - _original_note["at"] > 300:   # nicht bei jedem Foto ins Log
                _original_note["at"] = now()
                log(f"WebDAV-Original nicht geladen ({Path(relative).name}): {str(exc)[:160]}", "warning")
            return None
        files = sorted(ORIGINAL_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[KEEP_ORIGINALS:]:
            try:
                old.unlink()
            except OSError:
                pass
        return str(target)


def test_webdav():
    values = settings()
    base, user, password = values["WebDavUrl"], values["WebDavUser"], values["WebDavPassword"]
    if not (base and user and password):
        return {"success": True, "ok": False, "message": tr("Adresse, Benutzer und Passwort fehlen noch.")}
    try:
        response = requests.request("PROPFIND", base.rstrip("/") + "/", auth=(user, password),
                                    headers={"Depth": "0"}, timeout=(CONNECT_TIMEOUT, 30))
    except requests.RequestException as exc:
        return {"success": True, "ok": False, "message": str(exc)[:200]}
    if response.status_code in (200, 207):
        return {"success": True, "ok": True, "message": tr("Verbunden. Motive kommen jetzt in voller Auflösung.")}
    if response.status_code in (401, 403):
        return {"success": True, "ok": False, "message": tr("Benutzer oder Passwort stimmt nicht (HTTP {status}).",
                                                             status=response.status_code)}
    return {"success": True, "ok": False, "message": tr("Der Server antwortet mit HTTP {status}.",
                                                         status=response.status_code)}


_webdav_guess = {"at": 0.0, "value": None}


def webdav_guess():
    """Adresse und Benutzer der WebDAV-Quelle von DynaFrame, zum Vorausfüllen."""
    if now() - _webdav_guess["at"] < 600:
        return _webdav_guess["value"]
    _webdav_guess["at"] = now()
    found = None
    try:
        rows = engine_call("GET", "/media/webdav/sources")
    except EngineError:
        rows = None
    stack = [rows]
    while stack and not found:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            lower = {str(k).lower(): v for k, v in item.items()}
            url = next((v for k, v in lower.items() if "url" in k and isinstance(v, str) and v.startswith("http")), "")
            user = next((v for k, v in lower.items() if "user" in k and isinstance(v, str)), "")
            if url:
                found = {"url": url, "user": user}
            else:
                stack.extend(item.values())
    _webdav_guess["value"] = found
    return found


# --------------------------------------------------------------------------
# Fotos holen
# --------------------------------------------------------------------------

immich = sources.Immich(tr)
dynaframe = sources.DynaFrame(engine_call, EngineError, log, heif=mosaic.HEIF)


def photo_source(row, big):
    """Pfad oder Bytes eines Fotos. big: für Motive und die Zoom-Kachel."""
    key = row["k"]
    if key.startswith("i:"):
        values = settings()
        immich.configure(values["ServerUrl"], values["ApiKey"])
        return immich.image(key[2:], "preview" if big else "thumbnail")
    if key.startswith("f:"):
        return key[2:]
    if key.startswith("d:"):
        media_id, _, path = key[2:].partition("|")
        if path and os.path.isfile(path):
            return path
        cached = webdav_cached(path, row.get("s") or 0)
        if cached:
            return cached
        if big and path.startswith("/webdav-media/"):
            original = webdav_original(path, row.get("s") or 0)
            if original:
                return original
        return engine_image(media_id, path)
    raise sources.SourceError("Unbekannte Quelle")


# --------------------------------------------------------------------------
# Kacheln einlesen
# --------------------------------------------------------------------------

INDEX_FILE = DATA_DIR / "index.json"
FEATURE_FILE = DATA_DIR / "tile_features.json"
_scan_lock = threading.Lock()
_scan_wake = threading.Event()
_scan_stop = threading.Event()
_stop_requested = threading.Event()
_data = {
    "ver": 0,
    "tiles": [],        # [{"k", "f": [12 Farben], "t", "p", "s"}]
    "sheets": 0,
    "motifs": [],       # Zeilen der Motiv-Quelle (leer: wie die Kacheln)
    "busy": False, "at": 0.0, "signature": "",
    "progress": {"done": 0, "total": 0, "phase": ""},
    "status": {"tiles": {}, "motifs": {}},
}


def immich_filters(values):
    split = lambda v: [x for x in v.split(",") if x]
    return {
        "rating": values["MinRating"], "favorites": values["FavoritesOnly"], "archived": values["IncludeArchived"],
        "people": split(values["People"]), "orientation": values["Orientation"],
        "city": values["City"], "state": values["State"], "country": values["Country"],
        "onThisDay": values["OnThisDay"], "lastDays": values["LastDays"],
        "after": values["TakenAfter"], "before": values["TakenBefore"],
        "make": values["Make"], "model": values["Model"], "lensModel": values["Lens"],
        "description": values["Description"], "ocr": values["OcrText"], "originalFileName": values["FileName"],
        "withPeople": values["WithPeople"], "cameraOnly": values["CameraOnly"],
        "noScreenshots": values["NoScreenshots"], "notInAlbum": values["NotInAlbum"],
        "megapixels": values["MinMegapixels"], "minKB": values["MinFileKB"],
        "skipAlbums": split(values["SkipAlbums"]), "skipTags": split(values["SkipTags"]),
        "skipNames": values["SkipNames"],
    }


DF_FILTERS = [name for name in SCHEMA if name.startswith("Df")]


def df_filters(values):
    return {name: values[name] for name in DF_FILTERS}


def df_active(values):
    return any(values[name] != SCHEMA[name]["default"] for name in DF_FILTERS)


def df_keep(row, values, today=None):
    """Passt ein Foto aus DynaFrame zu den Filtern? Daten aus der Mediendatenbank
    (Sterne, Datum, Kamera, Objektiv, Größe, Ort, Titel/Tags). Fotos, die nur
    im Ordner liegen und die Datenbank nicht kennt, fallen bei aktiven Filtern weg."""
    meta = row.get("m") or {}
    if not meta:
        return False
    contains = lambda hay, needle: not needle or needle.lower() in str(hay or "").lower()
    if values["DfMinRating"] and meta.get("r", 0) < values["DfMinRating"]:
        return False
    w, h = meta.get("w") or 0, meta.get("h") or 0
    if values["DfOrientation"] != "any":
        if not (w and h):
            return False
        ratio = w / h
        shape = "square" if 0.9 <= ratio <= 1.1 else "landscape" if ratio > 1 else "portrait"
        if shape != values["DfOrientation"]:
            return False
    if values["DfMinMegapixels"] and (not (w and h) or w * h < values["DfMinMegapixels"] * 1e6):
        return False
    taken = row.get("t") or ""
    day = taken[:10]
    if values["DfAfter"] and (not day or day < values["DfAfter"]):
        return False
    if values["DfBefore"] and (not day or day > values["DfBefore"]):
        return False
    if values["DfLastDays"]:
        since = (datetime.date.today() - datetime.timedelta(days=values["DfLastDays"])).isoformat()
        if not day or day < since:
            return False
    if values["DfOnThisDay"]:
        today = today or datetime.date.today()
        if taken[5:10] != today.strftime("%m-%d"):
            return False
    if not (contains(row.get("p"), values["DfPlace"]) and contains(meta.get("mk"), values["DfMake"])
            and contains(meta.get("md"), values["DfModel"]) and contains(meta.get("ln"), values["DfLens"])
            and contains(meta.get("x"), values["DfText"]) and contains(meta.get("n"), values["DfFileName"])):
        return False
    if values["DfCameraOnly"] and not (meta.get("mk") or meta.get("md")):
        return False
    name = str(meta.get("n") or "").lower()
    if values["DfNoScreenshots"] and (re.search(r"screen ?shot|bildschirmfoto|captura|screen_|scrnli", name)
                                      or name.endswith(".png")):
        return False
    skip = [n.strip().lower() for n in values["DfSkipNames"].split(",") if n.strip()]
    if skip and any(n in name for n in skip):
        return False
    return True


def scan_signature(values):
    # Nur ein Hash: index.json ist für alle lesbar, der API-Key gehört nicht hinein
    return hashlib.sha256(_signature_text(values).encode()).hexdigest()


def _signature_text(values):
    return json.dumps([values["TileKind"], values["TileRef"], values["MotifKind"], values["MotifRef"],
                       values["MaxTiles"], values["TileDirs"], values["MotifDirs"], values["ServerUrl"], values["ApiKey"], values["Folders"],
                       immich_filters(values), df_filters(values)], sort_keys=True)


FILE_META = DATA_DIR / "file_meta.json"
_filter_note = {}   # wie viele Fotos vor den Filtern da waren


def add_meta(rows, values, stop):
    """EXIF-Daten für Fotos, die die Mediendatenbank so nicht kennt (z. B. eine
    Playlist mit Ordner auf einem SMB-Laufwerk, während DynaFrame dieselben Fotos
    über WebDAV kennt). Erst gleicher Pfad, dann gleicher Dateiname und gleiche
    Größe in der Datenbank, sonst die Datei selbst lesen (gemerkt nach Pfad,
    Größe und Änderungszeit)."""
    by_path, by_name = {}, {}
    for lib in library_cached(values, stop):
        meta = lib.get("m")
        if not meta:
            continue
        path = lib["k"].split("|", 1)[1] if lib["k"].startswith("d:") else lib["k"][2:]
        by_path[path] = lib
        by_name.setdefault((os.path.basename(path).lower(), lib.get("s") or 0), lib)
    cache = read_json(FILE_META, {})
    cache = cache if isinstance(cache, dict) else {}
    out, read = [], 0
    for r in rows:
        if r.get("m") or stop.is_set():
            out.append(r)
            continue
        path = r["k"].split("|", 1)[1] if r["k"].startswith("d:") else r["k"][2:]
        size = r.get("s") or 0
        if not size and os.path.isfile(path):
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
        lib = by_path.get(path) or by_name.get((os.path.basename(path).lower(), size))
        if lib:
            out.append(dict(r, m=lib["m"], t=r.get("t") or lib.get("t") or "", p=r.get("p") or lib.get("p") or ""))
            continue
        if os.path.isfile(path):
            try:
                stamp = f"{size}:{int(os.path.getmtime(path))}"
            except OSError:
                stamp = ""
            hit = cache.get(path)
            if not hit or hit.get("v") != stamp:
                meta, taken = mosaic.file_meta(path)
                hit = {"v": stamp, "m": meta, "t": taken}
                cache[path] = hit
                read += 1
            if hit.get("m"):
                out.append(dict(r, m=hit["m"], t=r.get("t") or hit.get("t") or ""))
                continue
        out.append(r)
    if read:
        write_json(FILE_META, cache)
        log(f"EXIF aus {read} Dateien gelesen.")
    return out


def collect(kind, ref, values, stop, dirs=None):
    rows = collect_raw(kind, ref, values, stop, dirs)
    if kind in ("library", "folders", "playlist") and df_active(values):
        if any(not r.get("m") for r in rows):
            rows = add_meta(rows, values, stop)
        before = len(rows)
        rows = [r for r in rows if df_keep(r, values)]
        log(f"DynaFrame-Filter: {len(rows)} von {before} Fotos passen.")
        _filter_note[kind] = before
    # Die EXIF-Daten brauchen wir nur zum Filtern, nicht im Index
    return [{k: v for k, v in r.items() if k != "m"} for r in rows]


def collect_raw(kind, ref, values, stop, dirs=None):
    if kind in ("immich_all", "immich_album"):
        immich.configure(values["ServerUrl"], values["ApiKey"])
        albums = [a for a in ref.split(",") if a] if kind == "immich_album" else None
        if kind == "immich_album" and not albums:
            raise sources.SourceError(tr("Wähle ein Album."))
        return immich.photos(stop, albums, immich_filters(values))
    if kind == "upload":
        rows = upload_rows()
        if not rows:
            raise sources.SourceError(tr("Lade auf der Plugin-Seite mindestens ein Foto hoch."))
        return rows
    if kind == "playlist":
        ids = [i for i in ref.split(",") if i]
        if not ids:
            raise sources.SourceError(tr("Wähle eine Playlist."))
        out, seen, gone = [], set(), 0
        for playlist_id in ids:
            try:
                rows = dynaframe.playlist(playlist_id, stop)
            except EngineError as exc:
                if exc.status == 404:
                    gone += 1
                    continue
                raise sources.SourceError(tr("DynaFrame antwortet nicht: {exc}", exc=exc)) from exc
            for row in rows:
                if row["k"] not in seen:
                    seen.add(row["k"])
                    out.append(row)
        if gone == len(ids):
            raise sources.SourceError(tr("Die Playlist gibt es nicht mehr."))
        return out
    if kind == "folders":
        chosen = set(dirs or [])
        if not chosen:
            raise sources.SourceError(tr("Hak mindestens einen Ordner an."))
        return [row for row in library_cached(values, stop) if row_dir(row) in chosen]
    try:
        return dynaframe.library([f for f in values["Folders"].splitlines() if f], stop)
    except EngineError as exc:
        raise sources.SourceError(tr("DynaFrame antwortet nicht: {exc}", exc=exc)) from exc


_library = {"at": 0.0, "rows": [], "folders": ""}
_library_lock = threading.Lock()


def library_cached(values, stop=None):
    """Die ganze Mediendatenbank (für die Ordnerliste), 10 Minuten gemerkt."""
    with _library_lock:
        if now() - _library["at"] > 600 or _library["folders"] != values["Folders"]:
            rows = dynaframe.library([f for f in values["Folders"].splitlines() if f], stop or threading.Event())
            _library.update(at=now(), rows=rows, folders=values["Folders"])
        return _library["rows"]


def row_dir(row):
    key = row["k"]
    path = key.split("|", 1)[1] if key.startswith("d:") else key[2:]
    return os.path.dirname(path)


def folder_label(path):
    """/webdav-media/<Quelle>/Bilder/X -> WebDAV: Bilder/X"""
    if path.startswith("/webdav-media/"):
        parts = path.split("/", 3)
        return "WebDAV: " + (parts[3] if len(parts) > 3 else "/")
    return path


_folders_job = {"thread": None, "error": ""}


def list_folders():
    """Die Ordner aus der Mediendatenbank. Das Lesen dauert auf dem Pi mit
    tausenden Fotos eine Weile; es läuft im Hintergrund und die Seite fragt
    alle paar Sekunden nach (loading: true), statt die Anfrage festzuhalten."""
    # Ohne Sperre lesen: während des Einlesens hält library_cached() sie lange
    fresh = now() - _library["at"] <= 600 and _library["folders"] == settings()["Folders"]
    rows = _library["rows"] if fresh else None
    if rows is None:
        job = _folders_job["thread"]
        if job is None or not job.is_alive():
            if _folders_job["error"]:
                error, _folders_job["error"] = _folders_job["error"], ""
                return {"success": False, "error": error}

            def work():
                try:
                    library_cached(settings())
                except Exception as exc:  # Engine weg, Zeitüberschreitung
                    _folders_job["error"] = tr("DynaFrame antwortet nicht: {exc}", exc=exc)
            _folders_job["thread"] = threading.Thread(target=work, daemon=True)
            _folders_job["thread"].start()
        return {"success": True, "loading": True}
    counts = {}
    for row in rows:
        folder = row_dir(row)
        counts[folder] = counts.get(folder, 0) + 1
    folders = [{"id": f, "name": folder_label(f), "count": n} for f, n in counts.items()]
    return {"success": True, "folders": sorted(folders, key=lambda f: f["name"].lower())}


# ------------------------------------------------------------ eigene Motive

UPLOAD_MAX = 40 * 1024 * 1024
UPLOAD_SIDE = 3200
UPLOAD_ID = re.compile(r"^[0-9a-f]{20}$")


def upload_rows():
    rows = []
    for path in sorted(UPLOAD_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime):
        meta = read_json(path.with_suffix(".json"), {})
        rows.append({"k": "f:" + str(path), "t": meta.get("t") or "", "p": "", "s": 0, "u": path.stem,
                     "n": meta.get("n") or ""})
    return rows


def save_upload(data, name):
    if not data:
        return {"success": False, "error": tr("Die Datei ist leer.")}
    if len(data) > UPLOAD_MAX:
        return {"success": False, "error": tr("Die Datei ist zu groß.")}
    try:
        image = mosaic.open_image(bytes(data), UPLOAD_SIDE)
        taken = mosaic.taken_date(bytes(data))
        image.thumbnail((UPLOAD_SIDE, UPLOAD_SIDE), mosaic.Image.LANCZOS)
    except Exception as exc:
        log(f"Hochladen: {str(exc)[:160]}", "warning")
        return {"success": False, "error": tr("Das ist kein Foto, das das Plugin lesen kann.")}
    ident = digest(hashlib.sha256(data).hexdigest())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / f"{ident}.jpg"
    image.save(target, "JPEG", quality=90)
    write_json(target.with_suffix(".json"), {"n": str(name or "")[:120], "t": taken})
    _order["ver"] = -1   # Reihenfolge neu mischen
    return {"success": True, "id": ident}


def delete_upload(ident):
    if not UPLOAD_ID.match(str(ident or "")):
        return {"success": False}
    for suffix in (".jpg", ".json"):
        try:
            (UPLOAD_DIR / f"{ident}{suffix}").unlink()
        except OSError:
            pass
    _order["ver"] = -1
    return {"success": True}


def upload_thumb(ident):
    if not UPLOAD_ID.match(str(ident or "")):
        return None
    path = UPLOAD_DIR / f"{ident}.jpg"
    if not path.is_file():
        return None
    import io
    with mosaic.Image.open(path) as image:
        image.thumbnail((320, 320))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=80)
    return buffer.getvalue()


def tile_file(key):
    return TILE_DIR / f"{digest(key)}.jpg"


def publish(tiles, motifs, values, final):
    """Neue Bögen schreiben und den Index tauschen."""
    ver = _data["ver"] + 1
    count = (len(tiles) + mosaic.PER_SHEET - 1) // mosaic.PER_SHEET
    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    paths = [SHEET_DIR / f"{ver}-{n}.jpg" for n in range(count)]
    mosaic.build_sheets([tile_file(t["k"]) for t in tiles], paths)
    with _scan_lock:
        _data.update(ver=ver, tiles=tiles, sheets=count, motifs=motifs, at=now() if final else _data["at"],
                     signature=scan_signature(values) if final else _data["signature"])
    for old in SHEET_DIR.glob("*.jpg"):
        if not old.name.startswith(f"{ver}-"):
            try:
                old.unlink()
            except OSError:
                pass
    write_json(INDEX_FILE, {"ver": ver, "tiles": tiles, "sheets": count, "motifs": motifs,
                            "at": _data["at"], "signature": _data["signature"]})


def scan(reason=""):
    values = settings()
    with _scan_lock:
        if _data["busy"]:
            return
        _data["busy"] = True
        _scan_stop.clear()
    log(f"Lese die Fotos ein{' - ' + reason if reason else ''}.")
    started = now()
    stop = _scan_stop
    progress = _data["progress"]
    try:
        progress.update(done=0, total=0, phase="list")
        try:
            _filter_note.clear()
            candidates = collect(values["TileKind"], values["TileRef"], values, stop,
                                 values["TileDirs"].splitlines())
            _data["status"]["tiles"] = {"state": "ok", "total": len(candidates), "error": "",
                                        "before": _filter_note.get(values["TileKind"], 0)}
        except (sources.SourceError, EngineError) as exc:
            _data["status"]["tiles"] = {"state": "error", "total": 0, "error": str(exc)}
            log(f"Kacheln: {exc}", "warning")
            return
        motifs = []
        if values["MotifKind"] != "same":
            try:
                motifs = collect(values["MotifKind"], values["MotifRef"], values, stop,
                                 values["MotifDirs"].splitlines())
                _data["status"]["motifs"] = {"state": "ok", "total": len(motifs), "error": ""}
            except (sources.SourceError, EngineError) as exc:
                _data["status"]["motifs"] = {"state": "error", "total": 0, "error": str(exc)}
                log(f"Motive: {exc}", "warning")
        else:
            _data["status"]["motifs"] = {}
        if stop.is_set():
            return

        # Welche Fotos Kacheln werden: die bisherigen behalten, der Rest zufällig.
        by_key = {row["k"]: row for row in candidates}
        previous = [t for t in _data["tiles"] if t["k"] in by_key and tile_file(t["k"]).is_file()]
        chosen = {t["k"] for t in previous}
        pool = [row for row in candidates if row["k"] not in chosen]
        random.shuffle(pool)
        features = read_json(FEATURE_FILE, {})
        features = features if isinstance(features, dict) else {}
        tiles = []
        for t in previous[:values["MaxTiles"]]:
            fresh = dict(by_key[t["k"]], f=t["f"])
            tiles.append(fresh)
        TILE_DIR.mkdir(parents=True, exist_ok=True)
        need = values["MaxTiles"] - len(tiles)
        progress.update(done=len(tiles), total=min(values["MaxTiles"], len(candidates)), phase="tiles")
        failures, made, last_publish = 0, 0, now()
        first_run = not _data["tiles"]
        for row in pool:
            if need <= 0 or stop.is_set() or _stop_requested.is_set():
                break
            name = digest(row["k"])
            feat = features.get(name)
            if feat is None or not tile_file(row["k"]).is_file():
                try:
                    data, feat = mosaic.tile(photo_source(row, big=False))
                    tile_file(row["k"]).write_bytes(data)
                    features[name] = feat
                    made += 1
                except Exception as exc:  # kaputte Datei, fehlendes Format, Netz
                    failures += 1
                    if failures <= 5:
                        log(f"Kachel übersprungen ({row['k'][:80]}): {str(exc)[:160]}", "warning")
                    continue
                time.sleep(0.005)   # den Rahmen nicht ausbremsen
            tiles.append(dict(row, f=feat))
            need -= 1
            progress["done"] = len(tiles)
            if made and made % 100 == 0:
                write_json(FEATURE_FILE, features)
            # Beim allerersten Durchlauf schon mal zeigen, was da ist
            if first_run and len(tiles) >= 150 and now() - last_publish > 60:
                publish(list(tiles), motifs, values, final=False)
                last_publish = now()
        # Kacheln, die keiner mehr braucht, aufräumen
        keep = {digest(t["k"]) for t in tiles}
        for name in [n for n in features if n not in keep]:
            features.pop(name, None)
        for old in TILE_DIR.glob("*.jpg"):
            if old.stem not in keep:
                try:
                    old.unlink()
                except OSError:
                    pass
        write_json(FEATURE_FILE, features)
        if stop.is_set() or _stop_requested.is_set():
            log("Einlesen abgebrochen.")
            return
        if not tiles:
            _data["status"]["tiles"]["state"] = "empty"
            log("Keine Fotos für Kacheln gefunden.", "warning")
            # Nicht mit den alten Kacheln weiterzeigen (z. B. aus einer früheren Quelle)
            publish([], [], values, final=True)
            return
        progress.update(phase="sheets")
        publish(tiles, motifs, values, final=True)
        log(f"{len(tiles)} Kacheln aus {len(candidates)} Fotos ({made} neu, {failures} übersprungen, "
            f"{now() - started:.0f} s).")
    finally:
        progress.update(phase="")
        with _scan_lock:
            _data["busy"] = False


def load_index():
    stored = read_json(INDEX_FILE, {})
    if isinstance(stored, dict) and isinstance(stored.get("tiles"), list):
        ver = as_int(stored.get("ver"), 1)
        if all((SHEET_DIR / f"{ver}-{n}.jpg").is_file() for n in range(as_int(stored.get("sheets"), 0))):
            _data.update(ver=ver, tiles=stored["tiles"], sheets=as_int(stored.get("sheets"), 0),
                         motifs=stored.get("motifs") or [], at=stored.get("at") or 0.0,
                         signature=stored.get("signature") or "")


def rename_playlist(playlist_id, name):
    """Nur den Namen ändern: die Playlist erst lesen und vollständig zurückschreiben,
    damit PUT nichts anderes (Beschreibung, Einstellungen) leert."""
    row = engine_call("GET", f"/playlists/{playlist_id}")
    row = (row.get("playlist") if isinstance(row, dict) and isinstance(row.get("playlist"), dict) else row)
    if not isinstance(row, dict) or str(row.get("id")) != str(playlist_id):
        raise EngineError("Playlist nicht lesbar")
    body = {k: v for k, v in row.items() if k not in ("items", "itemCount", "createdAt", "updatedAt")}
    body["name"] = name
    engine_call("PUT", f"/playlists/{playlist_id}", body)


def rename_old_playlist():
    """Eine Playlist mit altem Namen (Foto Mosaik, Fotomosaik, Fotomosaico) bekommt den englischen."""
    try:
        for row in dynaframe.playlists():
            if row["name"] in OLD_PLAYLIST_NAMES:
                rename_playlist(row["id"], PLAYLIST_NAME)
                log(f"Playlist {row['name']} in {PLAYLIST_NAME} umbenannt.")
    except EngineError as exc:
        log(f"Alte Playlist nicht umbenannt: {exc}", "warning")


def scan_loop():
    rename_old_playlist()
    while not _stop_requested.is_set():
        values = settings()
        due = now() - _data["at"] >= values["RefreshHours"] * 3600
        if due or _data["signature"] != scan_signature(values):
            scan("geplant" if due else "Einstellungen")
        _scan_wake.wait(60)
        _scan_wake.clear()


def rescan_now():
    if _data["busy"]:
        _scan_stop.set()
    _data["at"] = 0.0
    _scan_wake.set()
    return {"success": True, "message": tr("Die Fotos werden neu eingelesen.")}


# --------------------------------------------------------------------------
# Motive
# --------------------------------------------------------------------------

_order = {"ver": -1, "bag": [], "newest": 0, "day": "", "today": [], "pos": 0}
_order_lock = threading.Lock()


def motif_rows():
    if settings()["MotifKind"] == "upload":
        return upload_rows()   # gleich da, ohne neues Einlesen
    return _data["motifs"] or _data["tiles"]


def pick_motif():
    rows = motif_rows()
    if not rows:
        return None
    mode = settings()["MotifOrder"]
    with _order_lock:
        if _order["ver"] != _data["ver"] or _order.get("n") != len(rows):
            _order.update(ver=_data["ver"], n=len(rows), bag=[], day="", newest=0)
        if mode == "newest":
            dated = sorted((r for r in rows if r.get("t")), key=lambda r: r["t"], reverse=True)[:60]
            if dated:
                row = dated[_order["newest"] % len(dated)]
                _order["newest"] += 1
                return row
        if mode == "onthisday":
            today = datetime.date.today()
            if _order["day"] != today.isoformat():
                near = []
                for row in rows:
                    taken = row.get("t") or ""
                    try:
                        when = datetime.date(today.year, int(taken[5:7]), int(taken[8:10]))
                        if int(taken[:4]) >= today.year:
                            continue
                    except ValueError:
                        continue
                    diff = abs((when - today).days)
                    if min(diff, 365 - diff) <= 3:
                        near.append(row)
                random.shuffle(near)
                _order.update(day=today.isoformat(), today=near, pos=0)
            if _order["today"]:
                row = _order["today"][_order["pos"] % len(_order["today"])]
                _order["pos"] += 1
                return row
        if not _order["bag"]:
            _order["bag"] = list(range(len(rows)))
            random.shuffle(_order["bag"])
        index = _order["bag"].pop()
        return rows[index] if index < len(rows) else rows[0]


_target_lock = threading.Lock()


def prune_targets():
    files = sorted((p for p in TARGET_DIR.glob("*.jpg") if not p.stem.endswith("-full")), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[KEEP_TARGETS:]:
        for path in (old, old.with_suffix(".json"), old.with_name(old.stem + "-full.jpg")):
            try:
                path.unlink()
            except OSError:
                pass


def next_motif(query):
    width = max(160, min(2560, as_int((query.get("w") or ["1280"])[0], 1280)))
    cols = max(8, min(200, as_int((query.get("cols") or ["80"])[0], 80)))
    rows_n = max(8, min(200, as_int((query.get("rows") or ["45"])[0], 45)))
    ver = as_int((query.get("v") or ["-1"])[0], -1)
    tile_index = as_int((query.get("tile") or ["-1"])[0], -1)
    screen_w = max(160, min(2560, as_int((query.get("sw") or [str(width)])[0], width)))
    screen_h = max(160, min(2560, as_int((query.get("sh") or [str(width)])[0], width)))
    values = settings()
    hd = "hd" if values["WebDavPassword"] and values["WebDavUrl"] else "sd"   # neu rechnen, sobald Originale kommen
    tries = []
    if tile_index >= 0 and ver == _data["ver"] and tile_index < len(_data["tiles"]):
        tries.append(_data["tiles"][tile_index])
    for _ in range(4):
        row = pick_motif()
        if row is not None:
            tries.append(row)
    for row in tries:
        ident = digest(f"{row['k']}|{width}|{cols}|{rows_n}|{screen_w}x{screen_h}|{hd}")
        image_path = TARGET_DIR / f"{ident}.jpg"
        full_path = TARGET_DIR / f"{ident}-full.jpg"
        meta_path = TARGET_DIR / f"{ident}.json"
        try:
            with _target_lock:   # nur ein großes Bild auf einmal, der Pi hat wenig Speicher
                want_full = "sw" in query   # ganzes Foto ohne Zuschnitt, nur auf Wunsch der Szene
                if not (image_path.is_file() and meta_path.is_file() and (full_path.is_file() or not want_full)):
                    data, cells, size, full = mosaic.target(photo_source(row, big=True), width, cols, rows_n,
                                                            (screen_w, screen_h) if want_full else None)
                    TARGET_DIR.mkdir(parents=True, exist_ok=True)
                    image_path.write_bytes(data)
                    if full:
                        full_path.write_bytes(full)
                    write_json(meta_path, {"cells": cells, "w": size[0], "h": size[1]})
                    prune_targets()
                else:
                    os.utime(image_path)
            meta = read_json(meta_path, {})
            return {"success": True, "id": ident, "cols": cols, "rows": rows_n, "cells": meta.get("cells"),
                    "w": meta.get("w"), "h": meta.get("h"), "taken": row.get("t") or "", "place": row.get("p") or "",
                    "own": bool(row.get("u"))}
        except Exception as exc:
            log(f"Motiv übersprungen ({row['k'][:80]}): {str(exc)[:160]}", "warning")
            continue
    return {"success": False, "error": "no motif"}


_zoom_cache = OrderedDict()
_zoom_lock = threading.Lock()


def zoom_bytes(query):
    ver = as_int((query.get("v") or ["-1"])[0], -1)
    index = as_int((query.get("i") or ["-1"])[0], -1)
    if ver != _data["ver"] or not 0 <= index < len(_data["tiles"]):
        return None
    row = _data["tiles"][index]
    with _zoom_lock:
        if row["k"] in _zoom_cache:
            _zoom_cache.move_to_end(row["k"])
            return _zoom_cache[row["k"]]
    try:
        data = mosaic.zoom_tile(photo_source(row, big=True))
    except Exception as exc:
        log(f"Zoom-Kachel: {str(exc)[:160]}", "warning")
        return None
    with _zoom_lock:
        _zoom_cache[row["k"]] = data
        while len(_zoom_cache) > 4:
            _zoom_cache.popitem(last=False)
    return data


# --------------------------------------------------------------------------
# Playlist für die Szene
# --------------------------------------------------------------------------

def find_scene():
    try:
        row = engine_call("GET", f"/dynamic-scenes/{SCENE_ID}")
    except EngineError:
        row = None
    if isinstance(row, dict) and row.get("id") is not None:
        return row
    return None


OWN = own_playlist.OwnPlaylist(
    state_file=DATA_DIR / "own_playlist.json",
    names=OWN_PLAYLISTS,
    name=lambda: PLAYLIST_NAME,
    description=lambda: tr("Deine Fotos, zusammengesetzt aus hunderten deiner Fotos."),
    scene_id=lambda: (find_scene() or {}).get("id"),
    seconds=lambda: settings()["PlaylistSeconds"],
    wanted=lambda: settings()["MakePlaylist"],
    set_wanted=lambda on: save_settings({"MakePlaylist": on}),
    engine_call=engine_call,
    language=lambda: settings()["Language"],
    log=lambda text, level="info": log(text, level),
)


def make_playlist():
    """Aktion „Playlist anlegen“ auf der Plugins-Seite: stellt „Eine Playlist dafür“ auf Ja."""
    return OWN.create_now()


# --------------------------------------------------------------------------
# Was die Szene und die Seite bekommen
# --------------------------------------------------------------------------

def scene_payload(query):
    values = settings()
    have = as_int((query.get("v") or ["-1"])[0], -1)
    payload = {
        "success": True,
        "ver": _data["ver"],
        "settings": {k: values[k] for k in SCENE_SETTINGS},
        "count": len(_data["tiles"]),
        "sheets": _data["sheets"],
        "grid": mosaic.SHEET_GRID,
        "tile": mosaic.TILE,
        "busy": _data["busy"],
        "progress": dict(_data["progress"]),
    }
    if have != _data["ver"]:
        payload["tiles"] = [[t["f"], (t.get("t") or "")[:10], t.get("p") or ""] for t in _data["tiles"]]
    return payload


DFR_DATA_DIR = Path(os.environ.get("DFR_DATA_DIR", Path.home() / ".local" / "share" / "dfr"))
THEME_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def theme_id():
    stored = read_json(DFR_DATA_DIR / "webui_theme.json", {})
    if not isinstance(stored, dict):
        return ""
    value = next((str(v) for k, v in stored.items() if k.lower() == "themeid" and v), "")
    return value if THEME_ID.match(value) else ""


def state_payload():
    values = settings()
    uploads = len(upload_rows()) if values["MotifKind"] == "upload" else 0
    public = dict(values)
    for name in SECRETS:
        public[name] = ""
    return {
        "ownPlaylist": OWN.text(),
        "success": True,
        "version": version(),
        "settings": public,
        "secretsSet": {name: bool(values[name]) for name in SECRETS},
        "status": dict(_data["status"], motifs={"state": "ok" if uploads else "empty", "total": uploads, "error": ""})
                  if values["MotifKind"] == "upload" else _data["status"],
        "busy": _data["busy"],
        "progress": dict(_data["progress"]),
        "at": _data["at"],
        "tiles": len(_data["tiles"]),
        "motifs": len(motif_rows()),
        "heif": mosaic.HEIF,
        "webdav": webdav_guess(),
        "theme": {"id": theme_id()},
    }


def test_immich():
    values = settings()
    immich.configure(values["ServerUrl"], values["ApiKey"])
    try:
        info = immich.test()
    except sources.SourceError as exc:
        return {"success": True, "ok": False, "message": str(exc)}
    return {"success": True, "ok": True,
            "message": tr("Verbunden als {user} (Immich {version}).", user=info["user"] or "?",
                          version=info["version"] or "?")}


def list_immich(what):
    values = settings()
    immich.configure(values["ServerUrl"], values["ApiKey"])
    try:
        return {"success": True, what: immich.people() if what == "people" else immich.tags()}
    except sources.SourceError as exc:
        return {"success": False, "error": str(exc)}


def list_albums():
    values = settings()
    immich.configure(values["ServerUrl"], values["ApiKey"])
    try:
        return {"success": True, "albums": immich.albums()}
    except sources.SourceError as exc:
        return {"success": False, "error": str(exc)}


def list_playlists():
    try:
        rows = [p for p in dynaframe.playlists() if p["name"] not in OWN_PLAYLISTS]
        return {"success": True, "playlists": sorted(rows, key=lambda p: str(p["name"]).lower())}
    except EngineError as exc:
        return {"success": False, "error": tr("DynaFrame antwortet nicht: {exc}", exc=exc)}


def page_html():
    html = (PLUGIN_DIR / "studio" / "index.html").read_text(encoding="utf-8")
    identifier = theme_id()
    css = f'@import url("/themes/{identifier}/theme.css") layer(frame-theme);' if identifier else ""
    if identifier:
        html = html.replace("<html", f'<html data-theme="{identifier}"', 1)
    return html.replace('<link rel="stylesheet"', f'<style id="frameTheme">{css}</style>\n  <link rel="stylesheet"', 1)


STUDIO_FILES = {
    "/studio.css": ("studio/studio.css", "text/css; charset=utf-8"),
    "/studio.js": ("studio/studio.js", "application/javascript; charset=utf-8"),
}
SAFE_ID = re.compile(r"^[0-9a-f]{20}$")


class StudioHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        """Das Plugin-Log ist das Log."""

    def _send(self, body, content_type, status=200, cache="no-store", cors=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200, cors=False):
        self._send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                   "application/json; charset=utf-8", status, cors=cors)

    def _drain_body(self):
        length = as_int(self.headers.get("Content-Length"), 0)
        self._raw_body = self.rfile.read(min(length, 48 * 1024 * 1024)) if length > 0 else b""

    def _body(self):
        raw = getattr(self, "_raw_body", b"")
        if not raw:
            return {}
        try:
            body = json.loads(raw.decode("utf-8")) or {}
        except (ValueError, UnicodeDecodeError):
            return {}
        return body if isinstance(body, dict) else {}

    def do_OPTIONS(self):
        self._drain_body()
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                self._send(page_html().encode("utf-8"), "text/html; charset=utf-8")
                return
            asset = STUDIO_FILES.get(path)
            if asset:
                self._send((PLUGIN_DIR / asset[0]).read_bytes(), asset[1])
                return
            if path == "/api/state":
                self._json(state_payload())
                return
            if path == "/api/scene":
                self._json(scene_payload(query), cors=True)
                return
            if path == "/api/sheet":
                ver = as_int((query.get("v") or ["-1"])[0], -1)
                index = as_int((query.get("n") or ["-1"])[0], -1)
                sheet = SHEET_DIR / f"{ver}-{index}.jpg"
                if ver == _data["ver"] and 0 <= index < _data["sheets"] and sheet.is_file():
                    self._send(sheet.read_bytes(), "image/jpeg", cache="private, max-age=86400", cors=True)
                else:
                    self._json({"success": False}, 404, cors=True)
                return
            if path == "/api/next":
                self._json(next_motif(query), cors=True)
                return
            if path == "/api/target":
                ident = (query.get("id") or [""])[0]
                full = (query.get("full") or [""])[0] == "1"
                image = TARGET_DIR / (f"{ident}-full.jpg" if full else f"{ident}.jpg")
                if SAFE_ID.match(ident) and image.is_file():
                    self._send(image.read_bytes(), "image/jpeg", cache="private, max-age=3600", cors=True)
                else:
                    self._json({"success": False}, 404, cors=True)
                return
            if path == "/api/zoom":
                data = zoom_bytes(query)
                if data is None:
                    self._json({"success": False}, 404, cors=True)
                else:
                    self._send(data, "image/jpeg", cache="private, max-age=3600", cors=True)
                return
            if path == "/api/report":
                text = re.sub(r"[\x00-\x1f]", " ", (query.get("m") or [""])[0])[:200]
                if text:
                    log(f"Szene: {text}", "warning")
                self._json({"success": True}, cors=True)
                return
            if path == "/api/albums":
                self._json(list_albums())
                return
            if path == "/api/playlists":
                self._json(list_playlists())
                return
            if path in ("/api/people", "/api/tags"):
                self._json(list_immich(path[5:]))
                return
            if path == "/api/folders":
                self._json(list_folders())
                return
            if path == "/api/uploads":
                self._json({"success": True, "uploads": [{"id": r["u"], "name": r["n"], "taken": r["t"]}
                                                         for r in upload_rows()]})
                return
            if path == "/api/upload":
                data = upload_thumb((query.get("id") or [""])[0])
                if data is None:
                    self._json({"success": False}, 404)
                else:
                    self._send(data, "image/jpeg", cache="private, max-age=86400")
                return
            self._json({"success": False, "error": "Nicht gefunden"}, 404)
        except OSError as exc:
            self._json({"success": False, "error": f"Konnte eine Plugin-Datei nicht lesen: {exc}"}, 500)
        except Exception as exc:  # pragma: no cover
            self._json({"success": False, "error": str(exc)}, 500)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        self._drain_body()
        try:
            if path == "/api/settings":
                body = self._body()
                for name in SECRETS:
                    if name in body and not str(body[name] or "").strip():
                        body.pop(name)
                    elif name in body and str(body[name]).strip() == "-":
                        body[name] = ""
                changed = save_settings(body)
                if "MakePlaylist" in changed:
                    OWN.changed()
                if changed and scan_signature(settings()) != _data["signature"]:
                    rescan_now()
                self._json({"success": True, "changed": changed})
                return
            if path == "/api/refresh":
                self._json(rescan_now())
                return
            if path == "/api/test":
                self._json(test_immich())
                return
            if path == "/api/upload":
                name = unquote(self.headers.get("X-File-Name") or "")
                self._json(save_upload(getattr(self, "_raw_body", b""), name))
                return
            if path == "/api/upload/delete":
                self._json(delete_upload(self._body().get("id")))
                return
            if path == "/api/webdavtest":
                self._json(test_webdav())
                return
            if path == "/api/playlist":
                self._json(make_playlist())
                return
            self._json({"success": False, "error": "Nicht gefunden"}, 404)
        except Exception as exc:  # pragma: no cover
            self._json({"success": False, "error": str(exc)}, 500)


studio_server = None


def start_studio():
    global studio_server
    studio_server = ThreadingHTTPServer(("127.0.0.1", 0), StudioHandler)
    port = studio_server.server_address[1]
    threading.Thread(target=studio_server.serve_forever, name=f"{PLUGIN_ID}-studio", daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    plugin.register_advanced_settings_page(url)
    log(f"Plugin-Seite unter {url}")
    return url


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Starte {PLUGIN_ID} {version()} (HEIC: {'ja' if mosaic.HEIF else 'nein'})")
    plugin.on_action("refresh", lambda _context=None: rescan_now())
    plugin.on_action("playlist", lambda _context=None: make_playlist())
    load_index()
    start_studio()
    plugin.connect_sse()
    plugin.ready()
    try:
        os.nice(10)   # Kacheln machen darf die Wiedergabe nicht stören
    except OSError:
        pass
    threading.Thread(target=scan_loop, name=f"{PLUGIN_ID}-scan", daemon=True).start()
    try:
        while not _stop_requested.is_set():
            _stop_requested.wait(3600)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()


def shutdown():
    _stop_requested.set()
    _scan_stop.set()
    _scan_wake.set()
    try:
        plugin.unregister_advanced_settings_page()
    except Exception:
        pass
    if studio_server is not None:
        try:
            studio_server.shutdown()
            studio_server.server_close()
        except Exception:
            pass
    log(f"{PLUGIN_ID} gestoppt.")


if __name__ == "__main__":
    main()
