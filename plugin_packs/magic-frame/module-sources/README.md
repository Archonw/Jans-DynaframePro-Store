# Module sources

Unpacked sources of the add-on modules for Dynaframe's Magic Mirror, as examples for your own modules or for porting MagicMirror² modules. The guide is [MODULES.md](../MODULES.md).

| Folder | What it shows | Rebuild of |
|---|---|---|
| `homeassistant` | values, house status, room climate, presence and bin collection from Home Assistant in one module with a view per instance; one login shared via `ctx["shared"]`, rooms from HA areas via `/api/template` | |
| `wifi` | network name, password and a QR code; the QR library is bundled into `module.js` (`module.src.js` + `lib/`, built with `build.sh`) | MMM-WiFiPassword |
| `webuntis` | timetable, exams, homework; QR or password login in `fetch.py` | MMM-Webuntis |
| `musicassistant` | now playing via a WebSocket written with the Python standard library | MMM-MusicAssistant |
| `jellyfin` | now playing on a Jellyfin server | |
| `traveltime` | travel time by car with traffic from Mapbox or the Google Routes API (own key), "leave by" for an arrival time, German motorway incidents near the route; results cached in `fetch.py` between fetches | |
| `pegelstand` | river level from PEGELONLINE, the smallest example | |

The installable ZIPs are in [../modules](../modules).
