"""Die Bildarbeit des Fotomosaiks, mit Pillow.

- tile(): ein Foto als quadratische Kachel (TILE Pixel) und ihre Farben
  (2 x 2 Teilflächen, RGB), damit die Szene passende Kacheln findet.
- build_sheets(): alle Kacheln als wenige große Bögen (SHEET_GRID x
  SHEET_GRID Kacheln je Bogen). Die Szene lädt nur diese paar Bilder.
- target(): das Motiv in Bildschirmgröße und seine Farben je Zelle des
  Mosaiks (2 x 2 Teilflächen je Zelle).

Große JPEGs werden mit draft() schon beim Entpacken verkleinert; das spart
auf dem Pi das meiste an Zeit und Speicher.
"""

import io
import os
import re

from PIL import Image, ImageOps

try:  # HEIC-Fotos von iPhones, wenn das Paket da ist
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
    HEIF = True
except Exception:  # pragma: no cover - optional
    HEIF = False

Image.MAX_IMAGE_PIXELS = 120_000_000

TILE = 96             # Kantenlänge einer Kachel in den Bögen
SHEET_GRID = 16       # 16 x 16 = 256 Kacheln je Bogen (1536 px)
PER_SHEET = SHEET_GRID * SHEET_GRID
ZOOM_SIDE = 900       # die Kachel, auf die die Szene zufährt, in groß


def open_image(data_or_path, want):
    """Bild öffnen, gedreht wie aufgenommen, mindestens `want` Pixel an der kurzen Seite (wenn möglich)."""
    source = io.BytesIO(data_or_path) if isinstance(data_or_path, (bytes, bytearray)) else data_or_path
    image = Image.open(source)
    if image.format == "JPEG":
        image.draft("RGB", (want, want))
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        if image.mode in ("RGBA", "LA", "P", "PA"):
            image = image.convert("RGBA")
            flat = Image.new("RGB", image.size, (0, 0, 0))
            flat.paste(image, mask=image.split()[-1])
            image = flat
        else:
            image = image.convert("RGB")
    return image


def taken_date(data):
    """Aufnahmedatum aus EXIF als 2024-05-01T12:00:00, sonst ""."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            exif = image.getexif()
            value = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132) or ""
    except Exception:
        return ""
    value = str(value).strip()
    if len(value) >= 19 and value[4] == ":":
        return value[:10].replace(":", "-") + "T" + value[11:19]
    return ""


_RATING = (re.compile(rb'xmp:Rating="(-?\d)"'), re.compile(rb"<xmp:Rating>(-?\d)</xmp:Rating>"))


def file_meta(path):
    """EXIF/XMP-Daten direkt aus einer Fotodatei, wie sie die Mediendatenbank
    von DynaFrame hätte: Sterne (XMP oder EXIF 0x4746, auch aus einer .xmp
    daneben), Datum, Kamera, Größe. Für Fotos aus Ordnern ohne DB-Eintrag."""
    meta = {"r": 0, "mk": "", "md": "", "ln": "", "w": 0, "h": 0, "x": "", "n": os.path.basename(path)}
    taken = ""
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
                taken = value[:10].replace(":", "-") + "T" + value[11:19]
            if exif.get(0x4746):
                meta["r"] = int(exif.get(0x4746))
    except Exception:
        return None, ""
    # XMP im Kopf der Datei oder als .xmp daneben
    sources = []
    for side in (path + ".xmp", os.path.splitext(path)[0] + ".xmp"):
        if os.path.isfile(side):
            sources.append(side)
    sources.append(path)
    for source in sources:
        try:
            with open(source, "rb") as handle:
                head = handle.read(512 * 1024)
        except OSError:
            continue
        found = next((m for m in (r.search(head) for r in _RATING) if m), None)
        if found:
            meta["r"] = max(0, int(found.group(1)))
            break
    return meta, taken


def square(image, side):
    """Mittiges Quadrat, auf `side` Pixel verkleinert."""
    return ImageOps.fit(image, (side, side), Image.LANCZOS if side >= 256 else Image.BILINEAR,
                        centering=(0.5, 0.45))


def features(image):
    """RGB der vier Viertel (oben links, oben rechts, unten links, unten rechts)."""
    small = image.resize((2, 2), Image.BOX)
    out = []
    for y in range(2):
        for x in range(2):
            out.extend(small.getpixel((x, y)))
    return out


def tile(data_or_path):
    """(JPEG-Bytes der Kachel, Farben) aus einem Foto."""
    image = open_image(data_or_path, TILE * 2)
    small = square(image, TILE)
    buffer = io.BytesIO()
    small.save(buffer, "JPEG", quality=88)
    return buffer.getvalue(), features(small)


def zoom_tile(data_or_path):
    image = open_image(data_or_path, ZOOM_SIDE)
    side = min(ZOOM_SIDE, image.width, image.height)
    big = square(image, side)
    buffer = io.BytesIO()
    big.save(buffer, "JPEG", quality=86)
    return buffer.getvalue()


def build_sheets(tile_files, out_paths):
    """Kacheln (Pfade der Kachel-JPEGs, in Reihenfolge) auf Bögen verteilen."""
    for index, out_path in enumerate(out_paths):
        chunk = tile_files[index * PER_SHEET:(index + 1) * PER_SHEET]
        rows = (len(chunk) + SHEET_GRID - 1) // SHEET_GRID
        sheet = Image.new("RGB", (SHEET_GRID * TILE, max(1, rows) * TILE), (0, 0, 0))
        for slot, path in enumerate(chunk):
            try:
                with Image.open(path) as piece:
                    piece = piece.convert("RGB")
                    if piece.size != (TILE, TILE):
                        piece = piece.resize((TILE, TILE))
                    sheet.paste(piece, ((slot % SHEET_GRID) * TILE, (slot // SHEET_GRID) * TILE))
            except OSError:
                continue
        temp = out_path.with_suffix(".tmp")
        sheet.save(temp, "JPEG", quality=86, optimize=True)
        temp.replace(out_path)


def target(data_or_path, width, cols, rows, full_box=None):
    """(JPEG width breit und so hoch wie das Raster, Farben je Zelle: rows x cols x 2 x 2 x RGB als Liste).

    Das Bild wird auf das Seitenverhältnis des Rasters zugeschnitten
    (cols:rows), so passen Bild und Mosaik genau übereinander."""
    image = open_image(data_or_path, max(int(width * max(1, rows / cols)), max(full_box or (0,))))
    out_w = max(1, int(width))
    out_h = max(1, round(out_w * rows / cols))
    full = None
    if full_box:
        # Das ganze Foto, nicht beschnitten, passend in den Bildschirm
        whole = image.copy()
        whole.thumbnail(full_box, Image.LANCZOS)
        buffer = io.BytesIO()
        whole.save(buffer, "JPEG", quality=88)
        full = buffer.getvalue()
    fitted = ImageOps.fit(image, (out_w, out_h), Image.LANCZOS, centering=(0.5, 0.45))
    buffer = io.BytesIO()
    fitted.save(buffer, "JPEG", quality=88)
    grid = fitted.resize((cols * 2, rows * 2), Image.BOX)
    raw = grid.tobytes()
    cells = []
    # Je Zelle: oben links, oben rechts, unten links, unten rechts
    stride = cols * 2 * 3
    for r in range(rows):
        for c in range(cols):
            for dy in range(2):
                base = (r * 2 + dy) * stride + c * 2 * 3
                cells.extend(raw[base:base + 6])
    return buffer.getvalue(), cells, fitted.size, full
