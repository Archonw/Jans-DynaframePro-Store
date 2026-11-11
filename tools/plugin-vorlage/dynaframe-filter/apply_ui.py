"""Setzt die Karte „Welche Fotos aus DynaFrame“ von Foto Mosaik in eine Plugin-Seite ein.

    python3 apply_ui.py <pack-ordner> <fm-studio-ordner> <config>

Ersetzt im HTML die Zeile <!-- dynaframe-filters --> (die Marke setzt der
Aufrufer vorher, üblich: vor der Immich-Karte) durch die Karte von Foto Mosaik,
Texte mit Schlüsseln "df…" in I18N, vorbefüllt in der Sprache von <html lang>.
Hängt block.js an studio.js an. Danach in render(): dfRender(s, state).
Stile (.group, input[type=date]) kommen vom Immich-Filter-Baustein; fehlen sie,
erst immich-filter/apply_ui.py laufen lassen oder die Stile übernehmen.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "immich-filter"))
from apply_ui import drop_field, drop_groups  # noqa: E402

LANGS = ["de", "en", "es"]

HINT = ["Gilt für Fotos aus DynaFrame (alle Fotos, Ordner, Playlists). Die Daten liest DynaFrame selbst aus den Fotos "
        "(EXIF, auch Sterne aus .xmp-Dateien daneben). Fotos, die DynaFrame nicht in seiner Mediendatenbank hat, fallen "
        "weg, sobald ein Filter gesetzt ist.",
        "Applies to photos from DynaFrame (all photos, folders, playlists). DynaFrame reads the data from the photos "
        "itself (EXIF, also stars from .xmp files next to them). Photos that are not in DynaFrame's media database are "
        "left out as soon as a filter is set.",
        "Se aplica a las fotos de DynaFrame (todas las fotos, carpetas, listas). DynaFrame lee los datos de las propias "
        "fotos (EXIF, también las estrellas de archivos .xmp al lado). Las fotos que no están en la base de datos de "
        "DynaFrame se omiten en cuanto hay un filtro."]
COUNT = ["{n} von {m} Fotos aus DynaFrame passen zu den Filtern.", "{n} of {m} photos from DynaFrame match the filters.",
         "{n} de {m} fotos de DynaFrame cumplen los filtros."]

CONFIGS = {
    "color-calendar": dict(drop_groups=["grpWhen"], drop_fields=["DfOrientation"]),
    "on-this-day": dict(drop_groups=["grpWhen"], drop_fields=[]),
    "travel-map": dict(drop_groups=[], drop_fields=["DfOrientation"]),
    "all": dict(drop_groups=[], drop_fields=[]),
}


def fm_i18n(js):
    """I18N von Foto Mosaik, auch Einträge über mehrere Zeilen."""
    out = {}
    for m in re.finditer(r'^  (\w+): (\[.*?\]),\n', js, re.M | re.S):
        try:
            out[m.group(1)] = json.loads(m.group(2))
        except ValueError:
            pass
    return out


def rename(key):
    return key if re.match(r"df[A-Z]", key) else "df" + key[0].upper() + key[1:]


def main(pack, fm_studio, cfg):
    studio = next(pack.rglob("studio/index.html")).parent
    fm_html = (fm_studio / "index.html").read_text(encoding="utf-8")
    texts = fm_i18n((fm_studio / "studio.js").read_text(encoding="utf-8"))
    start = fm_html.index('      <h4 class="group" data-i18n="grpWhat">', fm_html.index('data-i18n="dfTitle"'))
    end = fm_html.index("    </section>", start)
    block = fm_html[start:end].rstrip() + "\n"
    block = drop_groups(block, cfg["drop_groups"])
    for field in cfg["drop_fields"]:
        block = drop_field(block, field)

    used = sorted(set(re.findall(r'data-i18n(?:-placeholder|-html)?="(\w+)"', block)))
    for key in used:
        block = re.sub(r'(data-i18n(?:-placeholder|-html)?=")' + key + '"', r"\g<1>" + rename(key) + '"', block)
    i18n = {"dfTitle": texts["dfTitle"], "dfHint": HINT, "dfCount": COUNT}
    i18n.update({rename(k): texts[k] for k in used})

    h = studio / "index.html"
    html = h.read_text(encoding="utf-8")
    lang = re.search(r'<html lang="([a-z]+)"', html).group(1)
    idx = LANGS.index(lang)
    card = ('    <section class="card" id="dynaframeFilters">\n'
            '      <h2 data-i18n="dfTitle"></h2>\n'
            '      <p class="hint" data-i18n="dfHint"></p>\n'
            + block +
            '      <p class="status" id="dfNote"></p>\n'
            '    </section>\n\n')

    def fill(m):
        return m.group(1) + i18n[m.group(2)][idx].replace("&", "&amp;").replace("<", "&lt;") + m.group(3)
    card = re.sub(r'(<[a-z0-9]+ [^>]*data-i18n="(\w+)"[^>]*>)[^<]*(</[a-z0-9]+>)', fill, card)
    new, n = re.subn(r" *<!-- dynaframe-filters -->\n", lambda m: card, html, count=1)
    if n != 1:
        raise SystemExit("Marke dynaframe-filters fehlt")
    h.write_text(new, encoding="utf-8")

    j = studio / "studio.js"
    js = j.read_text(encoding="utf-8")
    lines = "".join(f"  {k}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in i18n.items())
    js, n = re.subn(r"^  supportAsk:", lambda m: "  // DynaFrame-Filter (wie Foto Mosaik)\n" + lines + m.group(0),
                    js, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("supportAsk fehlt")
    js = js.rstrip("\n") + "\n" + (HERE / "block.js").read_text(encoding="utf-8")
    j.write_text(js, encoding="utf-8")
    print("ok", pack.name, lang, len(i18n), "Texte")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), CONFIGS[sys.argv[3]])
