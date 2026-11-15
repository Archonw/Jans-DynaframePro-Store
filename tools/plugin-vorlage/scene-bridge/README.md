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
