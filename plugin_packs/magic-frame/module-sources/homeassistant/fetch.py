"""Home Assistant für Dynaframe's Magic Mirror.

Ein Modul, mehrere Ansichten (config "view"):
  values   - Werte beliebiger Entitäten (wie früher das eingebaute Modul)
  status   - nur Auffälliges: offene Fenster/Türen, Schlösser, Melder, leere Akkus
  climate  - Temperatur, Luftfeuchte, CO2 je Raum (Räume aus den Bereichen in HA)
  presence - wer zu Hause ist (person.*)
  waste    - Müllabfuhr aus HA (Kalender, Waste Collection Schedule) oder ICS-Link

Adresse und Token braucht nur ein Modul: Module ohne eigene nehmen die eines
anderen Home-Assistant-Moduls (ctx["shared"], sonst die zuletzt benutzten).
Alle Ansichten teilen sich eine Abfrage von /api/states (20 s).
"""

import json
import re
import threading
import time
from datetime import datetime, timedelta

import requests

_lock = threading.Lock()
_last = {"url": "", "token": ""}          # zuletzt funktionierende Verbindung
_cache = {"key": None, "at": 0.0, "value": None}


# ------------------------------------------------------------ Verbindung

def base_url(url):
    url = str(url or "").strip().rstrip("/")
    if url and not re.match(r"^https?://", url):
        url = "http://" + url
    if re.match(r"^http://[^/:]+$", url):
        url += ":8123"
    return url


def connection(config, ctx):
    url, token = base_url(config.get("url")), str(config.get("token") or "").strip()
    if not token:
        for other in ctx.get("shared") or []:
            if str(other.get("token") or "").strip():
                url, token = url or base_url(other.get("url")), str(other["token"]).strip()
                break
    if not token:
        url, token = url or _last["url"], _last["token"]
    if not url or not token:
        raise ctx["SourceError"]("no-key")
    return url, token


def headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def remember(url, token):
    with _lock:
        _last.update(url=url, token=token)


# Eigene Fehlertexte (der Magic Mirror zeigt unbekannte Codes so, wie sie sind)
ERRORS = {
    "no-rooms": ("Keine Räume gefunden. Trag sie unter „Räume“ ein.", "No rooms found. Enter them under “Rooms”.",
                 "No se encontraron habitaciones. Escríbelas en «Habitaciones»."),
    "no-people": ("Keine Personen in Home Assistant gefunden.", "No people found in Home Assistant.",
                  "No se encontraron personas en Home Assistant."),
    "waste-none": ("Keine Müll-Entität gefunden. Trag sie unter „Entitäten“ ein.",
                   "No waste entity found. Enter it under “Entities”.",
                   "No se encontró ninguna entidad de basura. Escríbela en «Entidades»."),
}


def fail(ctx, code):
    texts = ERRORS[code]
    return ctx["SourceError"](texts[("de", "en", "es").index(ctx.get("lang"))] if ctx.get("lang") in ("de", "en", "es")
                              else texts[1])


# ------------------------------------------------------------ Entitäten

DATE_KEY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$|^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() if value else None
    except ValueError:
        return None


def entity(entity_id, row, url):
    attributes = row.get("attributes") or {}
    out = {
        "id": entity_id,
        "state": str(row.get("state") or "")[:40],
        "name": str(attributes.get("friendly_name") or entity_id)[:60],
        "unit": str(attributes.get("unit_of_measurement") or "")[:12],
        "deviceClass": str(attributes.get("device_class") or "")[:30],
        "domain": entity_id.split(".", 1)[0],
        "icon": str(attributes.get("icon") or "")[:40],
        "changed": parse_time(row.get("last_changed")),
    }
    for key, name in (("current_temperature", "temp"), ("current_humidity", "humidity")):
        if isinstance(attributes.get(key), (int, float)):
            out[name] = attributes[key]
    picture = str(attributes.get("entity_picture") or "")
    if picture:
        out["picture"] = (url + picture if picture.startswith("/") else picture)[:300]
    # Abholtermine wie bei Waste Collection Schedule: {"2026-10-28": "Gelber Sack", ...}
    dates = {}
    for key, value in attributes.items():
        match = DATE_KEY.match(str(key).strip())
        if match:
            y, m, d = match.group(1, 2, 3) if match.group(1) else match.group(6, 5, 4)
            types = value if isinstance(value, list) else [value]
            dates[f"{int(y):04d}-{int(m):02d}-{int(d):02d}"] = [str(t)[:40] for t in types if str(t or "").strip()][:4]
    if dates:
        out["dates"] = dict(sorted(dates.items())[:20])
    return out


def snapshot(config, ctx):
    """Alle Zustände auf einmal, 20 s lang für alle Home-Assistant-Module geteilt."""
    url, token = connection(config, ctx)
    with _lock:
        if _cache["key"] == (url, token) and time.time() - _cache["at"] < 20:
            return _cache["value"]
    rows = ctx["get"](f"{url}/api/states", headers=headers(token))
    if not isinstance(rows, list):
        raise ctx["SourceError"]("format", "keine Liste")
    value = {}
    for row in rows:
        entity_id = str(row.get("entity_id") or "")[:120] if isinstance(row, dict) else ""
        if "." in entity_id:
            value[entity_id] = entity(entity_id, row, url)
    remember(url, token)
    with _lock:
        _cache.update(key=(url, token), at=time.time(), value=value)
    return value


def lines_of(text, limit):
    return [line.strip() for line in str(text or "").splitlines() if line.strip()][:limit]


def named_ids(text, limit=20):
    """ "sensor.x" oder "Name = sensor.x" je Zeile."""
    out = []
    for line in lines_of(text, limit):
        name, _, entity_id = line.rpartition("=")
        if "." in entity_id.strip():
            out.append({"id": entity_id.strip(), "label": name.strip()})
    return out


def number(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------ Werte

def view_values(config, ctx):
    rows = named_ids(config.get("entities"))
    if not rows:
        raise ctx["SourceError"]("no-entities")
    states = snapshot(config, ctx)
    out = []
    for row in rows:
        e = states.get(row["id"])
        out.append(dict(e, name=row["label"] or e["name"]) if e else {"id": row["id"], "missing": True})
    if all(e.get("missing") for e in out):
        raise ctx["SourceError"]("ha-none")
    return {"entities": out}


# ------------------------------------------------------------ Haus-Status

OPENING = ("window", "door", "garage_door", "opening")
SAFETY = ("smoke", "gas", "moisture", "carbon_monoxide", "problem", "safety", "tamper", "heat", "cold", "battery")
COVERS = ("garage", "door", "gate", "window")
RULE = re.compile(r"^(?:(?P<name>.*?)\s*=\s*)?(?P<id>[a-z_]+\.[a-z0-9_]+)\s*(?:(?P<op><=|>=|!=|==|<|>|=)\s*(?P<value>.+))?$")


def problem(e, battery):
    """Was ist an dieser Entität auffällig? "" = nichts, sonst die Art."""
    state, cls, domain = e["state"], e["deviceClass"], e["domain"]
    if domain == "binary_sensor":
        if cls in OPENING and state == "on":
            return "open"
        if cls in SAFETY and state == "on":
            return "battery" if cls == "battery" else "safety"
        return ""
    if domain == "lock":
        return "lock" if state in ("unlocked", "open", "opening", "unlocking", "jammed") else ""
    if domain == "cover" and cls in COVERS:
        return "open" if state in ("open", "opening") else ""
    if domain == "sensor" and cls == "battery":
        level = number(state)
        return "battery" if level is not None and level < battery else ""
    return ""


def watchable(e):
    cls, domain = e["deviceClass"], e["domain"]
    return (domain == "binary_sensor" and cls in OPENING + SAFETY) or domain == "lock" \
        or (domain == "cover" and cls in COVERS) or (domain == "sensor" and cls == "battery")


def matches(state, op, wanted):
    a, b = number(state), number(wanted)
    if op in ("<", ">", "<=", ">="):
        if a is None or b is None:
            return False
        return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
    same = str(state).strip().lower() == wanted.strip().lower() or (a is not None and a == b)
    return not same if op == "!=" else same


def view_status(config, ctx):
    states = snapshot(config, ctx)
    battery = int(config.get("battery") or 20)
    ignore = [w.strip().lower() for w in re.split(r"[,\n]", str(config.get("ignore") or "")) if w.strip()]
    rules = [m.groupdict() for m in (RULE.match(line) for line in lines_of(config.get("entities"), 80)) if m]
    auto = not rules
    if auto:
        rules = [{"id": i, "name": "", "op": None, "value": None} for i, e in states.items() if watchable(e)]
    alerts, checked = [], 0
    for rule in rules:
        e = states.get(rule["id"])
        if e is None or e["state"] in ("unavailable", "unknown", ""):
            continue
        if any(w in rule["id"].lower() or w in e["name"].lower() for w in ignore):
            continue
        checked += 1
        if rule["op"]:
            kind = "custom" if matches(e["state"], rule["op"], rule["value"].strip()) else ""
        else:
            kind = problem(e, battery) or ("open" if not auto and e["state"] in ("on", "open", "unlocked") else "")
        if kind:
            alerts.append(dict(e, name=(rule["name"] or "").strip() or e["name"], kind=kind))
    order = {"safety": 0, "open": 1, "lock": 2, "custom": 3, "battery": 4}
    alerts.sort(key=lambda a: (order.get(a["kind"], 5), -(a.get("changed") or 0)))
    return {"alerts": alerts[:20], "checked": checked}


# ------------------------------------------------------------ Raumklima

ROOMS_TEMPLATE = """{%- set ns = namespace(rows=[]) -%}
{%- for a in areas() -%}
{%- set s = area_entities(a) | select('match', 'sensor\\.') | list -%}
{%- set t = s | select('is_state_attr', 'device_class', 'temperature') | list -%}
{%- set h = s | select('is_state_attr', 'device_class', 'humidity') | list -%}
{%- set c = s | select('is_state_attr', 'device_class', 'carbon_dioxide') | list -%}
{%- set k = area_entities(a) | select('match', 'climate\\.') | list -%}
{%- if t or k -%}{%- set ns.rows = ns.rows + [{'name': area_name(a), 'ids': t[:1] + h[:1] + c[:1] + k[:1]}] -%}{%- endif -%}
{%- endfor -%}{{ ns.rows | tojson }}"""

_areas = {"key": None, "at": 0.0, "value": None}


def area_rooms(config, ctx):
    """Räume aus den Bereichen in Home Assistant (über /api/template, 10 min gemerkt)."""
    url, token = connection(config, ctx)
    if _areas["key"] == (url, token) and time.time() - _areas["at"] < 600:
        return _areas["value"]
    response = requests.post(f"{url}/api/template", json={"template": ROOMS_TEMPLATE},
                             headers=headers(token), timeout=(8, 20))
    response.raise_for_status()
    rooms = [r for r in json.loads(response.text) if isinstance(r, dict) and r.get("ids")][:16]
    _areas.update(key=(url, token), at=time.time(), value=rooms)
    return rooms


def room_lines(text):
    """ "Wohnzimmer = sensor.a, sensor.b" oder nur "sensor.a" je Zeile."""
    out = []
    for line in lines_of(text, 16):
        name, _, ids = line.rpartition("=") if re.search(r"=\s*[a-z_]+\.", line) else ("", "", line)
        ids = [i.strip() for i in ids.split(",") if re.match(r"^[a-z_]+\.[a-z0-9_]+$", i.strip())]
        if ids:
            out.append({"name": name.strip(), "ids": ids[:4]})
    return out


def view_climate(config, ctx):
    states = snapshot(config, ctx)
    rooms = room_lines(config.get("rooms"))
    if not rooms:
        try:
            rooms = area_rooms(config, ctx)
        except (requests.RequestException, ValueError) as exc:
            ctx["log"](f"Home Assistant: Bereiche nicht lesbar ({exc}), nehme die Thermostate")
        if not rooms:
            rooms = [{"name": "", "ids": [i]} for i, e in states.items() if e["domain"] == "climate"][:16]
        if not rooms:
            raise fail(ctx, "no-rooms")
    out = []
    for room in rooms:
        tile = {"name": room.get("name") or ""}
        for entity_id in room["ids"]:
            e = states.get(entity_id)
            if not e:
                continue
            tile["name"] = tile["name"] or e["name"]
            value = number(e["state"])
            if e["domain"] == "climate":
                for key in ("temp", "humidity"):
                    if tile.get(key) is None and e.get(key) is not None:
                        tile[key] = e[key]
                tile["hvac"] = e["state"]
            elif value is None:
                continue
            elif e["deviceClass"] == "temperature" or e["unit"] in ("°C", "°F"):
                tile.setdefault("temp", value)
                tile.setdefault("unit", e["unit"])
            elif e["deviceClass"] == "humidity":
                tile.setdefault("humidity", value)
            elif e["deviceClass"] == "carbon_dioxide" or e["unit"] == "ppm":
                tile.setdefault("co2", value)
        if any(tile.get(k) is not None for k in ("temp", "humidity", "co2")):
            out.append(tile)
    if not out:
        raise ctx["SourceError"]("ha-none")
    return {"rooms": out}


# ------------------------------------------------------------ Anwesenheit

def view_presence(config, ctx):
    states = snapshot(config, ctx)
    rows = named_ids(config.get("entities"), 12)
    if not rows:
        rows = [{"id": i, "label": ""} for i, e in sorted(states.items(), key=lambda x: x[1]["name"].lower())
                if e["domain"] == "person"]
    people = []
    for row in rows[:12]:
        e = states.get(row["id"])
        if e:
            people.append({"name": row["label"] or e["name"], "state": e["state"],
                           "picture": e.get("picture", ""), "changed": e.get("changed")})
    if not people:
        raise fail(ctx, "no-people")
    return {"people": people}


# ------------------------------------------------------------ Müllabfuhr

WASTE_WORDS = re.compile(r"abfall|m(ü|ue)ll|waste|trash|garbage|bin_|tonne|recycl|basura|residuos", re.I)


def ics_pickups(urls, days, ctx):
    """Ganztägige (und andere) Termine aus ICS-Links: [(JJJJ-MM-TT, Titel)]."""
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days + 1)
    out = []
    for url in urls:
        url = re.sub(r"^webcals?://", "https://", url.strip())
        body = ctx["get"](url, expect="text")
        try:
            import icalendar
            import recurring_ical_events
            calendar = icalendar.Calendar.from_ical(body)
            for item in recurring_ical_events.of(calendar).between(start, end):
                begin = item.get("DTSTART")
                if begin is not None:
                    begin = begin.dt
                    day = begin.astimezone().date() if isinstance(begin, datetime) and begin.tzinfo else \
                        (begin.date() if isinstance(begin, datetime) else begin)
                    out.append((day.isoformat(), str(item.get("SUMMARY") or "").strip()[:60]))
        except ImportError:
            # ohne Bibliothek: einfache Termine ohne Wiederholung
            text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
            for block in text.split("BEGIN:VEVENT")[1:]:
                when = re.search(r"\nDTSTART[^:]*:(\d{8})", block)
                title = re.search(r"\nSUMMARY[^:]*:(.*)", block)
                if when and title:
                    raw = when.group(1)
                    out.append((f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}", title.group(1).strip()[:60]))
    return out


def ha_calendar(url, token, entity_id, days, ctx):
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days + 1)
    rows = ctx["get"](f"{url}/api/calendars/{entity_id}", headers=headers(token),
                      params={"start": start.isoformat(), "end": end.isoformat()})
    out = []
    for row in rows if isinstance(rows, list) else []:
        begin = row.get("start") if isinstance(row, dict) else None
        if not isinstance(begin, dict):
            continue
        day = begin.get("date")
        if not day and begin.get("dateTime"):
            stamp = parse_time(begin["dateTime"])
            day = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d") if stamp else None
        if day:
            out.append((str(day)[:10], str(row.get("summary") or "").strip()[:60]))
    return out


_waste = {}


def view_waste(config, ctx):
    """Abholtermine ändern sich selten: 30 Minuten merken, egal wie oft die Szene fragt."""
    key = json.dumps([config.get(k) for k in ("source", "urls", "entities", "days", "count", "url")], default=str)
    hit = _waste.get(key)
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    value = waste_now(config, ctx)
    if len(_waste) > 8:
        _waste.clear()
    _waste[key] = (time.time(), value)
    return value


def waste_now(config, ctx):
    days = int(config.get("days") or 14)
    today = time.strftime("%Y-%m-%d")
    last = time.strftime("%Y-%m-%d", time.localtime(time.time() + days * 86400))
    found, texts = [], []
    if config.get("source") == "ics":
        urls = lines_of(config.get("urls"), 5)
        if not urls:
            raise ctx["SourceError"]("no-url")
        found = ics_pickups(urls, days, ctx)
    else:
        url, token = connection(config, ctx)
        states = snapshot(config, ctx)
        ids = [r["id"] for r in named_ids(config.get("entities"), 6)]
        if not ids:
            # Waste Collection Schedule legt Kalender und Sensoren an: lieber die Kalender,
            # sonst Sensoren mit Terminen, sonst irgendwelche passenden Sensoren
            found_ids = [i for i, e in states.items() if e["domain"] in ("calendar", "sensor")
                         and WASTE_WORDS.search(i + " " + e["name"])]
            ids = [i for i in found_ids if i.startswith("calendar.")] \
                or [i for i in found_ids if states[i].get("dates")] or found_ids
            ids = ids[:6]
        if not ids:
            raise fail(ctx, "waste-none")
        for entity_id in ids:
            e = states.get(entity_id) or {}
            if entity_id.startswith("calendar."):
                found += ha_calendar(url, token, entity_id, days, ctx)
            elif e.get("dates"):
                found += [(day, title) for day, types in e["dates"].items() for title in types]
            elif e.get("state") not in (None, "", "unknown", "unavailable"):
                texts.append({"name": e["name"], "state": e["state"]})
    pickups = {}
    for day, title in found:
        if today <= day <= last and title and title not in pickups.setdefault(day, []):
            pickups[day].append(title)
    rows = [{"date": day, "types": pickups[day]} for day in sorted(pickups) if pickups[day]]
    return {"days": rows[:int(config.get("count") or 3)], "texts": texts[:4]}


VIEWS = {"values": view_values, "status": view_status, "climate": view_climate,
         "presence": view_presence, "waste": view_waste}


def fetch(config, ctx):
    view = VIEWS.get(config.get("view") or "values", view_values)
    try:
        return dict(view(config, ctx), view=config.get("view") or "values")
    except requests.HTTPError as exc:
        raise ctx["SourceError"](f"http:{exc.response.status_code}") from exc
