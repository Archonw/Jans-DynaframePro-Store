"""Die Immich-Filter von Photo Mosaic als gemeinsamer Baustein
(Travel Map, Colour Calendar, On This Day).

Einbau im Plugin:
    SCHEMA.update(immich_filters.SCHEMA)          # oder nur Teile davon
    coerce():  value = immich_filters.coerce(spec, raw); if value is not None: return value
    f = immich_filters.from_settings(values)       # Filter für die Suche
    items = immich_filters.search(immich, stop, f, album_ids, extra_body)
    /api/people -> immich_filters.people(immich), /api/tags -> immich_filters.tags(immich)

Wie Growing Up und Photo Mosaic: eine Suche je Album und je Person (mehrere
IDs verknüpft Immich mit UND, wir wollen ODER). Was Immich selbst kann
(Favoriten, Ort, Kamera, Zeitraum, Beschreibung, Text im Bild, Dateiname,
in keinem Album) macht der Server, den Rest prüft keep(): Sterne (>=),
Ausrichtung, Megapixel, Dateigröße, an diesem Tag, nur mit Personen, nur
Kamerafotos, Bildschirmfotos und Dateinamen weglassen.
"""

import datetime
import re

PAGE_SIZE = 1000
MAX_PHOTOS = 300000

SCHEMA = {
    "MinRating":       {"kind": "int", "default": 0, "min": 0, "max": 5},
    "FavoritesOnly":   {"kind": "bool", "default": False},
    "IncludeArchived": {"kind": "bool", "default": False},
    "Orientation":     {"kind": "choice", "default": "any", "choices": ("any", "landscape", "portrait", "square")},
    "People":          {"kind": "ref", "default": ""},
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
}

# Filter, die ein bestimmtes Datum wählen: On This Day sucht selbst nach Tagen
WHEN = ("OnThisDay", "LastDays", "TakenAfter", "TakenBefore")


def schema(without=()):
    return {k: v for k, v in SCHEMA.items() if k not in without}


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def coerce(spec, raw):
    """Die zusätzlichen Arten ref/date/name; None = nicht zuständig."""
    kind = spec["kind"]
    if kind == "ref":
        items = raw if isinstance(raw, list) else str(raw or "").split(",")
        chosen = []
        for item in items:
            item = re.sub(r"[^A-Za-z0-9_-]", "", str(item))[:64]
            if item and item not in chosen:
                chosen.append(item)
        return ",".join(chosen[:50])
    if kind == "date":
        value = str(raw or "").strip()[:10]
        return value if re.match(r"^\d{4}-\d{2}-\d{2}$", value) else ""
    if kind == "name":
        return re.sub(r"\s+", " ", str(raw or "")).strip()[:200]
    return None


def from_settings(values):
    """Die Filter aus den Einstellungen (fehlende Schlüssel = aus)."""
    v = lambda key: values.get(key, SCHEMA[key]["default"])
    split = lambda text: [x for x in str(text or "").split(",") if x]
    return {
        "rating": v("MinRating"), "favorites": v("FavoritesOnly"), "archived": v("IncludeArchived"),
        "people": split(v("People")), "orientation": v("Orientation"),
        "city": v("City"), "state": v("State"), "country": v("Country"),
        "onThisDay": v("OnThisDay"), "lastDays": v("LastDays"), "after": v("TakenAfter"), "before": v("TakenBefore"),
        "make": v("Make"), "model": v("Model"), "lensModel": v("Lens"),
        "description": v("Description"), "ocr": v("OcrText"), "originalFileName": v("FileName"),
        "withPeople": v("WithPeople"), "cameraOnly": v("CameraOnly"), "noScreenshots": v("NoScreenshots"),
        "notInAlbum": v("NotInAlbum"), "megapixels": v("MinMegapixels"), "minKB": v("MinFileKB"),
        "skipAlbums": split(v("SkipAlbums")), "skipTags": split(v("SkipTags")), "skipNames": v("SkipNames"),
    }


def signature(values):
    """Für scan_signature: ändert sich, sobald sich ein Filter ändert."""
    return [values.get(k, SCHEMA[k]["default"]) for k in SCHEMA]


def active(f):
    """True, wenn irgendein Filter von „alle Fotos“ abweicht."""
    return any(bool(value) and value != "any" for value in f.values())


def needs_exif(f):
    """Ob die Suche exifInfo mitliefern muss (sonst geht es schneller ohne)."""
    return bool(f.get("rating") or f.get("orientation") not in (None, "", "any") or f.get("megapixels")
                or f.get("minKB") or f.get("cameraOnly"))


def people(immich):
    data = immich.call("GET", "/people", params={"withHidden": "false", "size": 1000}) or {}
    rows = data.get("people") if isinstance(data, dict) else data
    out = [{"id": r["id"], "name": r.get("name") or ""} for r in rows or []
           if isinstance(r, dict) and r.get("id") and r.get("name")]
    return sorted(out, key=lambda r: r["name"].lower())


def tags(immich):
    rows = immich.call("GET", "/tags") or []
    out = [{"id": r["id"], "name": r.get("value") or r.get("name") or "?"} for r in rows
           if isinstance(r, dict) and r.get("id")]
    return sorted(out, key=lambda r: r["name"].lower())


def _pages(immich, body, stop, limit, timeout=120):
    """Alle Treffer einer Suche, seitenweise."""
    out = []
    page, cursor = 1, None
    while len(out) < limit and not stop.is_set():
        query = dict(body, size=min(PAGE_SIZE, max(1, limit)))
        query.setdefault("type", "IMAGE")
        if cursor:
            query["cursor"] = cursor
        else:
            query["page"] = page
        data = immich.call("POST", "/search/metadata", query, timeout=timeout) or {}
        assets = data.get("assets") or {}
        items = assets.get("items") or []
        out += [i for i in items if isinstance(i, dict) and i.get("id")]
        cursor = assets.get("nextCursor")
        next_page = assets.get("nextPage")
        if cursor:
            continue
        if next_page and items:
            page = _int(next_page, page + 1)
            continue
        break
    return out


def _ids_of(immich, field, ids, stop):
    """Alle Asset-IDs in diesen Alben bzw. mit diesen Tags (zum Weglassen)."""
    found = set()
    for one in ids:
        try:
            found.update(i["id"] for i in _pages(immich, {field: [one]}, stop, MAX_PHOTOS))
        except Exception as exc:  # noqa: BLE001 - SourceError des Plugins
            if getattr(exc, "status", None) != 400:
                raise
    return found


def base_body(immich, f, album_ids=None, with_exif=True):
    body = {"withExif": bool(with_exif)}
    if f.get("favorites"):
        body["isFavorite"] = True
    if not f.get("archived") and not getattr(immich, "_old_visibility", False):
        body["visibility"] = "timeline"
    for key in ("city", "state", "country", "make", "model", "lensModel", "description", "originalFileName"):
        if f.get(key):
            body[key] = f[key]
    if f.get("ocr"):
        body["ocr"] = f["ocr"]
    if f.get("notInAlbum") and not album_ids:
        body["isNotInAlbum"] = True
    if f.get("withPeople"):
        body["withPeople"] = True
    after, before = f.get("after"), f.get("before")
    if f.get("lastDays"):
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(f["lastDays"]))
        after = since.strftime("%Y-%m-%d")
    if after:
        body["takenAfter"] = after + "T00:00:00.000Z"
    if before:
        body["takenBefore"] = before + "T23:59:59.999Z"
    return body


class Context:
    """Was eine Suche über mehrere Aufrufe braucht (z. B. ein Jahr nach dem anderen):
    die weggelassenen IDs werden nur einmal geholt."""

    def __init__(self, immich, f, stop):
        self.f = f
        self.skip = _ids_of(immich, "albumIds", f.get("skipAlbums") or [], stop) if f.get("skipAlbums") else set()
        if f.get("skipTags"):
            self.skip |= _ids_of(immich, "tagIds", f["skipTags"], stop)
        self.names_out = [n.strip().lower() for n in str(f.get("skipNames") or "").split(",") if n.strip()]
        self.today = datetime.date.today()

    def keep(self, item):
        return keep(item, self.f, self.skip, self.names_out, self.today)


def search(immich, stop, f, album_ids=None, extra=None, limit=MAX_PHOTOS, ctx=None, progress=None,
           ocr_error="Dieses Immich kann nicht nach Text im Bild suchen.", timeout=120):
    """Alle Immich-Einträge, die zu allen Filtern passen (mit exifInfo).

    extra: weitere Felder für die Suche, z. B. takenAfter/takenBefore oder order.
    Sie gehen vor den Filtern."""
    ctx = ctx or Context(immich, f, stop)
    found = {}
    for album in album_ids or [None]:
        for person in f.get("people") or [None]:
            body = base_body(immich, f, album_ids)
            body.update(extra or {})
            if album:
                body["albumIds"] = [album]
            if person:
                body["personIds"] = [person]
            try:
                try:
                    items = _pages(immich, body, stop, limit - len(found), timeout)
                except Exception as exc:  # noqa: BLE001 - SourceError des Plugins
                    if getattr(exc, "status", None) == 400 and "visibility" in body and "ocr" not in str(exc):
                        immich._old_visibility = True   # älteres Immich: isArchived statt visibility
                        body.pop("visibility")
                        items = _pages(immich, body, stop, limit - len(found), timeout)
                    else:
                        raise
            except Exception as exc:  # noqa: BLE001
                if getattr(exc, "status", None) != 400:
                    raise
                if "ocr" in body:
                    tr = getattr(immich, "tr", None)
                    raise type(exc)(tr(ocr_error) if tr else ocr_error) from exc
                if album or person:
                    continue                            # Album oder Person gibt es nicht mehr
                raise
            for item in items:
                if item["id"] not in found and ctx.keep(item):
                    found[item["id"]] = item
            if progress:
                progress(len(found))
            if len(found) >= limit or stop.is_set():
                break
    return list(found.values())[:limit]


def keep(item, f, skip=(), names_out=(), today=None):
    if item.get("isTrashed") or item.get("type") not in (None, "IMAGE") or item.get("id") in skip:
        return False
    if item.get("visibility") in ("hidden", "locked"):
        return False
    if not f.get("archived") and (item.get("isArchived") or item.get("visibility") == "archive"):
        return False
    if f.get("favorites") and item.get("isFavorite") is False:
        return False
    exif = item.get("exifInfo") or {}
    if f.get("rating") and _int(exif.get("rating"), 0) < int(f["rating"]):
        return False
    name = str(item.get("originalFileName") or "").lower()
    if f.get("noScreenshots") and (re.search(r"screen ?shot|bildschirmfoto|captura|screen_|scrnli", name)
                                   or name.endswith(".png")):
        return False
    if names_out and any(n in name for n in names_out):
        return False
    if f.get("cameraOnly") and not (exif.get("make") or exif.get("model")):
        return False
    if f.get("withPeople") and "people" in item and not item.get("people"):
        return False
    width, height = _int(exif.get("exifImageWidth"), 0), _int(exif.get("exifImageHeight"), 0)
    if str(exif.get("orientation") or "") in ("5", "6", "7", "8"):
        width, height = height, width
    if f.get("orientation") in ("landscape", "portrait", "square") and width and height:
        ratio = width / height
        shape = "square" if 0.9 <= ratio <= 1.1 else "landscape" if ratio > 1 else "portrait"
        if shape != f["orientation"]:
            return False
    if f.get("megapixels") and width and height and width * height < float(f["megapixels"]) * 1e6:
        return False
    size = _int(exif.get("fileSizeInByte"), 0)
    if f.get("minKB") and size and size < int(f["minKB"]) * 1024:
        return False
    if f.get("onThisDay"):
        taken = str(item.get("localDateTime") or exif.get("dateTimeOriginal") or "")
        if taken[5:10] != (today or datetime.date.today()).strftime("%m-%d"):
            return False
    return True
