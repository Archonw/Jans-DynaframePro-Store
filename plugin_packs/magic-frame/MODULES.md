# Writing a Dynaframe's Magic Mirror module

This guide is complete on its own: you can hand it to an AI assistant together with a module of the original [MagicMirror²](https://github.com/MagicMirrorOrg/MagicMirror) (its GitHub link or files) and ask it to rebuild that module for Dynaframe's Magic Mirror. See [Porting a MagicMirror² module](#porting-a-magicmirror-module) below.

A Dynaframe's Magic Mirror module is a folder with up to four files:

```
magicframe/
  module.json   what the module is called and which settings it has (required)
  module.js     draws the module in the scene (required)
  module.css    extra styles (optional)
  fetch.py      fetches data on the frame (optional)
```

Modules reach Dynaframe's Magic Mirror in four ways. The first three do **not** show up as a separate plugin in DynaFrame's Plugins overview:

1. **Module catalog** (recommended): a JSON list of modules that the plugin page shows under "More modules" with an Install / Update button. Jan's catalog is built in; anyone can publish their own and users add its link under "Other sources":

   ```json
   {"name": "My modules", "modules": [
     {"type": "yourname.thing", "name": {"en": "Thing"}, "description": {"en": "…"},
      "version": "1.0.0", "author": "You", "url": "https://github.com/you/thing", "zip": "thing.zip"}
   ]}
   ```
   `zip` may be relative to the catalog. Bump `version` to offer an update.
2. **ZIP link** pasted on the plugin page. The ZIP contains the files above, at the top level or in one folder.
3. **DynaFrame store entry** with `"type": "magic-mirror-module"` whose `download_url` points at the module ZIP (files inside one folder, e.g. `magicframe-thing/module.json`). The store only knows plugin, integration, fontpack (font files only), overlay and theme, and unpacks any other type as media into `~/Pictures/<entry title>/`, where Dynaframe's Magic Mirror finds the module. Remove it in the store.
4. **Inside another installed DynaFrame plugin** that has a `magicframe/` folder. This works too, but that plugin then appears in the Plugins overview.

After that, the module appears under **Add module** like a built-in one, and its settings form is generated from `module.json`.

## module.json

```json
{
  "type": "pegelstand",
  "name": {"de": "Pegelstand", "en": "River level", "es": "Nivel del río"},
  "description": {"de": "…", "en": "…", "es": "…"},
  "version": "1.0.0",
  "author": "Your name",
  "url": "https://github.com/you/your-module",
  "region": "top_right",
  "script": "module.js",
  "style": "module.css",
  "fetch": "fetch.py",
  "every": 900,
  "visibleOnly": false,
  "place": false,
  "fields": [
    {"key": "station", "kind": "text", "default": "MAINZ",
     "label": {"de": "Pegel", "en": "Gauge", "es": "Estación"},
     "hint": {"en": "All gauges: pegelonline.wsv.de"}}
  ]
}
```

- `type`: unique id, lowercase letters, digits, `.`, `_`, `-` (2–48 chars). Use a prefix such as `yourname.weather` to avoid clashes. Built-in types (`clock`, `weather`, `forecast`, `rain`, `calendar`, `news`, `departures`, `compliments`, `warnings`, `homeassistant`, `webpage`) are taken.
- Texts (`name`, `description`, `label`, `hint`, option labels) are a string or `{"de", "en", "es"}`; missing languages fall back to English.
- `region`: where the module lands when added: `top_bar`, `top_left`, `top_center`, `top_right`, `middle_left`, `middle_center`, `middle_right`, `bottom_left`, `bottom_center`, `bottom_right`, `bottom_bar`.
- `every`: seconds between fetches (30 to 86400; down to 10 with `visibleOnly`). `visibleOnly`: only fetch while the scene is on screen (for data that changes by the minute). `place`: the module needs the location set on the page (`ctx["lat"]`, `ctx["lon"]`).
- `fields[].kind`: `text`, `textarea`, `number` (with `min`/`max`), `bool`, `select` (with `options: [{"value", "label"}]`), `secret` (passwords and tokens: never sent to the scene or back to the page), `stop` (a public transport stop picked via search). `showIf: {"otherKey": "value"}` shows a field only for that value. Every module also gets a `header` field automatically.

## module.js

```js
(function () {
  const { esc, t } = window.MagicFrame.helpers;
  window.MagicFrame.register("pegelstand", {
    render(el, ctx) {
      if (!ctx.data) { el.innerHTML = '<div class="xsmall dimmed">…</div>'; return true; }
      el.innerHTML = `<div class="medium bright">${ctx.h.number(ctx.data.cm)} cm</div>`;
      // return false to hide the module, e.g. when there is nothing to show
    },
    tick(el, ctx) { /* optional: runs every second */ },
  });
})();
```

`render` runs when the settings or the data change. `ctx` has:

| | |
|---|---|
| `config` | the module's settings (secrets are empty, `has_<key>` says whether one is set) |
| `data` | what `fetch.py` returned last (or `null`) |
| `error` | a readable error text if the last fetch failed |
| `at` | when the data was fetched (epoch seconds) |
| `lang` | `de`, `en` or `es` |
| `region`, `place`, `clock24` | where the module is, the location name, 24-hour clock |
| `h` | helpers: `esc`, `t({de,en,es}, values)`, `time(epoch)`, `dayName(epoch)`, `number(v, digits)`, `degrees(v, imperial)`, `icon(name)`, `weatherIcon(wmoCode, isDay)`, `weatherText(wmoCode)`, `nowSec()` |

CSS classes from MagicMirror work as you'd expect: `xsmall small medium large xlarge`, `bright normal dimmed`, `light thin`. Text alignment follows the region (left, right, centre). Each module sits in `<section class="module m-<type>">` (characters other than `a-z0-9-` in the type become `-`, so `yourname.thing` gets `m-yourname-thing`). Scope your own CSS with that class as the ancestor, e.g. `.m-pegelstand .trend`, and do not give your own inner elements the same class.

## fetch.py

```python
def fetch(config, ctx):
    row = ctx["get"]("https://example.org/api", params={"q": config["station"]})
    return {"cm": row["value"]}
```

Dynaframe's Magic Mirror imports this file in its own Python process and calls `fetch(config, ctx)` on the `every` schedule. Return anything JSON-serialisable; it becomes `ctx.data` in the scene. `ctx` has `lat`, `lon`, `lang`, `imperial`, `get(url, params=None, headers=None, expect="json"|"text")` (with Dynaframe's Magic Mirror's User-Agent and timeouts), `SourceError(code, detail)` and `log(text)`. Raise `ctx["SourceError"]("unreachable")`, `("key")`, `("format")`, `("http:503")` etc. for readable errors on the page.

Use only the Python standard library and `requests` (and `icalendar`, which Dynaframe's Magic Mirror already has): your plugin's own requirements may live in a different environment.

## Packaging and publishing

Put the files in one folder named `magicframe-<type>/` and zip that folder. The same ZIP works for all three ways in: as a ZIP link, in a module catalog and as a store entry. To offer an update, raise `version` in `module.json` and in your catalog or store entry.

A store entry in a DynaFrame store `catalog.json` looks like this (`size` in bytes and `checksum` as SHA-256 of the ZIP):

```json
{"id": "magic-mirror-module-thing", "type": "magic-mirror-module", "title": "Magic Mirror module: Thing",
 "author": "You", "description": "Module for Dynaframe's Magic Mirror (install that first). …",
 "version": "1.0.0", "download_url": "plugin_packs/thing.zip", "size": 1234, "checksum": "…"}
```

## Porting a MagicMirror² module

A MagicMirror² module (`MMM-Something`) runs in a browser with a Node.js helper next to it. Dynaframe's Magic Mirror has the same split, but with Python on the frame instead of Node.js and no configuration file: users set everything on the plugin page. Map the parts like this:

| MagicMirror² | Dynaframe's Magic Mirror |
|---|---|
| `config.js` entry with `module`, `position`, `config: {…}` | `module.json`: `region` is the default position (`top_left` etc. use the same names), each config option becomes a field in `fields` with a label in de/en/es |
| `defaults` in `Module.register` | `default` of each field |
| `node_helper.js` (fetching, logins, sockets, npm packages) | `fetch.py` with `fetch(config, ctx)`, standard library and `requests` only; whatever it returns arrives as `ctx.data` |
| `sendSocketNotification` / `socketNotificationReceived` | not needed: `fetch.py` returns data, `render` draws it |
| `updateInterval` / `setInterval` in the helper | `every` (seconds) in `module.json`, with `visibleOnly: true` for data that is only worth fetching while the scene is visible |
| `getDom()` | `render(el, ctx)` writing `el.innerHTML`; return `false` to hide the module |
| `updateDom()` every second (clocks, progress bars) | `tick(el, ctx)` |
| `getStyles()` | `module.css` |
| `getTranslations()` | `ctx.h.t({de, en, es})` and `ctx.lang` |
| `this.config.lat/lon`, location options | `"place": true` and `ctx["lat"]`, `ctx["lon"]` in `fetch.py` |
| passwords, API keys, tokens | fields with `"kind": "secret"`; they reach `fetch.py` but never the scene |

Things that differ from MagicMirror² and catch people out:

- There is no `node_helper`, no npm and no `require`. Rewrite what the helper does in Python. Third-party JavaScript for the scene (e.g. a QR code library) has to be bundled into `module.js` itself; the scene loads only `module.js` and `module.css`.
- `render` runs only when the settings or the data change. Show a placeholder while `ctx.data` is `null`. If `fetch.py` fails before any data arrived, the core shows the error text itself and does not call `render` or `tick`.
- `ctx["SourceError"]("code", "detail")` with one of the known codes (`no-key`, `login`, `key`, `unreachable`, `format`, `ssl`, `quota`, `http:NNN`) gives a translated message. Any other code is shown as written, so a module can raise its own readable text, e.g. `SourceError(ctx["lang"] == "de" and "Kein Schüler gefunden" or "No student found")`.
- After an error the next fetch waits between 1 and 5 minutes.
- Times from `fetch.py` are best sent as epoch seconds; format them in `module.js` with `ctx.h.time()` and `ctx.h.dayName()` so they follow the user's language and clock.
- Sizes: use the MagicMirror classes (`small`, `medium` …) or `calc(n * var(--u))` in CSS, so modules scale with the screen. Do not use fixed pixel sizes.
- Test both landscape and portrait: regions are narrower in portrait.

Working examples, each a rebuild of a MagicMirror² module, are in [module-sources](https://github.com/Archonw/Jans-DynaframePro-Store/tree/main/plugin_packs/magic-frame/module-sources): `wifi` (MMM-WiFiPassword, with a bundled QR library), `webuntis` (MMM-Webuntis, with logins), `musicassistant` (MMM-MusicAssistant, WebSocket in pure Python), `jellyfin` and `pegelstand`.

## Trust

Add-on modules run with the same rights as Dynaframe's Magic Mirror. Only install modules you trust.
