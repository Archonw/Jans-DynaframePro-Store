# Ports für Plugins mit eigener Seite im WLAN

Baustein für Plugins, die einen Port im Heimnetz öffnen (Handy-Seite, Gäste-Seite,
Upload, DIAL). Die Port-Liste steht in [PORTS.md](../PORTS.md).

| Datei | Wofür |
|---|---|
| `plugin_ports.py` | `PortKeeper`: Port suchen, wirklich öffnen, merken, auf Wunsch wechseln; Liste `RESERVED`/`BLOCKS` |
| `block.js` | Port-Feld für die Plugin-Seite (Texte DE/EN/ES), wird als `studio/port_block.js` kopiert |
| `block.html` | HTML dazu, `apply_ui.py` setzt es in der Sprache von `<html lang>` ein |
| `apply_ui.py` | `python3 apply_ui.py <plugin>/studio/index.html`: Block einsetzen (an `<!-- port-block -->` oder nach `id="phoneNote"`), Script einbinden, `port_block.js` kopieren |

## So verhält sich ein Plugin

1. Beim Start wird der Port **wirklich geöffnet**, nicht nur in der Liste nachgeschaut.
   Ist er belegt, egal von wem (fremdes Plugin, DynaFrame, irgendein Dienst), kommt
   der nächste: zuletzt genutzter Port, Standard-Port, eigener Block, dann 8180 bis 8999.
   Ports anderer unserer Plugins (laut Liste und laut `~/.local/share/dfr/plugin-ports/`)
   werden übersprungen.
2. Der gefundene Port steht in `data/ports.json` (`last`) und wird beim nächsten Start
   zuerst genommen, damit Kurzbefehle und Lesezeichen weiter passen.
3. Auf der Plugin-Seite: Feld „Port“ (leer = automatisch, Zahl = fest), Statuszeile
   („Läuft auf Port 8116 statt 8115. Port 8115 von … war belegt.“), Knopf „Zurück auf
   Port 8115“. Der Wechsel geht ohne Neustart: neuer Port auf, dann alter zu. QR-Code und
   Adresse kommen aus `phone_url()` und passen sich von selbst an.
4. Jedes Plugin schreibt seine Ports nach `~/.local/share/dfr/plugin-ports/<PluginId>.json`.
   Web Login (ab 0.4.2) zeigt damit den Plugin-Namen in der Portliste und zieht in der
   strengen Firewall eine Freigabe mit, wenn ein Plugin umzieht.

## Einbau

```python
import plugin_ports

PORTS = plugin_ports.PortKeeper(PLUGIN_ID, "Thumbs Up", DATA_DIR, default=8115, env="THUMBSUP_PORT",
                                log=lambda text, level="info": log(text, level),
                                language=lambda: settings()["Language"])

def start_phone():
    PORTS.start(lambda port: ThreadingHTTPServer(("0.0.0.0", port), PhoneHandler))

def phone_url():
    return f"http://{lan_ip()}:{PORTS.port}/" if PORTS.port else ""

# state:        "port": PORTS.status()
# Plugin-Seite: POST ./api/port  ->  self._json(PORTS.change(body.get("port")))
# STUDIO_FILES: "/port_block.js": ("studio/port_block.js", "application/javascript; charset=utf-8")
# studio.js render(): if (window.PortBlock) PortBlock.render(state.port, lang);
# shutdown():   PORTS.stop()
```

Zwei Ports nebeneinander (Photo Stories: http auf Port, https auf Port + 1): `span=2`,
`make_server(port)` gibt eine Liste zurück und schließt bei `OSError` selbst, was schon offen war.
Eigene Dienste wie DIAL (YouTube Cast, `dial.py`) bekommen den `PortKeeper` übergeben und
lesen `keeper.port`.

Neues Plugin mit Port: nächsten freien Fünferblock aus PORTS.md nehmen, in `BLOCKS`
(plugin_ports.py) **und** PORTS.md eintragen, Baustein in alle Plugins mit Port neu kopieren.
