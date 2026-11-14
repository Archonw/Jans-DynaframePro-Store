# Jans DynaFrame-Pro-Projekte: wo was liegt

## Repos

| Repo | Zweck |
|---|---|
| `Archonw/Dynaframe-Testing` | **Test-Store.** Neue Packs und Updates kommen zuerst hierher (Branch `main`). Katalog: `DynaframPro/Jans-store/catalog.json` |
| `Archonw/Jans-DynaframePro-Store` | **Öffentlicher Store.** Katalog liegt direkt im Hauptverzeichnis: `catalog.json`, Packs unter `plugin_packs/` |
| `Archonw/Dynaframe-Stuff` | Nur noch Altes für die frühere Dynaframe-Version. **Keine Store-Dateien mehr dorthin.** Der alte Ordner `DynaframPro/Jans-store` wurde am 22.10.2026 gelöscht. |
| `Archonw/dynaframe-homeassistant` | Home-Assistant-Integration (HACS) |

Store-Adressen für DynaFrame:
- Öffentlich: `https://raw.githubusercontent.com/Archonw/Jans-DynaframePro-Store/main/catalog.json`
- Test: `https://raw.githubusercontent.com/Archonw/Dynaframe-Testing/main/DynaframPro/Jans-store/catalog.json`

## Links in Packs

Alle Links in Packs (Problem melden, Anleitungen, User-Agent, Quellen) zeigen auf den öffentlichen Store, **ohne** `DynaframPro/Jans-store/` im Pfad:
- Issues: `https://github.com/Archonw/Jans-DynaframePro-Store/issues/new?title=...`
- Modul-Anleitung: `https://github.com/Archonw/Jans-DynaframePro-Store/blob/main/plugin_packs/magic-frame/MODULES.md`
- Magic-Frame-Modulkatalog (fest in `plugin/addons.py`, `DEFAULT_CATALOG`): `https://raw.githubusercontent.com/Archonw/Jans-DynaframePro-Store/main/plugin_packs/magic-frame/modules/catalog.json`

Vor dem Veröffentlichen prüfen, dass in keiner ZIP noch `Dynaframe-Stuff`, `Dynaframe-Testing` oder `DynaframPro/Jans-store` steht.

## Veröffentlichen (Test-Store → öffentlicher Store)

1. ZIP und Vorschaubilder nach `plugin_packs/<pack>/` im öffentlichen Store kopieren.
2. Pack-Eintrag in `catalog.json` übernehmen, Pfade ohne `DynaframPro/Jans-store/`.
3. `size` und `checksum` (SHA-256) zur ZIP passend setzen, `updated` und `generated` aktualisieren.
4. Jede Änderung braucht eine **höhere Version** als die im öffentlichen Store, in `catalog.json` **und** in `dynaframe-package.json`/`manifest.json` in der ZIP. Sonst sehen Frames kein Update.
5. `download_url` zeigt auf ein **GitHub Release** des jeweiligen Repos (`https://github.com/<repo>/releases/download/<pack-id>-<version>/<Zip>.zip`), damit Downloads gezählt werden (seit 25.10.2026, getestet). Die ZIP trotzdem nach `plugin_packs/` committen: der Workflow `Pack-Releases` legt bei jedem Push auf `main` das fehlende Release aus der ZIP an (passend zu `size`/`checksum`) und korrigiert `download_url` selbst, auch wenn sie noch relativ ist oder aus dem Test-Store kopiert wurde. Darum nie eine ZIP bei gleicher Version austauschen: ein bestehendes Release wird nicht überschrieben. Zahlen: `python3 tools/downloads.py [owner/repo]`.
6. Magic-Mirror-Module zusätzlich in `plugin_packs/magic-frame/modules/catalog.json` eintragen bzw. Version erhöhen.
7. Die Pack-Tabellen in `README.md` (zwischen `<!-- packs:start -->` und `<!-- packs:end -->`) nicht von Hand pflegen: Sie werden aus `catalog.json` erzeugt (`python3 tools/build_readme.py`, macht auch der Workflow `Pack-Releases` bei jedem Push). Jeder Abschnitt ist alphabetisch sortiert. Neue Packs erscheinen automatisch mit dem ersten Satz ihrer Beschreibung; einen kürzeren Text legt man in `tools/readme_texts.json` fest.
8. Direkt auf `main` committen und pushen.

## Geparkte Packs (Test-Store zeigt nur, woran gearbeitet wird)

Veröffentlichte Packs verschwinden aus dem Test-Store, bleiben aber im Repo: `tools/park.py` verschiebt ihren Eintrag aus `DynaframPro/Jans-store/catalog.json` nach `DynaframPro/Jans-store/parked.json` (ZIPs und Bilder bleiben in `plugin_packs/`). Das läuft automatisch im Workflow `Pack-Releases` bei jedem Push und alle 3 Stunden: Geparkt wird jedes Pack, dessen Testversion **nicht höher** ist als die im öffentlichen Store. Packs mit neuerer Testversion bleiben sichtbar, bis sie veröffentlicht sind.

- Wieder daran arbeiten: `python3 tools/park.py unpark <id>`, dann Version erhöhen wie gewohnt. Oder einfach einen neuen Eintrag mit höherer Version in `catalog.json` schreiben: Der Katalog gewinnt, der geparkte Eintrag wird gelöscht.
- Von Hand parken (auch mit neuerer Testversion): `python3 tools/park.py park <id>` oder `"parked": true` in den Eintrag schreiben.
- Überblick: `python3 tools/park.py list`.
- Ein mit `unpark` zurückgeholtes Pack bleibt in derselben Version sichtbar, auch wenn es öffentlich gleich ist. Nach dem nächsten Veröffentlichen wird es wieder geparkt.
- Wer ein Pack bearbeitet, das nicht in `catalog.json` steht: zuerst in `parked.json` nachsehen.

## Plugin-Einstellungsseiten: immer nach Vorlage

Jede neue Plugin-Seite (und jede überarbeitete) wird nach `tools/plugin-vorlage/` gebaut: README.md dort lesen, Referenz ist Photo Mosaic (`tools/plugin-vorlage/referenz-foto-mosaik/`). Kurz: Kopf mit Sprachwahl, Status-Karte (Version zuletzt), eigene Karten, nur bei Bedarf Immich-/WebDAV-/Ordner-Karten aus der Referenz, als letzte Karte „Eine Playlist dafür“ (`own_playlist.py`), dann der Support-Fuß. Texte DE/EN/ES, im HTML in der Sprache von `<html lang>` vorbefüllt. ZIPs mit `tools/plugin-vorlage/make_zip.py` packen. Plugins, die Fotos aus DynaFrame nehmen, bekommen die Karte „Welche Fotos aus DynaFrame“ (`tools/plugin-vorlage/dynaframe-filter/`); Sterne usw. immer aus der Mediendatenbank, nie aus Playlist-Einträgen (die haben kein `rating`).
