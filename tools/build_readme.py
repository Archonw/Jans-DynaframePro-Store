#!/usr/bin/env python3
"""Erzeugt die Pack-Tabellen in README.md aus catalog.json.

Ersetzt alles zwischen den Markern <!-- packs:start --> und <!-- packs:end -->.
Jeder Abschnitt ist alphabetisch nach dem angezeigten Namen sortiert.
Kurztexte kommen aus tools/readme_texts.json (Pack-ID -> Text). Neue Packs ohne
Eintrag dort erscheinen trotzdem, mit dem ersten Satz der Katalog-Beschreibung. Wer einen schoeneren Kurztext
will, traegt ihn in readme_texts.json ein.

Aufruf: python3 tools/build_readme.py          (schreibt README.md)
        python3 tools/build_readme.py --check  (Exit 1, wenn README veraltet)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CATALOG = ROOT / "catalog.json"
TEXTS = ROOT / "tools" / "readme_texts.json"
START, END = "<!-- packs:start -->", "<!-- packs:end -->"

SECTIONS = [
    ("integration", "Live integrations",
     "Integrations bring their own scene and can show themselves over the running "
     "slideshow every few minutes or when something happens. All of them speak "
     "German, English and Spanish.", "Pack", "What it does", 220),
    ("plugin", "Plugins", None, "Pack", "What it does", 220),
    ("magic-mirror-module", "Magic Mirror modules",
     "Add-ons for **Dynaframe's Magic Mirror** (install that first). They appear in "
     "the Store and in the Magic Mirror plugin page under \"More modules\", not as "
     "separate plugins.", "Module", "What it shows", 160),
]
MODULES_FOOTER = (
    "**Build your own module or port one from MagicMirror²:** the guide "
    "[MODULES.md](plugin_packs/magic-frame/MODULES.md) is complete on its own, so you "
    "can hand it to an AI together with the link to a MagicMirror² module. Working "
    "examples are in [module-sources](plugin_packs/magic-frame/module-sources)."
)


def display_title(pack):
    title = pack["title"]
    m = re.match(r"Magic Mirror (module|skin): (.+)", title)
    if m:
        return m.group(2) + ("** (skin)" if m.group(1) == "skin" else "**")
    return title + "**"


def first_sentence(text):
    text = text.strip()
    for m in re.finditer(r"[.!?](?=\s+[A-ZÄÖÜ\"]|$)", text):
        head = text[:m.end()]
        if re.search(r"\b(e\.g|i\.e|etc|incl|approx)\.$", head) or head.count("(") > head.count(")"):
            continue
        return head
    return text


def cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def build(packs, texts):
    out = []
    known = {s[0] for s in SECTIONS}
    for ptype, heading, intro, col, what, width in SECTIONS:
        items = [p for p in packs if p.get("type") == ptype
                 or (ptype == "plugin" and p.get("type") not in known)]
        if not items:
            continue
        items.sort(key=lambda p: display_title(p).casefold())
        out += [f"### {heading}", ""]
        if intro:
            out += [intro, ""]
        out += [f"| | {col} | {what} |", "|---|---|---|"]
        for p in items:
            thumb = (p.get("thumbnails") or [""])[0]
            text = texts.get(p["id"]) or first_sentence(p.get("description", ""))
            img = f'<img src="{thumb}" width="{width}">' if thumb else ""
            out.append(f"| {img} | **{display_title(p)} | {cell(text)} |")
        out.append("")
        if ptype == "magic-mirror-module":
            out += [MODULES_FOOTER, ""]
    return "\n".join(out).rstrip() + "\n"


def main():
    packs = json.loads(CATALOG.read_text(encoding="utf-8"))["packs"]
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        sys.exit(f"Marker {START} / {END} fehlen in README.md")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    new = f"{head}{START}\n{build(packs, texts)}{END}{tail}"
    missing = [p["id"] for p in packs if p["id"] not in texts]
    if missing:
        print("Ohne Kurztext (erster Satz der Beschreibung genommen):", ", ".join(missing))
    if "--check" in sys.argv:
        if new != readme:
            sys.exit("README.md ist nicht aktuell: python3 tools/build_readme.py")
        return
    if new != readme:
        README.write_text(new, encoding="utf-8")
        print("README.md aktualisiert")
    else:
        print("README.md ist schon aktuell")


if __name__ == "__main__":
    main()
