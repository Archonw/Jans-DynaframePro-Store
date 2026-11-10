"""Packt ein Pack-Verzeichnis als ZIP mit richtigen Unix-Rechten.

    python3 make_zip.py <pack-ordner> <ziel.zip>

Integration: <pack-ordner> enthält dynaframe-package.json, README.md, dynamic/, plugin/.
Flaches Plugin: manifest.json, plugin.py ... direkt im Ordner.

Wichtig (9.11.2026): Ohne S_IFREG/S_IFDIR in external_attr (z. B. Ordner mit
0600) bricht die Installation im DynaFrame-Store mit „Error“ ab und hinterlässt
„already installed“-Reste. Dieses Skript setzt Dateien 0644, Ordner 0755.
__pycache__ und .pyc bleiben draußen.
"""
import sys
import zipfile
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
order = ["dynaframe-package.json", "README.md", "manifest.json"]
paths = sorted((p for p in src.rglob("*") if "__pycache__" not in p.parts and p.suffix != ".pyc"),
               key=lambda p: (str(p.relative_to(src)) not in order, str(p.relative_to(src))))
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in paths:
        rel = p.relative_to(src).as_posix()
        if p.is_dir():
            info = zipfile.ZipInfo(rel + "/", date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o40755 << 16) | 0x10
            z.writestr(info, b"")
        else:
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, p.read_bytes())
print(out, out.stat().st_size)
