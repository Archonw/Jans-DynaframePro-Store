# Vorlage für Plugin-Einstellungsseiten

Jans Regel (10.11.2026): **Jede neue Plugin-Seite wird nach diesem Grundgerüst
gebaut.** Bestehende Plugins werden bei der nächsten Änderung angeglichen.
Referenz ist Foto Mosaik 0.1.7 (`referenz-foto-mosaik/`, komplettes Pack zum
Abschauen und Kopieren).

| Datei | Wofür |
|---|---|
| `referenz-foto-mosaik/` | Komplettes Pack: Seite (`plugin/studio/`), Plugin (`plugin/plugin.py`), Quellen inkl. Immich (`plugin/sources.py`), Szene (`dynamic/`) |
| `own_playlist.py` | Gemeinsamer Baustein für die Karte „Eine Playlist dafür“ (Einbau im Docstring) |
| `immich-filter/` | Immich-Filter von Foto Mosaik als Baustein: `immich_filters.py` (Schema, Suche je Album × Person, Prüfen), `block.js` (Seite), `apply_ui.py` (setzt die Filtergruppen in eine Seite ein, Texte DE/EN/ES vorbefüllt). So eingebaut in Reisekarte, Farbkalender, Heute vor X Jahren. |
| `make_zip.py` | ZIP mit richtigen Datei-/Ordnerrechten packen (sonst „Error“ im Store) |

## Aufbau der Seite (Reihenfolge der Karten)

1. **Kopf** (`<header class="hero">`): „Plugin-Seite“, Name, ein Satz was das Plugin macht + „Jede Änderung hier wird sofort gespeichert.“, Sprachwahl Deutsch/English/Español.
2. **Status** (`card-head` mit Knöpfen rechts, `<dl class="facts">` mit Kennzahlen, immer zuletzt **Version**, darunter `statusNote`). Kein Knopf „Playlist anlegen“ hier.
3. **Eigene Karten des Plugins** (was es zeigt, Aussehen, Zeitplan, „Über die Playlist legen“ usw.).
4. **Quellen-Karten, nur wenn sinnvoll** (alle drei aus der Referenz übernehmen, nicht neu erfinden):
   - **Immich-Server**: Adresse, API-Schlüssel, „Verbindung testen“, darunter `h3.sub` „Welche Fotos aus Immich“ mit den Filtergruppen (Was, Wer, Wo, Wann, Kamera, Text, Aussortieren, Weglassen) und am Ende `<details>` „So bekommst du einen API-Schlüssel“. Nur die Filter zeigen, die für das Plugin Sinn ergeben. Tipp: Growing Up übernimmt Adresse/Schlüssel aus `ImmichSlideshow/data/settings.json`, wenn die Felder leer sind; das lohnt sich auch für neue Immich-Plugins.
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

## Regeln fürs Pack (Kurzfassung, Details in den Projektnotizen)

- `requirements.txt` enthält immer `requests`; `plugin.connect_sse()` und `plugin.ready()` vor langsamer Einrichtung.
- Aktions-IDs nur `^[a-z][a-z0-9-]*$`.
- Szene ruft `window.DynaFrameScene?.ready?.()` auf, sobald sie etwas zeigt (+ ~8 s Rückfall).
- Takeover-Plugins: Schutz gegen übrig gebliebene Takeover-Playlist (`/mnt/project-files/takeover-stop/leftover.py`).
- Szene+Plugin = Pack-Typ `integration`; Version in `dynaframe-package.json`, `plugin/manifest.json` und Katalog erhöhen; ZIP mit `make_zip.py` packen.
