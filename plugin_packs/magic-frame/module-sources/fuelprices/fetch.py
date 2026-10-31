"""Spritpreise für Dynaframe's Magic Mirror: die Tankstellen in der Nähe.

Fragt Tankerkönig (Daten der Markttransparenzstelle für Kraftstoffe, MTS-K,
Lizenz CC BY 4.0, freier Schlüssel) nach allen Tankstellen im Umkreis. Nur
Deutschland. Tankerkönig bittet, höchstens alle 5 Minuten zu fragen: mehrere
Module mit derselben Abfrage teilen sich darum ein gemerktes Ergebnis.

Daneben merkt sich das Modul je Sorte den billigsten Preis jeder Stunde
(35 Tage) und rechnet daraus selbst: Durchschnitt, Spanne, die Stunde, zu der
es meist am billigsten ist, und den Verlauf der letzten 24 Stunden.
"""

import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

# Die Umgebungsvariablen sind nur für Tests mit nachgebauten Diensten.
TANKER_URL = os.environ.get("FP_TANKER_URL", "https://creativecommons.tankerkoenig.de/json")
NOMINATIM_URL = os.environ.get("FP_NOMINATIM_URL", "https://nominatim.openstreetmap.org")
HISTORY_FILE = Path(os.environ.get("FP_HISTORY") or Path.home() / ".cache" / "magicframe-fuelprices.json")
FUELS = ("e5", "e10", "diesel")
KEEP_DAYS = 35
ASK_SECONDS = 300          # nie öfter als alle 5 Minuten zu Tankerkönig
LATLON = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
PRICE = re.compile(r"^\s*(\d)[.,](\d{2,3})\s*(?:€|eur)?\s*$", re.I)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

_lock = threading.Lock()
_geo = {}        # Adresse -> (lat, lon)
_asked = {}      # Schlüssel der Abfrage -> {"at", "value"}

TEXT = {
    "not-found": {"de": "Die Adresse „{a}“ wurde nicht gefunden. Versuch es mit Straße, Hausnummer und Ort.",
                  "en": "The address “{a}” was not found. Try street, number and town.",
                  "es": "No se encontró la dirección «{a}». Prueba con calle, número y ciudad."},
    "key": {"de": "Tankerkönig nimmt den Schlüssel nicht an. Prüfe, ob er vollständig kopiert ist.",
            "en": "Tankerkönig does not accept the key. Check that it was copied completely.",
            "es": "Tankerkönig no acepta la clave. Comprueba que esté copiada entera."},
    "refused": {"de": "Tankerkönig antwortet: {m}", "en": "Tankerkönig says: {m}", "es": "Tankerkönig responde: {m}"},
    "no-fuel": {"de": "Wähle mindestens eine Sorte.", "en": "Choose at least one fuel type.",
                "es": "Elige al menos un tipo de combustible."},
}


def say(ctx, code, **values):
    lang = ctx.get("lang") or "de"
    text = TEXT[code].get(lang) or TEXT[code]["en"]
    return ctx["SourceError"](text.format(**values))


# ------------------------------------------------------------ Ort

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


# ------------------------------------------------------------ Tankerkönig

def stations_near(key, lat, lon, radius, ctx):
    """Alle Tankstellen im Umkreis mit allen drei Preisen (gemerkt für 5 Minuten)."""
    ask = (key, round(lat, 4), round(lon, 4), radius)
    with _lock:
        known = _asked.get(ask)
        for old in [k for k, v in _asked.items() if time.time() - v["at"] > 3600]:
            del _asked[old]
    if known and time.time() - known["at"] < ASK_SECONDS:
        return known["value"], known["at"]
    payload = ctx["get"](f"{TANKER_URL}/list.php", params={"lat": f"{lat:.5f}", "lng": f"{lon:.5f}",
                                                             "rad": radius, "type": "all", "apikey": key})
    if not isinstance(payload, dict):
        raise ctx["SourceError"]("format")
    if not payload.get("ok"):
        message = str(payload.get("message") or "").strip()
        if "key" in message.lower():
            raise say(ctx, "key")
        raise say(ctx, "refused", m=message[:120] or "?")
    stations = []
    for row in payload.get("stations") or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        prices = {}
        for fuel in FUELS:
            value = row.get(fuel)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0.5:
                prices[fuel] = round(float(value), 3)
        brand = str(row.get("brand") or "").strip()
        name = str(row.get("name") or "").strip()
        stations.append({
            "id": str(row["id"]),
            "brand": (brand or name)[:30],
            "name": name[:60],
            "street": " ".join(str(row.get(k) or "").strip() for k in ("street", "houseNumber")).strip().title()[:60],
            "place": str(row.get("place") or "").strip().title()[:40],
            "km": round(float(row.get("dist") or 0), 1),
            "open": bool(row.get("isOpen")),
            "prices": prices,
        })
    at = time.time()
    with _lock:
        _asked[ask] = {"at": at, "value": stations}
    return stations, at


def wanted(config):
    """Die Zeilen von "stations": Tankstellen-IDs oder Wörter aus Marke, Name, Straße, Ort."""
    return [line.strip() for line in re.split(r"[\n;]", str(config.get("stations") or "")) if line.strip()][:20]


def matches(station, line):
    if UUID.match(line):
        return station["id"].lower() == line.lower()
    hay = " ".join((station["brand"], station["name"], station["street"], station["place"])).lower()
    return all(word in hay for word in line.lower().split())


def limit_of(config, fuel):
    match = PRICE.match(str(config.get(f"limit_{fuel}") or ""))
    return float(f"{match.group(1)}.{match.group(2)}") if match else None


# ------------------------------------------------------------ Verlauf

def read_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_history(history):
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=HISTORY_FILE.parent, delete=False,
                                         suffix=".tmp") as handle:
            json.dump(history, handle, separators=(",", ":"))
        os.replace(handle.name, HISTORY_FILE)
    except OSError:
        pass   # ohne Verlauf geht es auch, nur ohne Durchschnitt


def record(scope, best):
    """Je Sorte der billigste Preis jeder Stunde; gibt die Reihen dieses Orts zurück."""
    hour = str(int(time.time() // 3600 * 3600))
    cutoff = time.time() - KEEP_DAYS * 86400
    with _lock:
        history = read_history()
        rows = history.setdefault(scope, {})
        for fuel, price in best.items():
            row = rows.setdefault(fuel, {})
            if hour not in row or price < row[hour]:
                row[hour] = price
        rows["seen"] = int(time.time())
        for name in list(history):
            if not isinstance(history[name], dict) or history[name].get("seen", 0) < time.time() - 14 * 86400:
                del history[name]
                continue
            for fuel in FUELS:
                for key in [k for k in history[name].get(fuel, {}) if int(k) < cutoff]:
                    del history[name][fuel][key]
        write_history(history)   # immer: auch "seen" soll stimmen
        return {fuel: dict(rows.get(fuel) or {}) for fuel in FUELS}


def day_start(epoch):
    return datetime.fromtimestamp(epoch).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def stats(row, days):
    """Durchschnitt, Spanne, günstigste Stunde und Verlauf aus den Stundenwerten einer Sorte."""
    points = sorted((int(k), p) for k, p in row.items())
    today = day_start(time.time())
    start = today - days * 86400
    past = [(k, p) for k, p in points if start <= k < today]
    seen = {datetime.fromtimestamp(k).date() for k, _ in past}
    out = {"daysKnown": len({datetime.fromtimestamp(k).date() for k, _ in points}), "avg": None,
           "low": None, "high": None, "cheapHour": None}
    if past and len(seen) >= 2:
        out["avg"] = round(sum(p for _, p in past) / len(past), 3)
        out["low"] = min(p for _, p in past)
        out["high"] = max(p for _, p in past)
    # Günstigste Stunde: je Tag (mit mindestens 12 Stunden) die Abweichung jeder
    # Stunde vom Tagesmittel, über die letzten 14 Tage gemittelt.
    by_day = {}
    for k, p in points:
        if k >= today - 14 * 86400:
            by_day.setdefault(datetime.fromtimestamp(k).date(), {})[datetime.fromtimestamp(k).hour] = p
    spread = {}
    full_days = [hours for hours in by_day.values() if len(hours) >= 12]
    for hours in full_days:
        mean = sum(hours.values()) / len(hours)
        for hour, price in hours.items():
            spread.setdefault(hour, []).append(price - mean)
    ranked = sorted((sum(v) / len(v), h) for h, v in spread.items() if len(v) >= max(2, len(full_days) // 2))
    if len(full_days) >= 3 and ranked and ranked[0][0] < -0.004:
        out["cheapHour"] = {"hour": ranked[0][1], "cents": round(-ranked[0][0] * 100),
                            "dearHour": ranked[-1][1], "dearCents": round(ranked[-1][0] * 100)}
    # Verlauf der letzten 24 Stunden für die kleine Kurve
    since = int(time.time() // 3600 * 3600) - 23 * 3600
    out["curve"] = [[k, p] for k, p in points if k >= since]
    return out


# ------------------------------------------------------------ Abfrage

def fetch(config, ctx):
    key = str(config.get("key") or "").strip() or \
        next((str(c.get("key")).strip() for c in ctx.get("shared") or [] if str(c.get("key") or "").strip()), "")
    if not key:
        raise ctx["SourceError"]("no-key")
    fuels = [f for f in FUELS if config.get(f, f != "e5")]
    if not fuels:
        raise say(ctx, "no-fuel")
    lat, lon = place(config.get("origin"), ctx)
    radius = max(1, min(25, int(config.get("radius") or 5)))
    stations, at = stations_near(key, lat, lon, radius, ctx)
    lines = wanted(config)
    if lines:
        stations = [s for s in stations if any(matches(s, line) for line in lines)]
    if config.get("onlyOpen", True):
        stations = [s for s in stations if s["open"]]
    days = max(2, min(30, int(config.get("avgDays") or 7)))
    open_ones = [s for s in stations if s["open"]]
    best = {}
    for fuel in fuels:
        prices = [s["prices"][fuel] for s in open_ones if fuel in s["prices"]]
        if prices:
            best[fuel] = min(prices)
    scope = json.dumps([round(lat, 3), round(lon, 3), radius, sorted(lines)])
    rows = record(scope, best)
    below = max(0, min(50, int(config.get("avgCents") or 0)))
    out_fuels = []
    for fuel in fuels:
        info = {"fuel": fuel, "price": best.get(fuel), "station": None}
        info.update(stats(rows.get(fuel) or {}, days))
        info["avgDays"] = days
        if info["price"] is not None:
            first = min((s for s in open_ones if s["prices"].get(fuel) == info["price"]), key=lambda s: s["km"])
            info["station"] = {k: first[k] for k in ("brand", "street", "place", "km")}
            info["same"] = sum(1 for s in open_ones if s["prices"].get(fuel) == info["price"]) - 1
            limit = limit_of(config, fuel)
            info["limit"] = limit
            info["cheap"] = bool((limit and info["price"] <= limit) or
                                 (below and info["avg"] is not None and info["price"] <= info["avg"] - below / 100))
        out_fuels.append(info)
    order = config.get("sort") or "price"
    first_fuel = fuels[0]
    if order == "distance":
        stations.sort(key=lambda s: s["km"])
    else:
        stations.sort(key=lambda s: (not s["open"], s["prices"].get(first_fuel, 99), s["km"]))
    count = max(1, min(15, int(config.get("count") or 5)))
    return {"at": int(at), "fuels": out_fuels, "order": order, "radius": radius,
            "stations": [{k: s[k] for k in ("brand", "street", "place", "km", "open", "prices")} for s in stations[:count]]}
