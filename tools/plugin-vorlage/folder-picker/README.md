# Ordnerliste „Ausgewählte Ordner in DynaFrame“ (Baustein)

Wunsch des DynaFrame-Entwicklers (Discord, 20.11.2026): Die Ordnerliste zeigte volle
Pfade (`/home/pi/Pictures/...`), lange Namen wurden auf dem Handy abgeschnitten und sahen
alle gleich aus. Jetzt:

- Jeder Ordner steht **ab seinem Medienordner** da: Ordnername fett, Oberordner klein
  darunter, lange Namen brechen um. Der Medienordner selbst heißt z. B. „Pictures“ mit
  „Nur die Fotos direkt in diesem Ordner“.
- Gibt es mehrere Medienordner (DynaFrame-Medienordner, eigene Ordner aus „Weitere
  Ordner“, WebDAV), bekommt jeder eine kleine Überschrift mit dem vollen Pfad.
- Unter der Liste: „Ordner fehlt?“ klappt die Karte „Weitere Ordner“ auf (Akkordeon).
- Gespeichert wird weiter der **volle Pfad** (`TileDirs` usw.), alte Einstellungen gelten.

## Einbau

    python3 tools/plugin-vorlage/folder-picker/apply.py <pack-ordner>

Kopiert `folder_names.py` nach `plugin/`, stellt `list_folders()` in `plugin.py` auf
`folder_names.listing(counts, dynaframe.media_folders(), Folders)` um, setzt in
`renderChecks()` den Haken auf `fpRender()` und hängt `folder-picker.js/.css` an
`studio.js/.css` (zwischen Marken, ein zweiter Lauf erneuert den Stand).
`/api/folders` liefert je Ordner `id` (voller Pfad), `name`, `leaf`, `parent`, `top`,
`root`, `rootPath`, `count`. Ältere Seiten ohne `leaf` zeigen weiter `name`.

Neue Plugins mit Ordnerquelle: aus der Referenz (Photo Mosaic) kopieren, dort ist der
Baustein schon drin.

## Getestet

Nachgebaute Engine mit Ordnern unter `/home/pi/Pictures` und einem NAS-Ordner, Handybreite
390 px (Vorher/Nachher: `/mnt/project-files/folder-picker/before-after-phone.png`).
Nebenbei: `accordion.css` setzt `.card[data-fold] { min-width: 0 }`, sonst war die Seite
auf dem Handy durch die Plakette breiter als der Bildschirm.
