#!/usr/bin/env python3
"""Setzt den Port-Block in eine Plugin-Seite ein (tools/plugin-vorlage/ports).

    python3 apply_ui.py <plugin>/studio/index.html

- ersetzt die Zeile mit <!-- port-block --> durch block.html (Texte in der
  Sprache von <html lang> vorbefüllt), oder hängt ihn nach dem Element mit
  id="phoneNote" an, wenn kein Marker da ist,
- bindet ./port_block.js vor ./studio.js ein,
- kopiert block.js als port_block.js neben index.html.
Im Plugin dann: STUDIO_FILES["/port_block.js"], "port" im State, POST /api/port,
und in studio.js render(): window.PortBlock && PortBlock.render(state.port, language).
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def texts():
    source = (HERE / "block.js").read_text(encoding="utf-8")
    found = {}
    for key, body in re.findall(r"(pb\w+): \[(.*?)\],\n", source, re.S):
        found[key] = [s.encode().decode("unicode_escape").encode("latin-1").decode("utf-8")
                      for s in re.findall(r'"((?:[^"\\]|\\.)*)"', body)]
    return found


def main(index):
    index = Path(index)
    html = index.read_text(encoding="utf-8")
    if 'id="portBlock"' in html:
        print("Port-Block ist schon drin.")
    else:
        lang = (re.search(r'<html lang="(\w\w)', html) or [None, "de"])[1]
        col = {"de": 0, "en": 1, "es": 2}.get(lang, 1)
        block = (HERE / "block.html").read_text(encoding="utf-8")
        for key, values in texts().items():
            block = block.replace("{" + key + "}", values[col].replace("&", "&amp;").replace("<", "&lt;"))
        marker = re.search(r"^([ \t]*)<!-- port-block -->[ \t]*\n", html, re.M)
        if marker:
            indent = marker.group(1)
            html = html[:marker.start()] + "".join(indent + l + "\n" for l in block.splitlines()) + html[marker.end():]
        else:
            note = re.search(r'^([ \t]*)<p [^>]*id="phoneNote"[^>]*>.*?</p>[ \t]*\n', html, re.M)
            if not note:
                sys.exit("Kein <!-- port-block --> und kein id=\"phoneNote\" gefunden.")
            indent = note.group(1)
            html = html[:note.end()] + "".join(indent + l + "\n" for l in block.splitlines()) + html[note.end():]
    if "port_block.js" not in html:
        html = re.sub(r'(\s*)(<script src="\./studio\.js")', r'\1<script src="./port_block.js"></script>\1\2', html, count=1)
    index.write_text(html, encoding="utf-8")
    shutil.copy(HERE / "block.js", index.parent / "port_block.js")
    print(f"{index}: Port-Block eingesetzt.")


if __name__ == "__main__":
    main(sys.argv[1])
