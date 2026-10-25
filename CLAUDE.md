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
7. Direkt auf `main` committen und pushen.
