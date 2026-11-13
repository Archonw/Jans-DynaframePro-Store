# Vorlage für Plugin-Einstellungsseiten

Jans Regel (10.11.2026): **Jede neue Plugin-Seite wird nach diesem Grundgerüst
gebaut.** Bestehende Plugins werden bei der nächsten Änderung angeglichen.
Referenz ist Photo Mosaic 0.1.11 (`referenz-foto-mosaik/`, komplettes Pack zum
Abschauen und Kopieren).

Jans Regel (12.11.2026): **Plugin-Namen immer englisch**, in allen drei Sprachen
gleich (Plugin-Seite, Szene, Playlist, Store). Wird ein Plugin umbenannt, bekommen
seine Playlists den neuen Namen über `renamed_playlists.py`.

| Datei | Wofür |
|---|---|
| `referenz-foto-mosaik/` | Komplettes Pack: Seite (`plugin/studio/`), Plugin (`plugin/plugin.py`), Quellen inkl. Immich (`plugin/sources.py`), Szene (`dynamic/`) |
| `renamed_playlists.py` | Benennt Playlists mit altem Namen beim ersten Start nach einem Update um (Einbau im Docstring) |
| `own_playlist.py` | Gemeinsamer Baustein für die Karte „Eine Playlist dafür“ (Einbau im Docstring) |
| `immich-filter/` | Immich-Filter von Photo Mosaic als Baustein: `immich_filters.py` (Schema, Suche je Album × Person, Prüfen), `block.js` (Seite), `apply_ui.py` (setzt die Filtergruppen in eine Seite ein, Texte DE/EN/ES vorbefüllt). So eingebaut in Travel Map, Colour Calendar, On This Day. |
| `dynaframe-filter/` | DynaFrame-Filter von Photo Mosaic als Baustein: `dynaframe_filters.py` (Schema, `Matcher` sucht jedes Foto in der Mediendatenbank, sonst EXIF/XMP der Datei), `block.js` (Seite), `apply_ui.py` (setzt die Karte „Welche Fotos aus DynaFrame“ ein, Texte DE/EN/ES vorbefüllt). So eingebaut in Photo Mosaic, Travel Map, Colour Calendar, On This Day. Anleitung in `dynaframe-filter/README.md`. |
| `ports/` + `PORTS.md` | Für Plugins mit eigener Seite im WLAN (Handy-Seite usw.): Port-Liste, `plugin_ports.py` (belegten Port erkennen, ausweichen, merken, auf der Seite änderbar), Port-Feld für die Plugin-Seite. Pflicht für jedes Plugin, das einen Port öffnet. Anleitung in `ports/README.md`. |
| `make_zip.py` | ZIP mit richtigen Datei-/Ordnerrechten packen (sonst „Error“ im Store) |

## Aufbau der Seite (Reihenfolge der Karten)

1. **Kopf** (`<header class="hero">`): „Plugin-Seite“, Name, ein Satz was das Plugin macht + „Jede Änderung hier wird sofort gespeichert.“, Sprachwahl Deutsch/English/Español.
2. **Status** (`card-head` mit Knöpfen rechts, `<dl class="facts">` mit Kennzahlen, immer zuletzt **Version**, darunter `statusNote`). Kein Knopf „Playlist anlegen“ hier.
3. **Eigene Karten des Plugins** (was es zeigt, Aussehen, Zeitplan, „Über die Playlist legen“ usw.).
4. **Quellen-Karten, nur wenn sinnvoll** (alle drei aus der Referenz übernehmen, nicht neu erfinden):
   - **Immich-Server**: Adresse, API-Schlüssel, „Verbindung testen“, darunter `h3.sub` „Welche Fotos aus Immich“ mit den Filtergruppen (Was, Wer, Wo, Wann, Kamera, Text, Aussortieren, Weglassen) und am Ende `<details>` „So bekommst du einen API-Schlüssel“. Nur die Filter zeigen, die für das Plugin Sinn ergeben. Tipp: Growing Up übernimmt Adresse/Schlüssel aus `ImmichSlideshow/data/settings.json`, wenn die Felder leer sind; das lohnt sich auch für neue Immich-Plugins.
   - **Welche Fotos aus DynaFrame** (eigene Karte, vor der Immich-Karte): Filter für Fotos aus DynaFrame-Quellen (alle Fotos, Ordner, Playlists) nach Sternen, Ausrichtung, Megapixel, Ort, Zeitraum, Kamera/Objektiv, Text und Dateinamen, darunter „{n} von {m} Fotos passen“. **Gehört in jedes Plugin, das Fotos aus DynaFrame nimmt.** Baustein `dynaframe-filter/`. Gruppen weglassen, die keinen Sinn ergeben (z. B. „Wann“, wenn das Plugin die Tage selbst wählt).
   - **Volle Auflösung für WebDAV-Fotos**: nur wenn das Plugin Fotos größer als 512 px braucht.
   - **Weitere Ordner auf dem Rahmen**: nur bei der Quelle „Alle Fotos in DynaFrame“.
5. **Eine Playlist dafür**: immer die letzte Karte, wenn das Plugin eine Szene hat. Auswahl Nein / Ja, anlegen, ggf. Dauer, Hinweis, Statuszeile (`playlistNote`), Backend über `own_playlist.py`.
6. **Support-Fuß** (`<footer class="support">`): Issue-Link `https://github.com/Archonw/Jans-DynaframePro-Store/issues/new?title=[Name Version] `, Buy me a coffee mit QR. Unverändert aus der Referenz kopieren.

## Regeln für die Seite

- Texte in DE/EN/ES in `I18N` in `studio.js` (`key: [de, en, es]`), Elemente mit `data-i18n` / `data-i18n-html`.
- **Im HTML immer den Text in der Sprache von `<html lang>` hineinschreiben**, keine leeren Platzhalter: `applyLanguage()` kehrt früh zurück, wenn die Sprache gleich bleibt, dann bleibt ein leerer Platzhalter leer.
- Jede Änderung sofort speichern (`save({Name: Wert})` → `POST ./api/settings`), Stand alle paar Sekunden über `GET ./api/state` holen; Feld mit Fokus nicht überschreiben.
- Immer relative Pfade `./api/...` (die WebUI liefert die Seite unter `/Plugins/Advanced/<Plugin>/` aus).
- Geheimnisse (API-Schlüssel, Passwörter) nie zurückgeben: leer = behalten, Platzhalter „gespeichert – leer lassen zum Behalten“.
- Design: Farben/Abstände aus `studio.css` der Referenz übernehmen (Karten, `.grid`, `.field`, `.hint`, `.status`, `h3.sub`, `h4.group`, `.checks`), Handy-Breite muss gehen.
- Manifest-Texte (Plugins-Seite) auf Englisch; Seite und Szene folgen der Spracheinstellung im Plugin.

## Daten aus DynaFrame (gelernt mit Photo Mosaic 0.1.9/0.1.10)

- Sterne, Kamera, Datum, Ort usw. stehen in der **Mediendatenbank** (`GET /media/database?page=N&pageSize=500`, Antwort `{items, totalCount, …}`). DynaFrame liest dafür EXIF und XMP selbst, auch Sidecars `foto.jpg.xmp` (so schreibt Jans App StarSwipe die Sterne; `metadataSource: "xmp"`).
- **Playlist-Einträge (`/playlists/{id}/items`) haben `make`, `width`, `dateTaken`, aber kein Feld `rating`.** Für Filter nie den Playlist-Eintrag nehmen, sondern die Zeile der Mediendatenbank über `mediaFileId` oder Pfad (macht `dynaframe_filters.Matcher`). Eine Zeile ohne Feld `rating` ist kein Datenbank-Eintrag.
- Ordner-Einträge in Playlists (`contentType: "directory"`) beachten `includeSubfolders` und `isEnabled`.
- Bei 0 Treffern die alten Ergebnisse verwerfen, sonst zeigt das Plugin weiter die ungefilterten Fotos.
- In gespeicherte Dateien (`index.json`, `days.json` …) nie Schlüssel schreiben; Einlese-Signaturen nur als SHA-256 speichern (die Dateien sind auf dem Rahmen für alle lesbar).

## Regeln fürs Pack (Kurzfassung, Details in den Projektnotizen)

- `requirements.txt` enthält immer `requests`; `plugin.connect_sse()` und `plugin.ready()` vor langsamer Einrichtung.
- Aktions-IDs nur `^[a-z][a-z0-9-]*$`.
- Szene ruft `window.DynaFrameScene?.ready?.()` auf, sobald sie etwas zeigt (+ ~8 s Rückfall).
- Takeover-Plugins: Schutz gegen übrig gebliebene Takeover-Playlist (`/mnt/project-files/takeover-stop/leftover.py`).
- Szene+Plugin = Pack-Typ `integration`; Version in `dynaframe-package.json`, `plugin/manifest.json` und Katalog erhöhen; ZIP mit `make_zip.py` packen.
