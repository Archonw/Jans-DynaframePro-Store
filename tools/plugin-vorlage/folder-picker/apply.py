#!/usr/bin/env python3
"""Ordnerliste „Ausgewählte Ordner in DynaFrame“ auf kurze Namen umstellen.

    python3 tools/plugin-vorlage/folder-picker/apply.py <pack-ordner>

Kopiert folder_names.py nach plugin/, stellt list_folders() in plugin.py darauf um,
hängt folder-picker.js/.css an studio.js/.css (zwischen Marken, ein zweiter Lauf
erneuert den Stand) und setzt in renderChecks() den Haken auf fpRender().
Gibt die geänderten Dateien aus; nichts geändert = Pack hat die Ordnerliste nicht.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_PY = ('    folders = [{"id": f, "name": folder_label(f), "count": n} for f, n in counts.items()]\n'
          '    return {"success": True, "folders": sorted(folders, key=lambda f: f["name"].lower())}\n')
NEW_PY = ('    try:\n'
          '        media = dynaframe.media_folders()\n'
          '    except Exception:  # Engine weg: Wurzeln raten\n'
          '        media = []\n'
          '    # Kurze Namen ab dem Medienordner, id bleibt der volle Pfad (folder-picker)\n'
          '    return {"success": True, "folders": folder_names.listing(counts, media, settings()["Folders"].splitlines())}\n')
HOOK_AT = "  const chosen = new Set(chosenItems(prefix, s));\n"
HOOK = ('  box.classList.toggle("fp-list", listKind === "folders");\n'
        '  if (listKind === "folders") { fpRender(box, prefix, s, items); return; }  // folder-picker\n')


def block(text, add, start, end):
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.S)
    add = add.rstrip("\n") + "\n"
    if pat.search(text):
        return pat.sub(lambda _: add, text)
    return text.rstrip("\n") + "\n\n" + add


def main(pack):
    pack = Path(pack)
    plugin = pack / "plugin"
    py, js, css = plugin / "plugin.py", plugin / "studio/studio.js", plugin / "studio/studio.css"
    if not (py.exists() and js.exists()) or "/api/folders" not in py.read_text(encoding="utf-8"):
        return []
    done = []
    src = py.read_text(encoding="utf-8")
    new = src
    if OLD_PY in new:
        new = new.replace(OLD_PY, NEW_PY)
    if "folder_names.listing" not in new:
        raise SystemExit(f"{py}: list_folders() nicht erkannt, bitte von Hand umstellen")
    if "import folder_names" not in new:
        new = re.sub(r"^(import sources\b[^\n]*)\n", r"import folder_names  # noqa: E402\n\1\n", new, count=1, flags=re.M)
        assert "import folder_names" in new, py
    if new != src:
        py.write_text(new, encoding="utf-8"); done.append("plugin.py")
    target = plugin / "folder_names.py"
    if not target.exists() or target.read_bytes() != (HERE / "folder_names.py").read_bytes():
        shutil.copyfile(HERE / "folder_names.py", target); done.append("folder_names.py")

    src = js.read_text(encoding="utf-8")
    new = src
    if "fpRender(box, prefix, s, items)" not in new:
        head = new.index("function renderChecks(")
        at = new.index(HOOK_AT, head)
        new = new[:at] + HOOK + new[at:]
    new = block(new, (HERE / "folder-picker.js").read_text(encoding="utf-8"),
                "// ==== folder-picker:start", "// ==== folder-picker:end ====")
    if new != src:
        js.write_text(new, encoding="utf-8"); done.append("studio.js")

    if css.exists():
        src = css.read_text(encoding="utf-8")
        new = block(src, (HERE / "folder-picker.css").read_text(encoding="utf-8"),
                    "/* ==== folder-picker:start", "/* ==== folder-picker:end ==== */")
        if new != src:
            css.write_text(new, encoding="utf-8"); done.append("studio.css")
    return done


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(arg, main(arg) or "nichts zu tun")
