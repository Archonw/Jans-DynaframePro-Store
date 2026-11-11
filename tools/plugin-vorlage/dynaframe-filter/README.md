# DynaFrame-Filter (Baustein)

Die Karte „Welche Fotos aus DynaFrame“ von Foto Mosaik für andere Plugins: Fotos aus
DynaFrame-Quellen (alle Fotos, Ordner, Playlists) nach Sternen, Ausrichtung, Megapixel,
Ort, Zeitraum, Kamera, Objektiv, Text und Dateinamen filtern. Die Daten kommen aus der
Mediendatenbank von DynaFrame; Fotos, die sie nicht kennt, liest `file_meta()` selbst
(Sterne aus XMP in der Datei oder `foto.jpg.xmp` daneben, EXIF mit Pillow, falls da).

## Einbau

1. `dynaframe_filters.py` nach `plugin/` kopieren, `import dynaframe_filters`.
2. Schema: `**dynaframe_filters.schema(without=(...))` in `SCHEMA`. Die Arten `date`/`name`
   gehen durch `dynaframe_filters.coerce(spec, raw)` (oder `immich_filters.coerce`, gleich).
3. Einlese-Signatur: `dynaframe_filters.signature(values)` hineinnehmen, damit eine
   Filteränderung neu einliest (Signatur als SHA-256 speichern).
4. Beim Einlesen, einmal pro Durchlauf:

   ```python
   match = None
   if dynaframe_filters.active(values):
       match = dynaframe_filters.Matcher(values, lambda: dynaframe.library_rows(stop),
                                         cache_file=str(DATA_DIR / "file_meta.json"), log=log)
   # für Quellen library / playlist / folders, Schlüssel "d:<id>|<pfad>" oder "f:<pfad>":
   rows = [r for r in rows if match.keep(key_of(r))]
   ...
   match.save(); _data["dfCount"] = match.counts()      # und "dfCount" in /api/state
   ```

5. Seite: im HTML eine Zeile `<!-- dynaframe-filters -->` vor die Immich-Karte setzen, dann

   ```
   python3 apply_ui.py <pack-ordner> <foto-mosaik>/plugin/studio <config>
   ```

   (`config` in `CONFIGS`: welche Gruppen/Felder wegfallen, `all` = alles). In `render()`
   nach `ifRender(s)` die Zeile `dfRender(s, state);` ergänzen.

## Getestet

Mit der nachgebauten Engine von Foto Mosaik (`fotomosaik/test/mock_engine.py`: Playlist 5 =
Einträge wie auf Jans Rahmen, ohne `rating`) in Reisekarte, Farbkalender und Heute vor X
Jahren; Sidecar im StarSwipe-Format über `file_meta()`.
