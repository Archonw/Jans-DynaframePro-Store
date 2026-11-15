#!/usr/bin/env python3
"""Baut plugin_bridge.js in eine Szene ein.

    python3 apply.py <pack>/dynamic

Kopiert plugin_bridge.js in den Ordner und setzt in jede .html-Datei mit <script>
die Zeile <script src="plugin_bridge.js"></script> vor das erste Skript (nur einmal).
Gibt aus, welche Dateien geändert wurden.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAG = '<script src="plugin_bridge.js"></script>'


def apply(dynamic_dir):
    dynamic_dir = Path(dynamic_dir)
    changed = []
    shutil.copyfile(HERE / "plugin_bridge.js", dynamic_dir / "plugin_bridge.js")
    for html in sorted(dynamic_dir.rglob("*.html")):
        text = html.read_text(encoding="utf-8")
        if "plugin_bridge.js" in text:
            continue
        match = re.search(r"^([ \t]*)<script\b", text, re.M)
        if not match:
            continue
        indent = match.group(1)
        prefix = "../" * (len(html.relative_to(dynamic_dir).parts) - 1)
        tag = TAG.replace('src="', f'src="{prefix}')
        text = text[:match.start()] + f"{indent}{tag}\n" + text[match.start():]
        html.write_text(text, encoding="utf-8")
        changed.append(str(html))
    return changed


if __name__ == "__main__":
    for path in apply(sys.argv[1]):
        print(path)
