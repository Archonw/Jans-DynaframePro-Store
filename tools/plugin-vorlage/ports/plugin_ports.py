"""Ports für Plugins, die im WLAN eine eigene Seite anbieten (Handy-Seite usw.).

Baustein aus tools/plugin-vorlage/ports (Jans Store). Kopie neben plugin.py legen.

Was er macht
------------
- Jedes unserer Plugins hat einen festen Standard-Port und einen kleinen Block
  dahinter (Liste unten in RESERVED, für Menschen in PORTS.md).
- Beim Start wird der Port wirklich geöffnet. Ist er belegt, egal von wem
  (fremdes Plugin, DynaFrame, irgendein Dienst), nimmt das Plugin den nächsten
  freien: erst im eigenen Block, dann ab 8180 aufwärts. Ports, die zu einem
  anderen unserer Plugins gehören, werden dabei übersprungen.
- Der gefundene Port wird gemerkt (data/ports.json) und beim nächsten Start
  zuerst genommen, damit Kurzbefehle und Lesezeichen weiter passen.
- Auf der Plugin-Seite kann man einen Port von Hand festlegen (leer = automatisch).
  Der Wechsel geht ohne Neustart: neuer Port auf, dann alter zu.
- Jedes Plugin trägt seine tatsächlichen Ports in
  ~/.local/share/dfr/plugin-ports/<PluginId>.json ein. Daraus liest Web Login,
  welcher Port zu welchem Plugin gehört, und andere Plugins weichen aus.

Einbau (Kurzfassung, Beispiel Thumbs Up)
----------------------------------------
    import plugin_ports
    PORTS = plugin_ports.PortKeeper(PLUGIN_ID, "Thumbs Up", DATA_DIR, default=8115,
                                    env="THUMBSUP_PORT", log=log)

    def start_phone():
        PORTS.start(lambda port: ThreadingHTTPServer(("0.0.0.0", port), PhoneHandler))

    phone_url():   PORTS.port statt phone_server.server_address[1]
    state:         "port": PORTS.status()
    Plugin-Seite:  POST ./api/port {"port": 8120 | ""}  ->  self._json(PORTS.change(body.get("port")))
    shutdown():    PORTS.stop()

make_server(port) gibt einen Server oder eine Liste von Servern zurück (Photo
Stories: http auf port, https auf port + 1, dann span=2) und wirft OSError, wenn
ein Port belegt ist. Teilweise geöffnete Server schließt make_server selbst.
"""

from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from pathlib import Path

DFR_DATA_DIR = Path(os.environ.get("DFR_DATA_DIR", Path.home() / ".local" / "share" / "dfr"))
REGISTRY_DIR = DFR_DATA_DIR / "plugin-ports"
PLUGINS_DIR = DFR_DATA_DIR / "plugins"

# Feste Ports auf dem Rahmen. Plugin-ID (Name im Manifest) oder "system".
# Neue Plugins: nächsten freien Block nehmen und hier + in PORTS.md eintragen.
RESERVED = {
    # DynaFrame und System
    22: ("system", "SSH"), 80: ("system", "DynaFrame WebUI (nginx)"), 443: ("system", "HTTPS"),
    139: ("system", "Samba"), 445: ("system", "Samba"),
    8001: ("system", "DynaFrame Engine"), 8003: ("system", "DynaFrame WebUI"), 8080: ("system", "DynaFrame renderer"),
    # unsere Plugins, nur auf dem Rahmen selbst (127.0.0.1)
    8097: ("WebLogin", "Web Login (login service)"),
    9333: ("webpages", "Web Page Button (browser)"), 9334: ("webpages", "Web Page Button (YouTube page)"),
    36783: ("PlaylistMusic", "Playlist Music (Spotify player)"),
}
# Blöcke unserer Plugins im WLAN: (erster, letzter) Port, der erste ist der Standard.
BLOCKS = {
    "YouTubeCast": (8090, 8094, "YouTube Cast"),
    "PhonePhotos": (8095, 8098, "Photo Cast"),
    "PhotoQuiz": (8099, 8103, "Photo Quiz"),
    "PhotoStories": (8104, 8109, "Photo Stories"),
    "PartyWall": (8110, 8114, "Party Wall"),
    "ThumbsUp": (8115, 8119, "Thumbs Up"),
    # 8120 bis 8179: für neue Plugins, in Fünferblöcken vergeben
}
OVERFLOW = (8180, 8999)     # hierhin weichen Plugins aus, wenn ihr Block voll ist
LOWEST = 1024               # darunter darf ein Plugin (Benutzer pi) nicht öffnen
TEXTS = {
    "busy": ("Port {port} ist belegt{by}.", "Port {port} is in use{by}.", "El puerto {port} está ocupado{by}."),
    "by": (" (von {who})", " (by {who})", " (por {who})"),
    "range": ("Bitte einen Port zwischen {low} und 65535 angeben.", "Please enter a port between {low} and 65535.",
              "Indica un puerto entre {low} y 65535."),
    "reserved": ("Port {port} gehört zu {who}. Bitte einen anderen nehmen.",
                 "Port {port} belongs to {who}. Please pick another one.",
                 "El puerto {port} pertenece a {who}. Elige otro."),
    "none": ("Kein freier Port gefunden.", "No free port found.", "No se encontró ningún puerto libre."),
}


def _text(key, language, **values):
    row = TEXTS[key]
    index = {"de": 0, "en": 1, "es": 2}.get((language or "de")[:2], 1)
    return row[index].format(**values)


def owner_of(port, plugin_id=None):
    """Name dessen, dem der Port laut Liste/Registry gehört (ohne das eigene Plugin)."""
    for other, entry in read_registry().items():
        if other == plugin_id:
            continue
        for item in entry.get("ports", {}).values():
            first = int(item.get("port") or 0)
            if first and first <= port < first + int(item.get("span") or 1):
                return entry.get("name") or other
    if port in RESERVED and RESERVED[port][0] != plugin_id:
        return RESERVED[port][1]
    for other, (low, high, name) in BLOCKS.items():
        if other != plugin_id and low <= port <= high:
            return name
    return ""


def reserved_for_others(plugin_id):
    """Alle Ports, die einem anderen gehören (Liste + was andere Plugins gerade nutzen)."""
    taken = {p for p, (owner, _name) in RESERVED.items() if owner != plugin_id}
    for other, (low, high, _name) in BLOCKS.items():
        if other != plugin_id:
            taken.update(range(low, high + 1))
    for other, entry in read_registry().items():
        if other == plugin_id:
            continue
        for item in entry.get("ports", {}).values():
            first = int(item.get("port") or 0)
            if first:
                taken.update(range(first, first + int(item.get("span") or 1)))
    return taken


def read_registry():
    """{plugin_id: eintrag} aller Plugins, die noch installiert sind."""
    found = {}
    try:
        files = list(REGISTRY_DIR.glob("*.json"))
    except OSError:
        return found
    for path in files:
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        plugin_id = path.stem
        if not isinstance(entry, dict):
            continue
        if PLUGINS_DIR.is_dir() and not (PLUGINS_DIR / plugin_id).is_dir():
            continue        # Plugin wurde entfernt, Eintrag ist alt
        found[plugin_id] = entry
    return found


def who_listens(port):
    """Bestmöglich herausfinden, welches Programm auf dem Port lauscht."""
    inodes = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) > 9 and parts[3] == "0A" and int(parts[1].rsplit(":", 1)[1], 16) == port:
                inodes.add(parts[9])
    if not inodes:
        return ""
    wanted = {f"socket:[{inode}]" for inode in inodes}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            continue        # Prozess eines anderen Benutzers
        for fd in fds:
            try:
                if os.readlink(f"/proc/{pid}/fd/{fd}") in wanted:
                    return _describe(pid)
            except OSError:
                continue
    return ""


def _describe(pid):
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return ""
    match = re.search(r"/plugins/([^/\s]+)/", cmd)
    if match:
        plugin_id = match.group(1)
        entry = read_registry().get(plugin_id) or {}
        return entry.get("name") or (BLOCKS.get(plugin_id) or (0, 0, ""))[2] or f"Plugin {plugin_id}"
    first = cmd.split(" ", 1)[0]
    return os.path.basename(first) or ""


class PortKeeper:
    def __init__(self, plugin_id, name, data_dir, default, key="phone", span=1, env=None,
                 host_lan=True, log=None, language=None):
        self.plugin_id = plugin_id
        self.name = name
        self.data_dir = Path(data_dir)
        self.default = int(default)
        self.key = key
        self.span = max(1, int(span))
        self.env = env
        self.host_lan = host_lan
        self._log = log or (lambda *_a, **_k: None)
        self._language = language or (lambda: "de")
        self._lock = threading.RLock()
        self.servers = []
        self.port = None
        self.busy = []           # [{"port": n, "by": "..."}] beim letzten Start belegt
        self.manual_busy = False
        self.error = ""

    # ---------------------------------------------------------------- Speicher
    @property
    def _file(self):
        return self.data_dir / "ports.json"

    def _saved(self):
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            entry = data.get(self.key) if isinstance(data, dict) else None
            return entry if isinstance(entry, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, **changes):
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            data = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            data = {}
        entry = dict(data.get(self.key) or {})
        entry.update(changes)
        data[self.key] = entry
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, self._file)
        except OSError as exc:
            self._log(f"Konnte {self._file} nicht schreiben: {exc}", "warning")

    @property
    def manual(self):
        value = self._saved().get("manual")
        return int(value) if isinstance(value, int) and value else None

    def _register(self):
        path = REGISTRY_DIR / f"{self.plugin_id}.json"
        try:
            REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                entry = entry if isinstance(entry, dict) else {}
            except (OSError, ValueError):
                entry = {}
            ports = dict(entry.get("ports") or {})
            ports[self.key] = {"port": self.port, "span": self.span, "proto": "tcp", "default": self.default,
                               "lan": self.host_lan}
            entry.update(plugin=self.plugin_id, name=self.name, ports=ports,
                         updated=time.strftime("%Y-%m-%dT%H:%M:%S"))
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(entry, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            self._log(f"Konnte die Port-Liste {path} nicht schreiben: {exc}", "warning")

    # ---------------------------------------------------------------- Suche
    def _fits(self, port, taken):
        return LOWEST <= port and port + self.span - 1 <= 65535 and \
            not any(p in taken for p in range(port, port + self.span))

    def candidates(self, keep_last=True):
        """Reihenfolge: zuletzt genutzter Port (damit Kurzbefehle passen), Standard, eigener Block, 8180 ff."""
        taken = reserved_for_others(self.plugin_id)
        low, high, _name = BLOCKS.get(self.plugin_id, (self.default, self.default + 4, ""))
        order = ([self._saved().get("last")] if keep_last else []) + [self.default]
        order += list(range(low, high + 1)) + list(range(OVERFLOW[0], OVERFLOW[1] + 1))
        seen, result = set(), []
        for port in order:
            if isinstance(port, int) and port not in seen and self._fits(port, taken):
                seen.add(port)
                result.append(port)
        return result

    def _open(self, make_server, port):
        made = make_server(port)
        servers = [s for s in (made if isinstance(made, (list, tuple)) else [made]) if s is not None]
        for server in servers:
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, name=f"{self.plugin_id}-{self.key}-{server.server_address[1]}",
                             daemon=True).start()
        return servers

    def _close(self, servers):
        for server in servers:
            try:
                server.shutdown()
                server.server_close()
            except Exception:  # noqa: BLE001
                pass

    def _busy_entry(self, port):
        who = owner_of(port, self.plugin_id) or who_listens(port)
        return {"port": port, "by": who}

    # ---------------------------------------------------------------- Ablauf
    def start(self, make_server):
        """Ersten passenden Port öffnen. Gibt die Server-Liste zurück (leer, wenn keiner frei war)."""
        with self._lock:
            self._make = make_server
            self.busy, self.manual_busy, self.error = [], False, ""
            forced = os.environ.get(self.env) if self.env else None
            manual = int(forced) if forced and forced.isdigit() else self.manual
            order = ([manual] if manual else []) + [p for p in self.candidates() if p != manual]
            for port in order:
                try:
                    servers = self._open(make_server, port)
                except OSError as exc:
                    if port == manual:
                        self.manual_busy = True
                    if len(self.busy) < 5:
                        self.busy.append(self._busy_entry(port))
                    self._log(f"Port {port} ist belegt ({exc}).", "warning")
                    continue
                self.servers, self.port = servers, port
                self._save(last=port)
                self._register()
                if port != self.default:
                    self._log(f"{self.name}: Port {port} statt {self.default}.", "warning")
                return servers
            self.error = _text("none", self._language())
            self._log(f"{self.name}: kein freier Port gefunden.", "warning")
            return []

    def change(self, value):
        """Von der Plugin-Seite: Zahl = Port festlegen, leer/0 = automatisch."""
        language = self._language()
        text = str(value if value is not None else "").strip()
        with self._lock:
            if not text or text == "0":
                self._save(manual=None)
                self.manual_busy = False
                if self.port in (None, self.default) or not getattr(self, "_make", None):
                    return {"success": True, "port": self.port}
                for port in self.candidates(keep_last=False):
                    if port == self.port:
                        break           # der jetzige ist schon der beste freie
                    if self._switch(port):
                        break
                return {"success": True, "port": self.port}
            if not text.isdigit() or not LOWEST <= int(text) <= 65535 - self.span + 1:
                return {"success": False, "error": _text("range", language, low=LOWEST)}
            port = int(text)
            owner = owner_of(port, self.plugin_id)
            for extra in range(1, self.span):
                owner = owner or owner_of(port + extra, self.plugin_id)
            if owner:
                return {"success": False, "error": _text("reserved", language, port=port, who=owner)}
            if port == self.port:
                self._save(manual=port)
                self.manual_busy = False
                return {"success": True, "port": port}
            if not getattr(self, "_make", None):
                self._save(manual=port)
                return {"success": True, "port": self.port}
            if not self._switch(port):
                who = who_listens(port)
                by = _text("by", language, who=who) if who else ""
                return {"success": False, "error": _text("busy", language, port=port, by=by)}
            self._save(manual=port)
            self.manual_busy = False
            return {"success": True, "port": port}

    def _switch(self, port):
        try:
            servers = self._open(self._make, port)
        except OSError:
            return False
        old = self.servers
        self.servers, self.port = servers, port
        self.busy, self.error = [], ""
        self._save(last=port)
        self._register()
        self._close(old)
        self._log(f"{self.name}: jetzt auf Port {port}.")
        return True

    def stop(self):
        with self._lock:
            self._close(self.servers)
            self.servers = []

    @property
    def server(self):
        return self.servers[0] if self.servers else None

    def status(self):
        return {"port": self.port, "default": self.default, "manual": self.manual, "span": self.span,
                "busy": list(self.busy), "manualBusy": self.manual_busy, "error": self.error}


def lan_ip():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))     # schickt nichts, sucht nur die Route
        return probe.getsockname()[0]
    except OSError:
        return ""
    finally:
        probe.close()
