# Ports auf dem Rahmen

Welche Ports DynaFrame und die Plugins aus Jans Store belegen. Unsere Plugins nehmen
ihren Standard-Port aus dieser Liste. Ist er belegt, weichen sie selbst aus (erst im
eigenen Block, dann ab 8180) und zeigen den Port auf ihrer Plugin-Seite; dort lässt er
sich auch von Hand festlegen. Technik: `ports/` (Baustein `plugin_ports.py`).

**Für andere Plugin-Autoren:** Bitte nehmt für eure Plugins Ports außerhalb von 8090
bis 8199, dann kommen wir uns nicht in die Quere. Belegt ein Plugin trotzdem einen
unserer Ports, weicht unseres aus. Wer mag, trägt seine tatsächlich genutzten Ports in
`~/.local/share/dfr/plugin-ports/<PluginId>.json` ein (Format siehe unten); unsere
Plugins meiden sie dann und Web Login zeigt den Plugin-Namen an.

## DynaFrame und System

| Port | Wer | Erreichbar |
|---|---|---|
| 22 | SSH | WLAN |
| 80 / 443 | DynaFrame-Weboberfläche (nginx), 443 mit Web Login HTTPS | WLAN |
| 139 / 445 | Samba | WLAN |
| 8001 | DynaFrame Engine | WLAN |
| 8003 | DynaFrame WebUI | WLAN |
| 8080 | DynaFrame Renderer | WLAN |
| 1900/udp | SSDP (YouTube Cast) | WLAN |

## Unsere Plugins

| Block | Standard | Plugin | Wofür |
|---|---|---|---|
| 8090–8094 | 8090 | YouTube Cast | Senden-Seite und DIAL für die YouTube-App |
| 8095–8098 | 8095 | Photo Cast | Handy-Seite und Upload (8097 ist Web Login, wird übersprungen) |
| 8099–8103 | 8099 | Photo Quiz | Handy-Seite zum Mitspielen |
| 8104–8109 | 8104 + 8105 | Photo Stories | Handy-Seite http + https (immer zwei Ports nebeneinander) |
| 8110–8114 | 8110 | Party Wall | Gäste-Seite |
| 8115–8119 | 8115 | Thumbs Up | Abstimmen am Handy |
| 8120–8179 | | frei | für neue Plugins, in Fünferblöcken |
| 8180–8999 | | Ausweichbereich | wenn ein Block voll ist |

Nur auf dem Rahmen selbst (127.0.0.1), nicht im WLAN:

| Port | Plugin |
|---|---|
| 8097 | Web Login (Anmeldedienst) |
| 9333 / 9334 | Web Page Button (Browser, YouTube-Seite) |
| 36783 | Playlist Music (Spotify-Player go-librespot) |
| zufällig | die Plugin-Seiten aller Plugins (`127.0.0.1:0`) |

## Format von plugin-ports/<PluginId>.json

```json
{"plugin": "ThumbsUp", "name": "Thumbs Up",
 "ports": {"phone": {"port": 8116, "span": 1, "proto": "tcp", "default": 8115, "lan": true}},
 "updated": "2026-11-13T09:00:00"}
```
