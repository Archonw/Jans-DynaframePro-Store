"""Setzt die Immich-Filter von Photo Mosaic in eine Plugin-Seite ein.

    python3 apply_ui.py <pack-ordner> <fm-studio-ordner> <config>

Ersetzt im HTML den Bereich zwischen <!-- immich-filters --> und
<!-- /immich-filters --> (diese Marken setzt der Aufrufer vorher) durch die
Filtergruppen von Photo Mosaic, mit Schlüsseln "if…" in I18N, Texte in der
Sprache von <html lang> vorbefüllt. Hängt block.js an studio.js an und die
Gruppen-Stile an studio.css.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGS = ["de", "en", "es"]

CONFIGS = {
    "color-calendar": dict(drop_groups=["grpWhen"], drop_fields=["Orientation"]),
    "on-this-day": dict(drop_groups=["grpWhen"], drop_fields=[]),
    "travel-map": dict(drop_groups=[], drop_fields=["Orientation"]),
}

EXTRA_TEXT = {
    "loading": ["Lädt …", "Loading …", "Cargando …"],
}


def fm_i18n(js):
    out = {}
    for m in re.finditer(r'^  (\w+): \[((?:[^\]"]|"(?:[^"\\]|\\.)*")*)\],', js, re.M):
        try:
            out[m.group(1)] = json.loads("[" + m.group(2) + "]")
        except ValueError:
            pass
    return out


def fm_block(html):
    start = html.index('      <h4 class="group" data-i18n="grpWhat">')
    end = html.index("      <details>", start)
    return html[start:end].rstrip() + "\n"


def drop_groups(block, groups):
    parts = re.split(r'(?=      <h4 class="group" data-i18n=")', block)
    keep = [p for p in parts if not any(f'data-i18n="{g}"' in p.split("\n", 1)[0] for g in groups)]
    return "".join(keep)


def drop_field(block, field_id):
    new, n = re.subn(r'\n        <label class="field">\n(?:(?!</label>).)*id="' + field_id + r'".*?</label>',
                     "", block, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"Feld {field_id} nicht gefunden")
    return new


def main(pack, fm_studio, cfg):
    studio = next(pack.rglob("studio/index.html")).parent
    fm_html = (fm_studio / "index.html").read_text(encoding="utf-8")
    fm_js = (fm_studio / "studio.js").read_text(encoding="utf-8")
    texts = fm_i18n(fm_js)
    block = fm_block(fm_html)
    block = drop_groups(block, cfg["drop_groups"])
    for field in cfg["drop_fields"]:
        block = drop_field(block, field)

    used = sorted(set(re.findall(r'data-i18n(?:-placeholder|-html)?="(\w+)"', block)))
    for key in used:
        block = re.sub(r'(data-i18n(?:-placeholder|-html)?=")' + key + '"', r"\1if" + key[0].upper() + key[1:] + '"', block)
    i18n = {"if" + k[0].upper() + k[1:]: texts[k] for k in used}
    for k in ("nothingHere", "oneChosen", "manyChosen"):
        i18n["if" + k[0].upper() + k[1:]] = texts[k]
    i18n["ifLoading"] = EXTRA_TEXT["loading"]

    h = studio / "index.html"
    html = h.read_text(encoding="utf-8")
    lang = re.search(r'<html lang="([a-z]+)"', html).group(1)
    idx = LANGS.index(lang)

    def fill(m):
        return m.group(1) + i18n[m.group(2)][idx].replace("&", "&amp;").replace("<", "&lt;") + m.group(3)
    block = re.sub(r'(<[a-z0-9]+ [^>]*data-i18n="(\w+)"[^>]*>)[^<]*(</[a-z0-9]+>)', fill, block)
    block = re.sub(r'(data-i18n-placeholder="(\w+)" placeholder=")[^"]*(")',
                   lambda m: m.group(1) + i18n[m.group(2)][idx] + m.group(3), block)
    block = '      <div id="immichFilters">\n' + block + "      </div>\n"
    new, n = re.subn(r"( *)<!-- immich-filters -->\n.*?<!-- /immich-filters -->\n", lambda m: block, html,
                     count=1, flags=re.S)
    if n != 1:
        raise SystemExit("Marke immich-filters fehlt")
    h.write_text(new, encoding="utf-8")

    j = studio / "studio.js"
    js = j.read_text(encoding="utf-8")
    lines = "".join(f"  {k}: {json.dumps(v, ensure_ascii=False)},\n".replace('", "', '", "') for k, v in i18n.items())
    js, n = re.subn(r"^  supportAsk:", lambda m: "  // Immich-Filter (wie Photo Mosaic)\n" + lines + m.group(0),
                    js, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("supportAsk fehlt")
    block_js = (HERE / "block.js").read_text(encoding="utf-8")
    js = js.rstrip("\n") + "\n" + block_js
    j.write_text(js, encoding="utf-8")

    c = studio / "studio.css"
    css = c.read_text(encoding="utf-8")
    css = css.replace('input[type="url"], select {', 'input[type="url"], input[type="date"], select {', 1)
    add = "\n/* Immich-Filter in Gruppen (wie Photo Mosaic) */\n"
    if not re.search(r"^\.card \.sub|^\.sub ", css, re.M):
        add += ".sub { margin: 18px 0 4px; font-size: 15px; }\n"
    add += (".group { margin: 22px 0 6px; font-size: 12.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }\n"
            ".group-sub { margin: 14px 0 4px; font-size: 14px; }\n"
            'input[type="date"] { color-scheme: dark light; }\n')
    if not re.search(r"^input\.filter", css, re.M):
        add += "input.filter { max-width: 320px; margin: 2px 0 8px; }\n@media (max-width: 720px) { input.filter { max-width: none; } }\n"
    c.write_text(css.rstrip("\n") + "\n" + add, encoding="utf-8")
    print("ok", pack.name, lang, len(i18n), "Texte")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), CONFIGS[sys.argv[3]])
