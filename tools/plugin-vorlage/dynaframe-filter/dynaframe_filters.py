"""Filter für Fotos aus DynaFrame (wie Photo Mosaic 0.1.10) als gemeinsamer Baustein.

DynaFrame liest beim Einlesen selbst EXIF/XMP aus den Fotos und legt es in
seiner Mediendatenbank ab (GET /media/database: rating 0-5, make, model,
width/height, dateTaken, locationName, title/description/tags/keywords,
customMetadata.cameraInfo.LensModel …). Die Sterne kommen auch aus XMP-Sidecars
(foto.jpg.xmp, z. B. von StarSwipe, digiKam, darktable).

WICHTIG (gelernt mit Photo Mosaic 0.1.9 auf Küche): Playlist-Einträge
(/playlists/{id}/items) haben make/width/dateTaken, aber KEIN Feld rating.
Deshalb nie die Daten aus dem Playlist-Eintrag nehmen, sondern immer die Zeile
der Mediendatenbank (über mediaFileId oder Pfad). Das macht Matcher.

Einbau im Plugin (Beispiel in README.md daneben):
    SCHEMA.update(dynaframe_filters.schema(without=...))
    coerce(): Arten int/bool/choice wie gehabt, date/name über dynaframe_filters.coerce()
    scan_signature(): dynaframe_filters.signature(values) mit hineinnehmen
    beim Einlesen einer DynaFrame-Quelle (alle Fotos, Playlist, Ordner):
        if dynaframe_filters.active(values):
            match = dynaframe_filters.Matcher(values, lambda: dynaframe.library_rows(stop),
                                              cache_file=DATA_DIR / "file_meta.json", log=log)
            rows = [r for r in rows if match.keep(key_of(r))]
            match.save(); _data["dfCount"] = match.counts()      # für die Seite
Schlüssel wie in allen unseren Plugins: "d:<mediaId>|<pfad>" oder "f:<pfad>".
"""

import datetime
import json
import os
import re

SCHEMA = {
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
}

# Filter, die ein Datum wählen (Colour Calendar/On This Day wählen die Tage selbst)
WHEN = ("DfOnThisDay", "DfLastDays", "DfAfter", "DfBefore")

PATH_KEYS = ("filePath", "path", "fullPath", "localPath", "file", "filename", "fileName")
_RATING = (re.compile(rb'(?<![\w])(?:xmp|xap|xapR):Rating\s*=\s*["\'](-?\d)'),
           re.compile(rb"<(?:xmp|xap|xapR):Rating>\s*(-?\d)"))
_SCREENSHOT = re.compile(r"screen ?shot|bildschirmfoto|captura|screen_|scrnli")


def schema(without=()):
    return {k: v for k, v in SCHEMA.items() if k not in without}


def coerce(spec, raw):
    """Die Arten date/name; None = nicht zuständig (int/bool/choice macht das Plugin)."""
    if spec["kind"] == "date":
        value = str(raw or "").strip()[:10]
        return value if re.match(r"^\d{4}-\d{2}-\d{2}$", value) else ""
    if spec["kind"] == "name":
        return re.sub(r"\s+", " ", str(raw or "")).strip()[:200]
    return None


def _v(values, name):
    return values.get(name, SCHEMA[name]["default"])


def signature(values):
    return {name: _v(values, name) for name in SCHEMA}


def active(values):
    return any(_v(values, name) != spec["default"] for name, spec in SCHEMA.items())


def _find(row, keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def meta_from_row(row):
    """Die Daten einer Zeile der Mediendatenbank; {} wenn es keine ist
    (ohne Feld rating: Playlist-Eintrag oder Ordnerfund, siehe oben)."""
    low = {str(k).lower(): v for k, v in row.items()}
    if low.get("rating") is None:
        return {}
    lens = ""
    extra = low.get("custommetadata")
    if isinstance(extra, str) and extra.strip().startswith("{"):
        try:
            extra = json.loads(extra)
        except ValueError:
            extra = None
    if isinstance(extra, dict):
        info = extra.get("cameraInfo") or extra.get("camerainfo") or {}
        if isinstance(info, dict):
            lens = str(info.get("LensModel") or info.get("Lens") or "")
    text = " ".join(str(low.get(k) or "") for k in ("title", "description", "subject", "tags", "keywords"))
    path = str(_find(row, PATH_KEYS) or "")
    return {"r": _int(low.get("rating")), "mk": str(low.get("make") or "")[:60],
            "md": str(low.get("model") or "")[:60], "ln": lens[:80],
            "w": _int(low.get("width")), "h": _int(low.get("height")),
            "x": text.strip()[:400], "n": str(low.get("filename") or os.path.basename(path))[:120],
            "t": str(low.get("datetaken") or "")[:19], "p": str(low.get("locationname") or "")[:80]}


def file_meta(path):
    """Für Fotos, die die Mediendatenbank nicht kennt: Sterne aus XMP (in der
    Datei oder foto.jpg.xmp / foto.xmp daneben) oder EXIF 0x4746, dazu Datum,
    Kamera und Größe, wenn Pillow da ist. {} wenn die Datei nicht lesbar ist."""
    meta = {"r": 0, "mk": "", "md": "", "ln": "", "w": 0, "h": 0, "x": "", "n": os.path.basename(path), "t": "", "p": ""}
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        try:
            with Image.open(path) as image:
                meta["w"], meta["h"] = image.size
                exif = image.getexif()
                if exif.get(0x0112) in (5, 6, 7, 8):
                    meta["w"], meta["h"] = meta["h"], meta["w"]
                meta["mk"] = str(exif.get(0x010F) or "").strip("\x00 ")[:60]
                meta["md"] = str(exif.get(0x0110) or "").strip("\x00 ")[:60]
                sub = exif.get_ifd(0x8769)
                meta["ln"] = str(sub.get(0xA434) or "").strip("\x00 ")[:80]
                value = str(sub.get(0x9003) or exif.get(0x0132) or "").strip()
                if len(value) >= 19 and value[4] == ":":
                    meta["t"] = value[:10].replace(":", "-") + "T" + value[11:19]
                if exif.get(0x4746):
                    meta["r"] = _int(exif.get(0x4746))
        except Exception:
            return {}
    elif not os.path.isfile(path):
        return {}
    for source in (path + ".xmp", os.path.splitext(path)[0] + ".xmp", path):
        if not os.path.isfile(source):
            continue
        try:
            with open(source, "rb") as handle:
                head = handle.read(512 * 1024)
        except OSError:
            continue
        found = next((m for m in (r.search(head) for r in _RATING) if m), None)
        if found:
            meta["r"] = max(0, int(found.group(1)))
            break
    return meta


def passes(meta, values, today=None):
    """Passt ein Foto (meta aus meta_from_row/file_meta) zu den Filtern?"""
    if not meta:
        return False
    v = lambda name: _v(values, name)
    contains = lambda hay, needle: not needle or needle.lower() in str(hay or "").lower()
    if v("DfMinRating") and meta.get("r", 0) < v("DfMinRating"):
        return False
    w, h = meta.get("w") or 0, meta.get("h") or 0
    if v("DfOrientation") != "any":
        if not (w and h):
            return False
        ratio = w / h
        shape = "square" if 0.9 <= ratio <= 1.1 else "landscape" if ratio > 1 else "portrait"
        if shape != v("DfOrientation"):
            return False
    if v("DfMinMegapixels") and (not (w and h) or w * h < v("DfMinMegapixels") * 1e6):
        return False
    taken = meta.get("t") or ""
    day = taken[:10]
    if v("DfAfter") and (not day or day < v("DfAfter")):
        return False
    if v("DfBefore") and (not day or day > v("DfBefore")):
        return False
    if v("DfLastDays"):
        since = (datetime.date.today() - datetime.timedelta(days=v("DfLastDays"))).isoformat()
        if not day or day < since:
            return False
    if v("DfOnThisDay"):
        today = today or datetime.date.today()
        if taken[5:10] != today.strftime("%m-%d"):
            return False
    if not (contains(meta.get("p"), v("DfPlace")) and contains(meta.get("mk"), v("DfMake"))
            and contains(meta.get("md"), v("DfModel")) and contains(meta.get("ln"), v("DfLens"))
            and contains(meta.get("x"), v("DfText")) and contains(meta.get("n"), v("DfFileName"))):
        return False
    if v("DfCameraOnly") and not (meta.get("mk") or meta.get("md")):
        return False
    name = str(meta.get("n") or "").lower()
    if v("DfNoScreenshots") and (_SCREENSHOT.search(name) or name.endswith(".png")):
        return False
    skip = [n.strip().lower() for n in str(v("DfSkipNames")).split(",") if n.strip()]
    if skip and any(n in name for n in skip):
        return False
    return True


def split_key(key):
    """"d:<id>|<pfad>" / "f:<pfad>" -> (id oder None, pfad)."""
    key = str(key or "")
    if key.startswith("d:"):
        media_id, _, path = key[2:].partition("|")
        return (media_id or None), path
    if key.startswith("f:"):
        return None, key[2:]
    return None, key


class Matcher:
    """Prüft Fotos aus DynaFrame gegen die Filter. Sucht jedes Foto in der
    Mediendatenbank (id, dann Pfad, dann Dateiname + Größe, falls DynaFrame
    dasselbe Foto über WebDAV kennt) und liest sonst die Datei selbst
    (gemerkt nach Pfad, Größe und Änderungszeit in cache_file)."""

    def __init__(self, values, library_rows, cache_file=None, log=None):
        self.values = values
        self._library_rows = library_rows
        self._index = None
        self.cache_file = cache_file
        self.log = log or (lambda *a, **k: None)
        self._cache = None
        self._read = 0
        self.total = 0
        self.kept = 0
        self.unknown = 0

    def _build(self):
        by_id, by_path, by_name = {}, {}, {}
        for row in self._library_rows() or []:
            meta = meta_from_row(row)
            if not meta:
                continue
            if row.get("id") is not None:
                by_id[str(row["id"])] = meta
            path = _find(row, PATH_KEYS)
            if path:
                by_path[str(path)] = meta
                by_name.setdefault((os.path.basename(str(path)).lower(), _int(row.get("fileSize"))), meta)
        self._index = (by_id, by_path, by_name)
        self.log(f"DynaFrame-Filter: {len(by_path)} Fotos aus der Mediendatenbank.")

    def _file(self, path):
        if self._cache is None:
            self._cache = {}
            if self.cache_file and os.path.isfile(self.cache_file):
                try:
                    with open(self.cache_file, encoding="utf-8") as handle:
                        data = json.load(handle)
                    self._cache = data if isinstance(data, dict) else {}
                except (OSError, ValueError):
                    self._cache = {}
        try:
            stat = os.stat(path)
        except OSError:
            return {}, 0
        stamp = f"{stat.st_size}:{int(stat.st_mtime)}"
        hit = self._cache.get(path)
        if not hit or hit.get("v") != stamp:
            hit = {"v": stamp, "m": file_meta(path)}
            self._cache[path] = hit
            self._read += 1
        return hit.get("m") or {}, stat.st_size

    def meta(self, key):
        if self._index is None:
            self._build()
        by_id, by_path, by_name = self._index
        media_id, path = split_key(key)
        meta = (by_id.get(str(media_id)) if media_id else None) or by_path.get(path)
        if meta:
            return meta
        if path.startswith("/") and os.path.isfile(path):
            meta, size = self._file(path)
            twin = by_name.get((os.path.basename(path).lower(), size))
            return twin or meta
        return {}

    def keep(self, key, today=None):
        self.total += 1
        meta = self.meta(key)
        if not meta:
            self.unknown += 1
            return False
        if passes(meta, self.values, today):
            self.kept += 1
            return True
        return False

    def counts(self):
        return {"kept": self.kept, "total": self.total, "unknown": self.unknown}

    def save(self):
        if self._read and self.cache_file:
            try:
                tmp = f"{self.cache_file}.tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(self._cache, handle)
                os.replace(tmp, self.cache_file)
            except OSError:
                pass
            self.log(f"DynaFrame-Filter: EXIF aus {self._read} Dateien gelesen.")
        self.log(f"DynaFrame-Filter: {self.kept} von {self.total} Fotos passen"
                 + (f" ({self.unknown} nicht in der Mediendatenbank)" if self.unknown else "") + ".")
