"""Füllt alle leeren data-i18n-Elemente der Seite in der Sprache von <html lang>."""
import json, re, sys
from pathlib import Path
d = Path(sys.argv[1]); h = next(d.rglob("studio/index.html")); j = h.parent / "studio.js"
html = h.read_text(); js = j.read_text()
lang = re.search(r'<html lang="([a-z]+)"', html).group(1); idx = ["de", "en", "es"].index(lang)
def text(key):
    m = re.search(r'^  ' + key + r': \[((?:[^\]"]|"(?:[^"\\]|\\.)*")*)\],', js, re.M)
    return json.loads("[" + m.group(1) + "]")[idx] if m else None
n = 0
def fill(m):
    global n
    value = text(m.group(2))
    if value is None or "{" in value:
        return m.group(0)
    n += 1
    if "data-i18n-html" in m.group(1):
        return m.group(1) + value + m.group(3)
    return m.group(1) + value.replace("&", "&amp;").replace("<", "&lt;") + m.group(3)
html = re.sub(r'(<[a-z0-9]+ [^>]*data-i18n(?:-html)?="(\w+)"[^>]*>)(</[a-z0-9]+>)', fill, html)
h.write_text(html); print(h, lang, n, "gefüllt")
