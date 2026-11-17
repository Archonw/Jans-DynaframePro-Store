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

Mit DynaFrames eigenem HTTPS/Login (ab 2026.11.14) hören 8001, 8003 und 8080 nur noch auf
127.0.0.1. Aus dem WLAN gehen 8001/8080 nur mit Login (nginx 18001/18080), 8003 gar nicht,
Port 80 zeigt nur noch /Connect und Gäste-Seiten. Die Engine ist auf dem Rahmen selbst weiter
ohne Login erreichbar, die Weboberfläche nicht mehr (Szenen: `scene-bridge/`).

## Unsere Plugins

| Block | Standard | Plugin | Wofür |
|---|---|---|---|
| 8090–8094 | 8090 | YouTube Cast | Senden-Seite und DIAL für die YouTube-App |
| 8095–8098 | 8095 | Photo Cast | Handy-Seite und Upload (8097 ist Web Login, wird übersprungen) |
| 8099–8103 | 8099 | Photo Quiz | Handy-Seite zum Mitspielen |
| 8104–8109 | 8104 + 8105 | Photo Stories | Handy-Seite http + https (immer zwei Ports nebeneinander) |
| 8110–8114 | 8110 | Party Wall | Gäste-Seite |
| 8115–8119 | 8115 | Thumbs Up | Abstimmen am Handy |
| 8120–8124 | 8120 | Photobomber | Mitspielen am Handy |
| 8125–8129 | 8125 | Postcards | Senden-Seite im WLAN |
| 8130–8134 | 8130 | Time Capsule | Handy-Seite im WLAN (8130 http, 8131 https zum Aufnehmen) |
| 8135–8139 | 8135 | Guestbook | Gäste-Seite im WLAN (Eintragen mit Selfie) |
| 8140–8144 | 8140 | Photo Gala | Abstimmen am Handy |
| 8145–8149 | 8145, 8146 | Photo Booth | Handy-Seite (8145 http, 8146 https für die Kamera) |
| 8150–8154 | 8150 | Spot the Difference | Handy-Seite im WLAN (Fehlersuche) |
| 8155–8159 | 8155 | Secret Santa | Handy-Seite im WLAN (Wichteln: Anmelden, eigenes Los) |
| 8160–8164 | 8160 | Game Night | Handy-Seite im WLAN (Punkte, Würfel, Timer, Bestenliste) |
| 8170–8174 | 8170 | Trivia Night | Handy-Seite im WLAN (Mitspielen, Antworten, Runde einstellen) |
| 8175–8179 | 8175 | Music Quiz | Handy-Seite im WLAN (Jahr und Künstler raten, Thema wählen) |
| 8165–8169 | 8165 | Dynaframe's Magic Mirror | Handy-Seiten von Zusatzmodulen (Knowledge of the Day: Quiz am Handy) |
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
