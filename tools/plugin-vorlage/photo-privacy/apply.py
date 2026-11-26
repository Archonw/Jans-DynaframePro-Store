#!/usr/bin/env python3
"""Schalter „Fotopositionen bleiben auf dem Rahmen“ in ein Pack einbauen.

    python3 tools/plugin-vorlage/photo-privacy/apply.py <pack-ordner> --uses places,weather[,elevation,sights,guide]

Kopiert photo_privacy.py nach plugin/, meldet die Einstellung KeepPhotoPlaces in
SCHEMA an, bindet sie an settings(), setzt die Karte „Fotopositionen“ vor die
Karte „Eine Playlist dafür“ und hängt block.js an studio.js (zwischen Marken,
ein zweiter Lauf erneuert den Stand).

Die Sperren selbst baut man von Hand ein: vor jeder Anfrage, die eine
Fotoposition enthält, `if photo_privacy.blocks(lat, lon): return …` und in der
Verbindungskarte bei `photo_privacy.active()` ohne Anfrage `photo_privacy.note()`
zeigen. Siehe README.md.
"""
import argparse
import html
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXTS = json.loads((HERE / "texts.json").read_text(encoding="utf-8"))
CARD_START, CARD_END = "<!-- photo-privacy:start -->", "<!-- photo-privacy:end -->"
JS_START, JS_END = "// ==== photo-privacy:start", "// ==== photo-privacy:end ===="


def card(uses, lang):
    tx = TEXTS.get(lang) or TEXTS["en"]
    hint = tx["hint"].replace("{uses}", ", ".join(tx[k] for k in uses if k in tx and k != "guide"))
    lines = [
        CARD_START,
        f'    <section class="card" id="photoPrivacy" data-pp-uses="{",".join(uses)}">',
        f'      <h2 data-pp="title">{html.escape(tx["title"])}</h2>',
        f'      <label class="field check"><input type="checkbox" id="KeepPhotoPlaces"><span data-pp="label">{html.escape(tx["label"])}</span></label>',
        f'      <p class="hint" data-pp="hint">{html.escape(hint)}</p>',
    ]
    if "guide" in uses:
        lines.append(f'      <p class="hint" data-pp="guide">{html.escape(tx["guide"])}</p>')
    lines += ['      <p class="status" id="photoPrivacyNote"></p>', "    </section>", "    " + CARD_END]
    return "\n".join(lines)


def main(pack, uses):
    plugin = Path(pack) / "plugin"
    py, js, page = plugin / "plugin.py", plugin / "studio/studio.js", plugin / "studio/index.html"
    done = []

    shutil.copyfile(HERE / "photo_privacy.py", plugin / "photo_privacy.py")
    done.append("photo_privacy.py")

    src = py.read_text(encoding="utf-8")
    new = src
    if "import photo_privacy" not in new:
        new = re.sub(r"^(import texts\b[^\n]*)\n", r"\1\nimport photo_privacy  # noqa: E402\n", new, count=1, flags=re.M)
        assert "import photo_privacy" in new, f"{py}: kein 'import texts' gefunden"
    if "SCHEMA.update(photo_privacy.SCHEMA)" not in new:
        start = new.index("\nSCHEMA = {")
        end = new.index("\n}\n", start) + 3
        new = new[:end] + "SCHEMA.update(photo_privacy.SCHEMA)   # Fotopositionen bleiben auf dem Rahmen\n" + new[end:]
    if "photo_privacy.bind(settings)" not in new:
        at = new.index("\ndef save_settings(")
        new = new[:at] + "\nphoto_privacy.bind(settings)\n\n" + new[at:]
    if new != src:
        py.write_text(new, encoding="utf-8"); done.append("plugin.py")

    src = page.read_text(encoding="utf-8")
    lang = (re.search(r'<html[^>]*\blang="([a-z]{2})', src) or [None, "en"])[1]
    block = card(uses, lang)
    if CARD_START in src:
        new = re.sub(re.escape(CARD_START) + r".*?" + re.escape(CARD_END), lambda _: block.strip(), src, flags=re.S)
    else:
        at = src.index('id="MakePlaylist"')
        at = src.rindex('<section class="card"', 0, at)
        at = src.rindex("\n", 0, at) + 1
        new = src[:at] + "    " + block.lstrip() + "\n" + src[at:]
    if new != src:
        page.write_text(new, encoding="utf-8"); done.append("index.html")

    src = js.read_text(encoding="utf-8")
    add = (HERE / "block.js").read_text(encoding="utf-8").replace(
        "/*PP_TEXT*/{}", json.dumps(TEXTS, ensure_ascii=False, indent=2)).rstrip("\n") + "\n"
    pat = re.compile(re.escape(JS_START) + r".*?" + re.escape(JS_END) + r"\n?", re.S)
    new = pat.sub(lambda _: add, src) if pat.search(src) else src.rstrip("\n") + "\n\n" + add
    if new != src:
        js.write_text(new, encoding="utf-8"); done.append("studio.js")
    return done


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pack")
    parser.add_argument("--uses", default="places", help="places,weather,elevation,sights,guide")
    args = parser.parse_args()
    print(args.pack, main(args.pack, [u for u in args.uses.split(",") if u]))
