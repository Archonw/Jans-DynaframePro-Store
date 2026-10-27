"""Fahrzeit für Dynaframe's Magic Mirror: wie lange die Fahrt gerade dauert.

Fragt Mapbox (Profil driving-traffic, ohne Zahlungsart 10.000 Abfragen im
Monat frei) oder die Google Routes API (TRAFFIC_AWARE, braucht ein Projekt mit
Zahlungsart) mit dem eigenen Schlüssel. Die Szene holt jede Minute, solange sie
zu sehen ist; gefragt wird der Dienst aber nur alle "minutes" Minuten, dazwischen
kommt das gemerkte Ergebnis zurück. Mapbox braucht Koordinaten: Adressen werden
einmal bei OpenStreetMap (Nominatim) nachgeschlagen und gemerkt.
Dazu auf Wunsch Meldungen und Sperrungen der Autobahn GmbH nahe der Route.
"""

import math
import os
import re
import threading
import time

import requests

# Die Umgebungsvariablen sind nur für Tests mit nachgebauten Diensten.
GOOGLE_URL = os.environ.get("TT_GOOGLE_URL", "https://routes.googleapis.com/directions/v2:computeRoutes")
MAPBOX_URL = os.environ.get("TT_MAPBOX_URL", "https://api.mapbox.com/directions/v5/mapbox/driving-traffic")
NOMINATIM_URL = os.environ.get("TT_NOMINATIM_URL", "https://nominatim.openstreetmap.org")
AUTOBAHN_URL = os.environ.get("TT_AUTOBAHN_URL", "https://verkehr.autobahn.de/o/autobahn")
TIMEOUT = (8, 20)
USER_AGENT = "Dynaframe-MagicMirror-TravelTime/1.0 (+https://github.com/Archonw/Jans-DynaframePro-Store)"

ROUTE_FIELDS = ",".join(["routes.duration", "routes.staticDuration", "routes.distanceMeters",
                         "routes.description", "routes.polyline.encodedPolyline"])
ROAD = re.compile(r"\bA\s?(\d{1,3})\b")
LATLON = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")

_lock = threading.Lock()
_geo = {}        # Adresse -> {"lat", "lon"}
_routes = {}     # Schlüssel der Abfrage -> {"at", "value"}
_events = {}     # Straßen -> {"at", "value"}

TEXT = {
    "no-dest": {"de": "Trag ein, wohin die Fahrt geht.", "en": "Enter where the trip goes.",
                "es": "Indica a dónde va el viaje."},
    "not-found": {"de": "Die Adresse „{a}“ wurde nicht gefunden. Versuch es mit Straße, Hausnummer und Ort.",
                  "en": "The address “{a}” was not found. Try street, number and town.",
                  "es": "No se encontró la dirección «{a}». Prueba con calle, número y ciudad."},
    "no-route": {"de": "{p} findet keine Route zwischen den beiden Orten.",
                 "en": "{p} finds no route between the two places.",
                 "es": "{p} no encuentra ninguna ruta entre los dos lugares."},
    "key": {"de": "{p} nimmt den Schlüssel nicht an. Prüfe, ob er vollständig kopiert ist.",
            "en": "{p} does not accept the key. Check that it was copied completely.",
            "es": "{p} no acepta la clave. Comprueba que esté copiada entera."},
    "denied": {"de": "{p} erlaubt diesem Schlüssel die Abfrage nicht. Prüfe die Einschränkungen des Schlüssels.",
               "en": "{p} does not allow this key to ask. Check the key's restrictions.",
               "es": "{p} no permite la consulta con esta clave. Revisa las restricciones de la clave."},
    "disabled": {"de": "Die Routes API ist für diesen Schlüssel nicht aktiviert. Aktiviere sie in der Google Cloud Console.",
                 "en": "The Routes API is not enabled for this key. Enable it in the Google Cloud Console.",
                 "es": "La Routes API no está activada para esta clave. Actívala en Google Cloud Console."},
    "billing": {"de": "Google verlangt für das Projekt eine Zahlungsart. Hinterlege sie in der Google Cloud Console.",
                "en": "Google requires a payment method for the project. Add one in the Google Cloud Console.",
                "es": "Google exige un método de pago para el proyecto. Añádelo en Google Cloud Console."},
    "quota": {"de": "Das Kontingent bei {p} ist erschöpft.", "en": "The {p} quota is used up.",
              "es": "Se ha agotado la cuota de {p}."},
}

_http = requests.Session()
_http.headers["User-Agent"] = USER_AGENT


def say(ctx, code, **values):
    lang = ctx.get("lang") or "de"
    text = TEXT[code].get(lang) or TEXT[code]["en"]
    return ctx["SourceError"](text.format(**values))


# ------------------------------------------------------------ Geometrie

def decode_polyline(encoded):
    """Encoded Polyline (Genauigkeit 5, so liefern es Google und Mapbox) -> [(lat, lon)]."""
    points, index, lat, lon = [], 0, 0, 0
    encoded = encoded or ""
    while index < len(encoded):
        values = []
        for _ in range(2):
            shift = result = 0
            while True:
                if index >= len(encoded):
                    return points
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            values.append(~(result >> 1) if result & 1 else result >> 1)
        lat += values[0]
        lon += values[1]
        points.append((lat / 1e5, lon / 1e5))
    return points


def distance_to_line_km(lat, lon, line):
    """Kleinster Abstand eines Punkts zu einem Linienzug, flach gerechnet."""
    if not line:
        return float("inf")
    kx, ky = 111.32 * math.cos(math.radians(lat)), 110.57
    px, py = lon * kx, lat * ky
    best, prev = float("inf"), None
    for la, lo in line:
        cur = (lo * kx, la * ky)
        if prev is None:
            best = min(best, math.hypot(cur[0] - px, cur[1] - py))
        else:
            (ax, ay), (bx, by) = prev, cur
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
            best = min(best, math.hypot(ax + t * dx - px, ay + t * dy - py))
        prev = cur
    return best


# ------------------------------------------------------------ Orte

def place(text, ctx):
    """(lat, lon) für eine Adresse oder "50.11, 8.68"; leer = der Ort der Seite."""
    text = str(text or "").strip()
    if not text:
        if ctx.get("lat") is None or ctx.get("lon") is None:
            raise ctx["SourceError"]("no-place")
        return float(ctx["lat"]), float(ctx["lon"])
    match = LATLON.match(text)
    if match:
        return float(match.group(1)), float(match.group(2))
    with _lock:
        known = _geo.get(text)
    if known:
        return known
    rows = ctx["get"](f"{NOMINATIM_URL}/search", params={"q": text, "format": "jsonv2", "limit": 1,
                                                         "accept-language": ctx.get("lang") or "de"})
    if not isinstance(rows, list) or not rows:
        raise say(ctx, "not-found", a=text[:60])
    try:
        found = (float(rows[0]["lat"]), float(rows[0]["lon"]))
    except (KeyError, TypeError, ValueError):
        raise ctx["SourceError"]("format")
    with _lock:
        _geo[text] = found
    return found


def waypoint(text, ctx):
    """Google nimmt Adressen direkt, nur der leere Start wird zum Ort der Seite."""
    text = str(text or "").strip()
    if text and not LATLON.match(text):
        return {"address": text}
    lat, lon = place(text, ctx)
    return {"location": {"latLng": {"latitude": lat, "longitude": lon}}}


# ------------------------------------------------------------ Dienste

def answer(response):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def row_of(seconds, normal, meters, via, polyline):
    return {"seconds": seconds, "normalSeconds": normal or seconds, "meters": int(meters or 0), "via": via[:60],
            "roads": sorted({f"A{n}" for n in ROAD.findall(via)}, key=lambda r: int(r[1:])), "polyline": polyline}


def seconds_of(value):
    """Google schreibt Dauern als "1834s"."""
    match = re.match(r"^\s*(\d+(?:\.\d+)?)s\s*$", str(value or ""))
    return round(float(match.group(1))) if match else None


def google(key, config, ctx):
    lang = ctx.get("lang") or "de"
    body = {"origin": waypoint(config.get("origin"), ctx), "destination": waypoint(config.get("destination"), ctx),
            "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE", "computeAlternativeRoutes": True,
            "languageCode": {"de": "de-DE", "en": "en-GB", "es": "es-ES"}.get(lang, "de-DE"), "units": "METRIC"}
    if config.get("avoidTolls"):
        body["routeModifiers"] = {"avoidTolls": True}
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": ROUTE_FIELDS}
    try:
        response = _http.post(GOOGLE_URL, json=body, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ctx["SourceError"]("unreachable", str(exc))
    payload = answer(response)
    if response.status_code >= 400 or "error" in payload:
        error = payload.get("error") or {}
        reasons = " ".join(str(d.get("reason") or "") for d in error.get("details") or [] if isinstance(d, dict))
        message, status = str(error.get("message") or ""), str(error.get("status") or "")
        if "API_KEY" in reasons or "API key not valid" in message:
            raise say(ctx, "key", p="Google")
        if "SERVICE_DISABLED" in reasons or "has not been used" in message or "disabled" in message:
            raise say(ctx, "disabled")
        if "BILLING" in reasons or "billing" in message.lower():
            raise say(ctx, "billing")
        if status == "RESOURCE_EXHAUSTED" or response.status_code == 429:
            raise say(ctx, "quota", p="Google")
        if status == "PERMISSION_DENIED":
            raise say(ctx, "denied", p="Google")
        raise ctx["SourceError"](f"http:{response.status_code}", message)
    routes = []
    for row in payload.get("routes") or []:
        traffic = seconds_of(row.get("duration"))
        if traffic is not None:
            routes.append(row_of(traffic, seconds_of(row.get("staticDuration")), row.get("distanceMeters"),
                                 str(row.get("description") or ""), (row.get("polyline") or {}).get("encodedPolyline") or ""))
    return routes


def mapbox(token, config, ctx):
    start, end = place(config.get("origin"), ctx), place(config.get("destination"), ctx)
    coords = f"{start[1]:.6f},{start[0]:.6f};{end[1]:.6f},{end[0]:.6f}"
    lang = ctx.get("lang") or "de"
    params = {"access_token": token, "alternatives": "true", "geometries": "polyline", "overview": "full",
              "steps": "false", "language": lang if lang in ("de", "en", "es") else "en"}
    if config.get("avoidTolls"):
        params["exclude"] = "toll"
    try:
        response = _http.get(f"{MAPBOX_URL}/{coords}", params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ctx["SourceError"]("unreachable", str(exc))
    payload = answer(response)
    code = str(payload.get("code") or "")
    if response.status_code == 401:
        raise say(ctx, "key", p="Mapbox")
    if response.status_code == 403:
        raise say(ctx, "denied", p="Mapbox")
    if response.status_code == 429:
        raise say(ctx, "quota", p="Mapbox")
    if code in ("NoRoute", "NoSegment") or response.status_code == 422:
        raise say(ctx, "no-route", p="Mapbox")
    if response.status_code >= 400 or (code and code != "Ok"):
        raise ctx["SourceError"](f"http:{response.status_code}", str(payload.get("message") or code))
    routes = []
    for row in payload.get("routes") or []:
        if not isinstance(row, dict) or row.get("duration") is None:
            continue
        typical = row.get("duration_typical")
        via = ", ".join(str(leg.get("summary") or "") for leg in row.get("legs") or []
                        if isinstance(leg, dict) and leg.get("summary"))
        routes.append(row_of(int(round(float(row["duration"]))),
                             int(round(float(typical))) if typical is not None else None,
                             row.get("distance"), via, row.get("geometry") if isinstance(row.get("geometry"), str) else ""))
    return routes


# ------------------------------------------------------------ Autobahn

def autobahn(roads, polyline, ctx):
    """Meldungen und Sperrungen höchstens 1,5 km neben der Route (nur deutsche Autobahnen)."""
    line = decode_polyline(polyline)
    if not roads or not line:
        return []
    key = (tuple(roads[:4]), polyline)
    with _lock:
        known = _events.get(key)
    if known and time.time() - known["at"] < 600:
        return known["value"]
    events = []
    for road in roads[:4]:
        for kind in ("warning", "closure"):
            try:
                payload = ctx["get"](f"{AUTOBAHN_URL}/{road}/services/{kind}")
            except Exception:   # Meldungen sind nur Beiwerk
                continue
            for row in (payload or {}).get(kind) or []:
                if not isinstance(row, dict) or row.get("future") is True:
                    continue
                spot = row.get("coordinate") or {}
                try:
                    lat, lon = float(spot.get("lat")), float(spot.get("long"))
                except (TypeError, ValueError):
                    continue
                if distance_to_line_km(lat, lon, line) > 1.5:
                    continue
                # Die erste Zeile ist meist "Beginn: …", eine weitere wiederholt Straße und Richtung.
                text = [str(d).strip() for d in row.get("description") or [] if str(d).strip()
                        and not re.match(r"^(Beginn|Ende|Start|Dauer)\b", str(d).strip()) and "->" not in str(d)]
                event = {"kind": kind, "title": str(row.get("title") or road).strip()[:90],
                         "text": (" ".join(text[:2]) or str(row.get("subtitle") or "").strip())[:160]}
                if not any((e["title"], e["text"]) == (event["title"], event["text"]) for e in events):
                    events.append(event)
    with _lock:
        prune(_events)
        _events[key] = {"at": time.time(), "value": events}
    return events


# ------------------------------------------------------------ Abfrage

def prune(store):
    """Alte Einträge vergessen (geänderte Einstellungen); nur unter _lock aufrufen."""
    for old in [k for k, v in store.items() if time.time() - v["at"] > 7200]:
        del store[old]


def fetch(config, ctx):
    service = "google" if config.get("service") == "google" else "mapbox"
    key = str(config.get("key") or "").strip()
    if not key:
        raise ctx["SourceError"]("no-key")
    if not str(config.get("destination") or "").strip():
        raise say(ctx, "no-dest")
    minutes = max(2, min(60, int(config.get("minutes") or 5)))
    ask = repr((service, key, config.get("origin"), config.get("destination"), bool(config.get("avoidTolls")),
                ctx.get("lat"), ctx.get("lon"), ctx.get("lang")))
    with _lock:
        known = _routes.get(ask)
    if known and time.time() - known["at"] < minutes * 60 - 5:
        value = known["value"]
    else:
        routes = google(key, config, ctx) if service == "google" else mapbox(key, config, ctx)
        if not routes:
            raise say(ctx, "no-route", p="Google" if service == "google" else "Mapbox")
        routes.sort(key=lambda r: r["seconds"])
        best = routes[0]
        value = {"at": time.time(), "provider": service, "seconds": best["seconds"],
                 "normalSeconds": best["normalSeconds"], "km": round(best["meters"] / 1000, 1), "via": best["via"],
                 "alternatives": [{"seconds": r["seconds"], "via": r["via"]} for r in routes[1:3]],
                 "roads": best["roads"], "polyline": best["polyline"]}
        with _lock:
            prune(_routes)   # mehrere Module (Ziele) teilen sich diese Datei
            _routes[ask] = {"at": value["at"], "value": value}
    out = {k: v for k, v in value.items() if k not in ("roads", "polyline")}
    out["events"] = autobahn(value["roads"], value["polyline"], ctx)[:3] if config.get("showEvents", True) else []
    return out
