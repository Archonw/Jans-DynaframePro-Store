"""Kurze Ordnernamen für die Liste „Ausgewählte Ordner in DynaFrame“.

Baustein aus tools/plugin-vorlage/folder-picker. Die Liste zeigt jeden Ordner ab
seinem Medienordner („Travel / Italy 2022“ statt „/home/pi/Pictures/Travel/Italy 2022“),
gruppiert nach Medienordner, falls es mehrere gibt. Gespeichert wird weiter der volle
Pfad (id), alte Einstellungen gelten also unverändert.
"""
import os
import re

# Ohne Antwort von DynaFrame: übliche Wurzeln raten
GUESS = re.compile(r"^(/home/[^/]+/(?:Pictures|Bilder|Photos|Fotos|Imágenes|Imagenes)"
                   r"|/media/[^/]+/[^/]+|/mnt/[^/]+/[^/]+|/mnt/[^/]+)(?=/|$)")


def _clean(path):
    path = (path or "").strip()
    return path.rstrip("/") if len(path) > 1 else path


def roots(media_folders=(), extra=()):
    """Medienordner von DynaFrame, dann eigene Ordner. Ein Ordner, der in einem
    anderen liegt, ist keine eigene Wurzel."""
    out = []
    for path in sorted({_clean(p) for p in list(media_folders) + list(extra) if _clean(p) not in ("", "/")}, key=len):
        if not any(path == r or path.startswith(r + "/") for r in out):
            out.append(path)
    return out


def _root_of(path, known):
    if path.startswith("/webdav-media/"):
        parts = path.split("/")
        return "/".join(parts[:3]), "WebDAV"
    hit = max((r for r in known if path == r or path.startswith(r + "/")), key=len, default="")
    if not hit:
        m = GUESS.match(path)
        hit = m.group(1) if m else (os.path.dirname(path) or "/")
    return hit, os.path.basename(hit) or hit


def entry(path, known, count=None):
    root_path, root = _root_of(path, known)
    segs = [s for s in path[len(root_path):].split("/") if s]
    row = {"id": path, "name": " / ".join(segs) or root, "leaf": segs[-1] if segs else root,
           "parent": " / ".join(segs[:-1]), "top": not segs, "root": root, "rootPath": root_path}
    if count is not None:
        row["count"] = count
    return row


def listing(counts, media_folders=(), extra=()):
    """counts: {voller Ordnerpfad: Anzahl Fotos} -> Liste für /api/folders."""
    known = roots(media_folders, extra)
    rows = [entry(path, known, n) for path, n in counts.items()]
    # Gleiche Namen bei verschiedenen Wurzeln: voller Pfad als Gruppenname
    names = {}
    for row in rows:
        names.setdefault(row["root"], set()).add(row["rootPath"])
    for row in rows:
        if len(names[row["root"]]) > 1:
            row["root"] = row["rootPath"]
    return sorted(rows, key=lambda r: (r["rootPath"].lower(), r["name"].lower()))
