# Baustein „Fotopositionen bleiben auf dem Rahmen“

Anlass (26.11.2026): Ein Nutzer hat in Photo Scanner die GPS-Koordinaten auf
„ausgeblendet“ gestellt und erwartet, dass dann nichts mehr an OpenStreetMap
geht. Jan wollte das für alle Plugins, die Fotopositionen nach draußen
schicken. Der Schalter ist **aus** voreingestellt (bisheriges Verhalten).

Ist er an, verlässt keine GPS-Position eines Fotos den Rahmen:

- keine Ortsnamen-Abfragen zu Fotopositionen (OpenStreetMap Nominatim),
- kein Wetter/keine Temperatur von damals am Fotoort (Open-Meteo-Archiv),
- keine Höhe über dem Meer am Fotoort (Open-Meteo Elevation),
- keine Sehenswürdigkeiten/Ortsinfos zum Fotoort (Wikipedia, Wikidata, Nominatim),
- keine Kartenkacheln am Fotoort (Photo Quiz: Szene und Handy zeigen dann nur die Küsten).

Was schon im Cache liegt, wird weiter gezeigt. **Die Heimat** (`HomeLat`/`HomeLon`
in den Einstellungen, ±0,02°) ist kein Foto und bleibt erlaubt, ebenso die
Ortssuche nach Text. Die Verbindungskarte prüft die betroffenen Dienste bei
Schalter an nicht mehr und zeigt `photo_privacy.note()`.

## Einbau

```
python3 tools/plugin-vorlage/photo-privacy/apply.py <pack-ordner> --uses places,weather
```

`--uses` nennt, was auf der Karte als betroffen steht: `places`, `weather`,
`elevation`, `sights`, `map`, dazu `guide` für den zusätzlichen Hinweis im
Travel Guide. Das Skript

- kopiert `photo_privacy.py` nach `plugin/`,
- setzt in `plugin.py` `import photo_privacy`, `SCHEMA.update(photo_privacy.SCHEMA)`
  (Einstellung `KeepPhotoPlaces`, bool) und `photo_privacy.bind(settings)`,
- setzt die Karte „Fotopositionen“ (`#photoPrivacy`, Haken `#KeepPhotoPlaces`)
  vor die Karte „Eine Playlist dafür“, Text in der Sprache von `<html lang>`,
- hängt `block.js` mit den Texten aus `texts.json` an `studio.js` (zwischen
  Marken; ein zweiter Lauf erneuert den Stand).

Von Hand: vor **jeder** Anfrage, die eine Fotoposition enthält,

```python
if photo_privacy.blocks(lat, lon):
    return ""            # bzw. None / nur Cache
```

und in der Verbindungskarte

```python
if photo_privacy.active():
    return _row(key, name, "ok", photo_privacy.note())
```

Danach testen: Schalter an, Plugin neu starten, im Log darf keine Anfrage an
die Dienste mit einer Fotoposition mehr auftauchen.

## Eingebaut (26.11.2026, Test-Store)

| Pack | Sperren in |
|---|---|
| Life Lines, Living Planet, Photo Life Story | `places.py` `Places.name` |
| Travel Map | `sources.py` `Places.name` |
| Travel Guide | `guide.py` `guide()` nur aus dem Cache; `plugin.py` zeigt neue Orte nur mit dem Namen aus dem Foto |
| On This Day, Photo Quiz, Travel Scrapbook, Comic Day | `weather.py` `then`/`days`/`today`/`place`, Comic Day zusätzlich `geo.py` `parts` und Verbindungskarte; On This Day „Wetter heute am Fotoort“ fällt aus; Photo Quiz ohne Kartenkacheln (`offlineMap` im Zustand) |
| Hall of Records, Photo Gala | `world.py` `fetch_elevations`/`fetch_temperatures`/`place`, Verbindungskarte |

Photo Scanner hat den Schalter nicht, dort hängt es an „GPS-Koordinaten: ausgeblendet“.
