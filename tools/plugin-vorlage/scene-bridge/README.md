# Szene erreicht ihr Plugin auch mit DynaFrames HTTPS/Login

Seit DynaFrame 2026.11.14 gibt es eingebautes HTTPS mit Login. Ist es an, antwortet die
Weboberfläche auf dem Rahmen selbst nicht mehr (127.0.0.1:8003 → 403, Port 80 → 421/302).
Unsere Szenen laufen im Renderer unter `http://127.0.0.1:8001` (Engine) und holten ihre
Daten über `/Plugins/Advanced/<Plugin>/` der Weboberfläche. Das ging damit kaputt.

`plugin_bridge.js` wird **vor** den Szenen-Skripten geladen und schreibt auf dem Rahmen jede
Adresse mit `/Plugins/Advanced/<Plugin>/` auf die lokale Adresse der Plugin-Seite um
(`GET /plugins/<Plugin>/advanced-page` der Engine → `localUrl`). Abgedeckt: `fetch`,
`XMLHttpRequest`, `EventSource`, `src` von Bild/Video/Audio/`<source>`/Iframe,
`setAttribute("src")`, `style.backgroundImage` u. Ä. Startet das Plugin neu (neuer Port),
holt es die Adresse neu und wiederholt den `fetch` einmal.

Im Browser über die Weboberfläche (gleicher Ursprung) oder ohne DynaFrame-Login ändert sich
nichts. Das Plugin muss nichts ändern: Die Szenen-Endpunkte schicken schon
`Access-Control-Allow-Origin: *`.

**Pflicht für jede Szene, die Daten von ihrem Plugin holt.** Einbau:

    python3 tools/plugin-vorlage/scene-bridge/apply.py <pack>/dynamic

Getestet am 15.11.2026 mit Photo Mosaic auf Küche (ohne Baustein „antwortet nicht“, mit
Baustein läuft das Mosaik). Eingebaut in alle 53 Packs mit Szene → Plugin.

## Plugin nach einem Neustart sofort starten (21.11.2026)

Nach einem Neustart spielt DynaFrame die Playlist schon nach ~40 s, startet die Plugins aber
erst nach 180 s und dann einzeln alle 30 s (`/opt/dynaframe/engine/appsettings.json`,
`Plugins.StartupDelaySeconds` / `StartupBetweenPluginsDelaySeconds`, Reihenfolge = Ordner-
reihenfolge, keine Priorität). Mit ~80 Plugins kam Contact Sheet auf Küche erst nach 8,5 Minuten
dran, bis dahin stand „antwortet nicht“ auf dem Bild.

Die Brücke merkt das an `advanced-page` → `available:false` und ruft dann
`POST /plugins/<Plugin>/start` der Engine, aber nur, wenn das Plugin in `GET /plugins`
eingeschaltet ist und nicht läuft (höchstens alle 45 s je Plugin). Szenen können mit
`window.__dfrPluginBridge?.isStarting?.("<Plugin>")` „startet gerade …“ statt „antwortet nicht“
zeigen (Beispiel: Contact Sheet 0.1.6, `failText()` in `dynamic/scene.js`).
