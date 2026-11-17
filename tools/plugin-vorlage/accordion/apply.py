"""Baut das Aufklappen (Akkordeon) in eine Plugin-Seite ein.

    python3 apply.py <pack-ordner> [extra.json]

- Hängt accordion.js an studio/studio.js und accordion.css an studio/studio.css
  (zwischen Marken; ein zweiter Lauf ersetzt den alten Stand).
- Setzt die Standard-Attribute an die bekannten Karten der Vorlage (erkannt am
  data-i18n-Schlüssel der Überschrift), siehe STANDARD unten.
- extra.json (optional) setzt weitere Karten/Abschnitte des Plugins, gleiche Form
  ("sub": true = nur h3.sub, "card": true = nur Karten-Überschrift h2):
  {"lookTitle": {"fold": "look", "start": "closed"}, "motionTitle": {"fold": "motion", "start": "closed"}}

Danach keine Änderung an render() nötig: accordion.js liest die Felder selbst.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Schlüssel der Überschrift -> Attribute. h3.sub-Schlüssel klappen einen Abschnitt in der Karte.
STANDARD = {
    "dfTitle": {"fold": "dynaframeFilter", "when": "uses:dynaframe", "start": "closed", "badge": "count"},
    "serverTitle": {"fold": "immich", "when": "uses:immich"},
    "filterTitle": {"fold": "immichFilter", "start": "closed", "badge": "count", "sub": True},
    "davTitle": {"fold": "webdav", "when": "uses:dynaframe", "start": "closed", "badge": "filled"},
    "foldersTitle": {"fold": "folders", "when": "uses:library", "start": "closed", "badge": "lines"},
    "servicesTitle": {"fold": "services", "start": "closed", "badge": "services"},
}

JS_START, JS_END = "// ---- accordion:start", "// ---- accordion:end"
CSS_START, CSS_END = "/* ---- accordion:start */", "/* ---- accordion:end */"


def attrs(cfg):
    out = f' data-fold="{cfg["fold"]}"'
    if cfg.get("when"):
        out += f' data-fold-when="{cfg["when"]}"'
    if cfg.get("start"):
        out += f' data-fold-start="{cfg["start"]}"'
    if cfg.get("badge"):
        out += f' data-fold-badge="{cfg["badge"]}"'
    return out


def mark_html(html, config):
    done = []
    # Karten: <section class="card"> … erste <h2 data-i18n="key">
    def card(m):
        tag, body = m.group(1), m.group(2)
        if "data-fold=" in tag:
            return m.group(0)
        h2 = re.search(r'<h2[^>]*data-i18n="(\w+)"', body)
        if not h2 or h2.group(1) not in config or config[h2.group(1)].get("sub"):
            return m.group(0)
        done.append(h2.group(1))
        return tag[:-1] + attrs(config[h2.group(1)]) + ">" + body

    html = re.sub(r'(<section class="card"[^>]*>)(.*?)(?=<section class="card"|<footer|</main>)', card, html, flags=re.S)

    # Abschnitte: <h3 class="sub" data-i18n="key">
    def sub(m):
        key = m.group(2)
        if key not in config or config[key].get("card") or "data-fold=" in m.group(0):
            return m.group(0)
        done.append(key)
        return m.group(1) + attrs(config[key]) + m.group(3)

    html = re.sub(r'(<h3 class="sub"[^>]*?data-i18n="(\w+)")([^>]*>)', sub, html)
    return html, done


def put_block(text, start, end, block):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.S)
    piece = f"{start}\n{block.strip()}\n{end}\n"
    if pattern.search(text):
        return pattern.sub(lambda _: piece, text)
    return text.rstrip("\n") + "\n\n" + piece


def main(pack, extra=None):
    studio = next(Path(pack).rglob("studio/index.html")).parent
    config = dict(STANDARD)
    if extra:
        config.update(json.loads(Path(extra).read_text(encoding="utf-8")))
    html_path = studio / "index.html"
    html, done = mark_html(html_path.read_text(encoding="utf-8"), config)
    html_path.write_text(html, encoding="utf-8")
    js = studio / "studio.js"
    js.write_text(put_block(js.read_text(encoding="utf-8"), JS_START, JS_END,
                            (HERE / "accordion.js").read_text(encoding="utf-8")), encoding="utf-8")
    css = studio / "studio.css"
    css.write_text(put_block(css.read_text(encoding="utf-8"), CSS_START, CSS_END,
                             (HERE / "accordion.css").read_text(encoding="utf-8")), encoding="utf-8")
    print(f"{studio}: {', '.join(done) or 'keine Karte markiert'}")
    return done


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
