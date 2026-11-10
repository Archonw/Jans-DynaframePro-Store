"""Woher die Fotos kommen: DynaFrame selbst (Playlist, ganze Mediendatenbank,
Ordner) oder ein Immich-Server (alle Fotos oder ein Album).

Jede Quelle liefert eine Liste von Zeilen {"k", "t", "p", "s"}:
- k: womit das Plugin das Foto später holt: "i:<asset-id>" bei Immich,
  "d:<id>|<pfad>" für Medien der Engine, "f:<pfad>" für Dateien auf dem Rahmen,
- t: Aufnahmedatum "YYYY-MM-DD..." oder "",
- p: Ort als Text, wenn die Quelle ihn kennt,
- s: Dateigröße in Byte, wenn bekannt (findet WebDAV-Originale im Cache).

Die Engine-API der Mediendatenbank ist nicht dokumentiert; die Wege sind von
der Reisekarte übernommen und auf Jans Rahmen geprüft.
"""

import datetime
import json
import os
import re
import time
from pathlib import Path
import requests

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 60
PAGE_SIZE = 1000
MAX_PHOTOS = 300000

# Was Pillow auf dem Rahmen sicher öffnen kann (HEIC nur mit pillow-heif)
IMAGE_EXT = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
HEIF_EXT = {".heic", ".heif"}


class SourceError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def as_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def short_error(exc):
    text = str(exc)
    for marker in ("Failed to establish a new connection: ", "Read timed out", "Name or service not known"):
        if marker in text:
            tail = text.split(marker, 1)[1] if marker.endswith(": ") else marker
            return tail.split("'))")[0].strip(" )") or marker
    return text[:200]


def image_ext(path, heif=False):
    suffix = Path(str(path)).suffix.lower()
    return suffix in IMAGE_EXT or (heif and suffix in HEIF_EXT)


# --------------------------------------------------------------------------
# Immich
# --------------------------------------------------------------------------

def normalize_url(url):
    url = str(url or "").strip().rstrip("/")
    if url and not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    if url.lower().endswith("/api"):
        url = url[:-4]
    return url


class Immich:
    """Der Zugang zu einem Immich-Server mit API-Schlüssel (wie Immich Slideshow)."""

    def __init__(self, tr):
        self.tr = tr
        self.base = ""
        self.key = ""
        self.session = requests.Session()
        self.visibility = True

    def configure(self, base, key):
        self.base, self.key = normalize_url(base), key

    def call(self, method, path, payload=None, params=None, raw=False, timeout=None):
        if not self.base:
            raise SourceError(self.tr("Trag die Adresse deines Immich-Servers ein."))
        if not self.key:
            raise SourceError(self.tr("Trag einen API-Schlüssel von Immich ein."))
        headers = {"x-api-key": self.key, "Accept": "image/*" if raw else "application/json"}
        try:
            response = self.session.request(method, f"{self.base}/api{path}", json=payload, params=params,
                                            headers=headers, timeout=(CONNECT_TIMEOUT, timeout or READ_TIMEOUT))
        except requests.RequestException as exc:
            raise SourceError(self.tr("Immich ist nicht erreichbar: {exc}", exc=short_error(exc))) from exc
        if response.status_code == 401:
            raise SourceError(self.tr("Immich lehnt den API-Schlüssel ab."), 401)
        if response.status_code == 403:
            raise SourceError(self.tr("Dem API-Schlüssel fehlt eine Berechtigung ({path}).",
                                      path=path.split("?")[0]), 403)
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                detail = body.get("message") if isinstance(body, dict) else ""
                if isinstance(detail, list):
                    detail = "; ".join(str(d) for d in detail)
            except ValueError:
                pass
            raise SourceError(f"{method} {path}: HTTP {response.status_code} {detail or ''}".strip(),
                              response.status_code)
        if raw:
            return response
        if not response.content.strip():
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(self.tr("Unter dieser Adresse antwortet kein Immich-Server.")) from exc

    def test(self):
        me = self.call("GET", "/users/me") or {}
        about = {}
        try:
            about = self.call("GET", "/server/about") or {}
        except SourceError as exc:
            if exc.status in (401, 403):
                raise
        return {"user": me.get("name") or me.get("email") or "", "version": about.get("version") or ""}

    def albums(self):
        found = {}
        for query in ({}, {"shared": "true"}):
            rows = self.call("GET", "/albums", params=query) or []
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict) and row.get("id"):
                    found[row["id"]] = {"id": row["id"], "name": row.get("albumName") or "?",
                                        "count": row.get("assetCount") or 0}
        return sorted(found.values(), key=lambda a: a["name"].lower())

    @staticmethod
    def _place(*parts):
        return ", ".join(p for p in parts if p)[:80]

    def people(self):
        data = self.call("GET", "/people", params={"withHidden": "false", "size": 1000}) or {}
        rows = data.get("people") if isinstance(data, dict) else data
        out = [{"id": r["id"], "name": r.get("name") or ""} for r in rows or []
               if isinstance(r, dict) and r.get("id") and r.get("name")]
        return sorted(out, key=lambda r: r["name"].lower())

    def tags(self):
        rows = self.call("GET", "/tags") or []
        out = [{"id": r["id"], "name": r.get("value") or r.get("name") or "?"} for r in rows
               if isinstance(r, dict) and r.get("id")]
        return sorted(out, key=lambda r: r["name"].lower())

    def _search(self, body, stop, limit):
        """Alle Treffer einer Suche, seitenweise. Gibt die Immich-Einträge zurück."""
        out = []
        page, cursor = 1, None
        while len(out) < limit and not stop.is_set():
            query = dict(body, type="IMAGE", size=PAGE_SIZE)
            if cursor:
                query["cursor"] = cursor
            else:
                query["page"] = page
            data = self.call("POST", "/search/metadata", query, timeout=120) or {}
            assets = data.get("assets") or {}
            items = assets.get("items") or []
            out += [i for i in items if isinstance(i, dict) and i.get("id")]
            cursor = assets.get("nextCursor")
            next_page = assets.get("nextPage")
            if cursor:
                continue
            if next_page and items:
                page = as_int(next_page, page + 1)
                continue
            break
        return out

    def _ids_of(self, field, ids, stop):
        """Alle Asset-IDs in diesen Alben bzw. mit diesen Tags (zum Weglassen)."""
        found = set()
        for one in ids:
            try:
                found.update(i["id"] for i in self._search({field: [one]}, stop, MAX_PHOTOS))
            except SourceError as exc:
                if exc.status != 400:
                    raise
        return found

    def photos(self, stop, album_ids=None, f=None, limit=MAX_PHOTOS):
        """Die Fotos, die zu allen Filtern passen.

        Wie Growing Up: eine Suche je Album und je Person (mehrere IDs
        verknüpft Immich mit UND, wir wollen ODER). Was Immich selbst kann
        (Favoriten, Ort, Kamera, Zeitraum, Beschreibung, Dateiname, in keinem
        Album) macht der Server, den Rest prüfen wir hier: Sterne (>=),
        Ausrichtung, Megapixel, Dateigröße, an diesem Tag, nur mit Personen,
        nur Kamerafotos, Bildschirmfotos und Dateinamen weglassen."""
        f = f or {}
        base = {"withExif": True}
        if f.get("favorites"):
            base["isFavorite"] = True
        if not f.get("archived") and self.visibility:
            base["visibility"] = "timeline"
        for key in ("city", "state", "country", "make", "model", "lensModel", "description", "originalFileName"):
            if f.get(key):
                base[key] = f[key]
        if f.get("ocr"):
            base["ocr"] = f["ocr"]
        if f.get("notInAlbum") and not album_ids:
            base["isNotInAlbum"] = True
        if f.get("withPeople"):
            base["withPeople"] = True
        after, before = f.get("after"), f.get("before")
        if f.get("lastDays"):
            since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(f["lastDays"])))
            after = since.strftime("%Y-%m-%d")
        if after:
            base["takenAfter"] = after + "T00:00:00.000Z"
        if before:
            base["takenBefore"] = before + "T23:59:59.999Z"
        skip = self._ids_of("albumIds", f.get("skipAlbums") or [], stop) if f.get("skipAlbums") else set()
        if f.get("skipTags"):
            skip |= self._ids_of("tagIds", f["skipTags"], stop)
        names_out = [n.strip().lower() for n in str(f.get("skipNames") or "").split(",") if n.strip()]
        today = datetime.date.today()
        found = {}
        for album in album_ids or [None]:
            for person in f.get("people") or [None]:
                body = dict(base)
                if album:
                    body["albumIds"] = [album]
                if person:
                    body["personIds"] = [person]
                try:
                    items = self._search(body, stop, limit - len(found))
                except SourceError as exc:
                    if exc.status == 400 and "visibility" in body:
                        self.visibility = False   # älteres Immich: isArchived statt visibility
                        body.pop("visibility")
                        items = self._search(body, stop, limit - len(found))
                    elif exc.status == 400 and "ocr" in body:
                        raise SourceError(self.tr("Dieses Immich kann nicht nach Text im Bild suchen.")) from exc
                    elif exc.status == 400 and (album or person):
                        continue                  # Album oder Person gibt es nicht mehr
                    else:
                        raise
                for item in items:
                    if self._keep(item, f, skip, names_out, today):
                        exif = item.get("exifInfo") or {}
                        taken = str(item.get("localDateTime") or exif.get("dateTimeOriginal")
                                    or item.get("fileCreatedAt") or "")[:19]
                        found[item["id"]] = {"k": "i:" + item["id"], "t": taken,
                                             "p": self._place(exif.get("city"), exif.get("country")), "s": 0}
                if len(found) >= limit or stop.is_set():
                    break
        return list(found.values())[:limit]

    @staticmethod
    def _keep(item, f, skip, names_out, today):
        if item.get("isTrashed") or item.get("type") not in (None, "IMAGE") or item["id"] in skip:
            return False
        if item.get("visibility") in ("hidden", "locked"):
            return False
        if not f.get("archived") and (item.get("isArchived") or item.get("visibility") == "archive"):
            return False
        exif = item.get("exifInfo") or {}
        if f.get("rating") and as_int(exif.get("rating"), 0) < int(f["rating"]):
            return False
        name = str(item.get("originalFileName") or "").lower()
        if f.get("noScreenshots") and (re.search(r"screen ?shot|bildschirmfoto|captura|screen_|scrnli", name)
                                       or name.endswith(".png")):
            return False
        if names_out and any(n in name for n in names_out):
            return False
        if f.get("cameraOnly") and not (exif.get("make") or exif.get("model")):
            return False
        if f.get("withPeople") and not item.get("people"):
            return False
        width, height = as_int(exif.get("exifImageWidth"), 0), as_int(exif.get("exifImageHeight"), 0)
        if str(exif.get("orientation") or "") in ("5", "6", "7", "8"):
            width, height = height, width
        if f.get("orientation") in ("landscape", "portrait", "square") and width and height:
            ratio = width / height
            shape = "square" if 0.9 <= ratio <= 1.1 else "landscape" if ratio > 1 else "portrait"
            if shape != f["orientation"]:
                return False
        if f.get("megapixels") and width and height and width * height < float(f["megapixels"]) * 1e6:
            return False
        if f.get("minKB") and as_int(exif.get("fileSizeInByte"), 0) and \
                as_int(exif.get("fileSizeInByte"), 0) < int(f["minKB"]) * 1024:
            return False
        if f.get("onThisDay"):
            taken = str(item.get("localDateTime") or exif.get("dateTimeOriginal") or "")
            if taken[5:10] != today.strftime("%m-%d"):
                return False
        return True

    def image(self, asset_id, size="preview"):
        """Bild von Immich: "thumbnail" (~250 px) für Kacheln, "preview" (~1440 px) für Motive."""
        response = self.call("GET", f"/assets/{asset_id}/thumbnail", params={"size": size}, raw=True,
                             timeout=60)
        kind = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
        if not kind.startswith("image/"):
            raise SourceError(f"Immich lieferte {kind} statt eines Bildes")
        return response.content


# --------------------------------------------------------------------------
# DynaFrame: Playlists, ganze Mediendatenbank, Ordner
# --------------------------------------------------------------------------

PATH_KEYS = ("filePath", "path", "fullPath", "localPath", "mediaPath", "sourcePath")
PLACE_KEYS = ("locationName", "location", "placeName")
TAKEN_KEYS = ("dateTaken", "takenAt", "dateTimeOriginal", "captureDate", "exifDate", "takenDate")
SIZE_KEYS = ("fileSize", "size", "fileSizeBytes", "length", "sizeBytes")
TYPE_KEYS = ("mediaType", "type", "kind")
SKIP_DIRS = {"@eaDir", "#recycle", ".thumbnails", "__pycache__", "node_modules", "lost+found", ".Trash-1000"}


def _rows(data):
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "media", "files", "data", "rows"):
            if isinstance(data.get(key), list):
                return [r for r in data[key] if isinstance(r, dict)]
    return []


def _find(row, keys, depth=0):
    """Den ersten Wert unter einem der Schlüssel, auch eine Ebene tiefer."""
    for key in keys:
        for name, value in row.items():
            if name.lower() == key.lower() and value not in (None, ""):
                return value
    if depth == 0:
        for value in row.values():
            if isinstance(value, dict):
                found = _find(value, keys, 1)
                if found not in (None, ""):
                    return found
    return None


def _media_folder_ok(path):
    """Nur echte Bilderordner durchsuchen, nie das ganze System."""
    clean = os.path.normpath(path)
    if clean in ("/", "/home", "/media", "/mnt", str(Path.home())) or not os.path.isdir(clean):
        return False
    if clean.startswith(("/opt", "/usr", "/etc", "/proc", "/sys", "/var", "/tmp", "/run", "/boot", "/dev")):
        return False
    return not any(part in clean for part in ("/.local", "/.config", "/.cache"))


def _quick_mix(row):
    """Eine Quick-Mix-Liste von DynaFrame: Typ steht als JSON in description."""
    text = row.get("description")
    if isinstance(text, str) and "quick_mix" in text.replace(" ", "").lower():
        try:
            data = json.loads(text)
        except ValueError:
            return True
        return str((data or {}).get("Type") or (data or {}).get("type") or "").lower() == "quick_mix" \
            if isinstance(data, dict) else True
    return False


class DynaFrame:
    def __init__(self, engine_call, engine_error, log, heif=False):
        self.engine_call = engine_call
        self.EngineError = engine_error
        self.log = log
        self.heif = heif
        self.library_way = ""
        self.logged_keys = set()

    def _log_keys(self, what, row):
        if what not in self.logged_keys and isinstance(row, dict):
            self.logged_keys.add(what)
            self.log(f"Engine {what}: Felder " + ", ".join(sorted(row.keys())))

    def playlists(self):
        data = self.engine_call("GET", "/playlists") or []
        rows = _rows(data) if not isinstance(data, list) else [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict) and not rows:
            rows = _rows({"items": data.get("playlists") or []})
        return [{"id": r.get("id"), "name": r.get("name") or "?", "count": r.get("itemCount") or r.get("count")}
                for r in rows if r.get("id") is not None and not _quick_mix(r)]

    def _is_photo(self, row):
        kind = str(_find(row, TYPE_KEYS) or "").lower()
        if kind and any(word in kind for word in ("video", "scene", "dynamic", "web")):
            return False
        path = _find(row, PATH_KEYS)
        return bool(path) and image_ext(path, self.heif)

    def _row(self, row, media_id=None):
        path = str(_find(row, PATH_KEYS) or "")
        if media_id is None:
            media_id = row.get("id")
        key = f"d:{media_id}|{path}" if media_id is not None else f"f:{path}"
        return {"k": key, "t": str(_find(row, TAKEN_KEYS) or "")[:19], "p": str(_find(row, PLACE_KEYS) or "")[:80],
                "s": as_int(_find(row, SIZE_KEYS), 0)}

    def _media_row(self, media_id):
        for path in (f"/media/{media_id}", f"/media/database/{media_id}"):
            try:
                row = self.engine_call("GET", path)
            except self.EngineError:
                continue
            if isinstance(row, dict):
                row = row.get("item") or row.get("media") or row
                if _find(row, PATH_KEYS):
                    return row
        return None

    def _page_through(self, path_for_page, stop):
        rows, seen, page = [], set(), 1
        while page <= 2000 and not stop.is_set():
            data = self.engine_call("GET", path_for_page(page))
            batch = _rows(data)
            fresh = 0
            for row in batch:
                path = _find(row, PATH_KEYS)
                if path and path not in seen:
                    seen.add(path)
                    rows.append(row)
                    fresh += 1
            if not batch or not fresh:
                break
            page += 1
        return rows

    def library_rows(self, stop):
        ways = [
            ("database", lambda p: f"/media/database?page={p}&pageSize=500&limit=500&offset={(p - 1) * 500}"),
            ("search", lambda p: f"/media/database/search?query=&page={p}&pageSize=500&limit=500"
                                 f"&offset={(p - 1) * 500}"),
        ]
        for name, way in ways:
            try:
                rows = self._page_through(way, stop)
            except self.EngineError:
                continue
            rows = [r for r in rows if _find(r, PATH_KEYS)]
            if rows:
                if self.library_way != name:
                    self.library_way = name
                    self._log_keys("Datenbank", rows[0])
                    self.log(f"Mediendatenbank über /media/database ({name}): {len(rows)} Einträge.")
                return rows
        self.library_way = ""
        return []

    def media_folders(self):
        found = []

        def walk(value, depth=0):
            if depth > 4:
                return
            if isinstance(value, dict):
                for name, inner in value.items():
                    if re.search(r"folder|director|librar|media|root|share", name, re.I):
                        walk(inner, depth + 1)
            elif isinstance(value, list):
                for inner in value:
                    walk(inner, depth + 1)
            elif isinstance(value, str) and value.startswith("/") and len(value) < 300:
                if _media_folder_ok(value):
                    found.append(value.rstrip("/"))

        for path in ("/settings/slideshow", "/settings/media", "/media/folders", "/media/directories"):
            try:
                walk(self.engine_call("GET", path))
            except self.EngineError:
                continue
        return list(dict.fromkeys(found))

    def folder_rows(self, folders, stop, seen):
        out = []
        for folder in folders:
            for root, dirs, files in os.walk(folder, followlinks=False):
                if stop.is_set() or len(out) >= MAX_PHOTOS:
                    return out
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
                for name in files:
                    if name.startswith(".") or not image_ext(name, self.heif):
                        continue
                    path = os.path.join(root, name)
                    if path in seen:
                        continue
                    seen.add(path)
                    out.append({"k": f"f:{path}", "t": "", "p": "", "s": 0})
                time.sleep(0.01)
        return out

    def library(self, extra_folders, stop):
        out, seen = [], set()
        for row in self.library_rows(stop):
            if stop.is_set():
                break
            if not self._is_photo(row):
                continue
            seen.add(str(_find(row, PATH_KEYS)))
            out.append(self._row(row))
        folders = list(dict.fromkeys(list(extra_folders) + self.media_folders()))
        if not folders and not seen:
            home = Path.home() / "Pictures"
            folders = [str(home)] if home.is_dir() else []
        out += self.folder_rows([f for f in folders if os.path.isdir(f)], stop, seen)
        return out

    def playlist(self, playlist_id, stop):
        items = _rows(self.engine_call("GET", f"/playlists/{playlist_id}/items") or [])
        if items:
            self._log_keys("Playlist-Eintrag", items[0])
        by_id, by_path = None, None
        out, unresolved = [], 0
        for item in items:
            if stop.is_set():
                break
            folder = _find(item, ("directoryPath", "folderPath", "directory", "folder"))
            if isinstance(folder, str) and folder.startswith("/"):
                out += self.folder_rows([folder], stop, set())
                continue
            media = item.get("media") if isinstance(item.get("media"), dict) else {}
            media_id = item.get("mediaFileId") or item.get("mediaId") or media.get("id")
            if item.get("dynamicSceneId") or (media_id is None and not _find(item, PATH_KEYS)):
                continue
            path = _find(item, PATH_KEYS) or _find(media, PATH_KEYS)
            row = None
            if path and (media or _find(item, PATH_KEYS)):
                row = media if _find(media, PATH_KEYS) else item
            if row is None or not _find(row, TAKEN_KEYS):
                # Die Mediendatenbank kennt Datum, Ort und Größe
                if by_id is None:
                    by_id, by_path = {}, {}
                    for lib in self.library_rows(stop):
                        if lib.get("id") is not None:
                            by_id[str(lib["id"])] = lib
                        lib_path = _find(lib, PATH_KEYS)
                        if lib_path:
                            by_path[str(lib_path)] = lib
                row = (by_id.get(str(media_id)) if media_id is not None else None) or \
                    (by_path.get(str(path)) if path else None) or row
            if row is None and media_id is not None and unresolved < 50:
                row = self._media_row(media_id)
            if row is None:
                unresolved += 1
                continue
            if self._is_photo(row):
                out.append(self._row(row, media_id if media_id is not None else row.get("id")))
        self.log(f"Playlist {playlist_id}: {len(items)} Einträge, {len(out)} Fotos"
                 + (f", {unresolved} nicht gefunden" if unresolved else "") + ".")
        return out

