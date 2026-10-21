"""Pegelstand für Dynaframe's Magic Mirror: holt den aktuellen Wasserstand von PEGELONLINE.

Dynaframe's Magic Mirror ruft fetch(config, ctx) im eigenen Prozess auf. ctx["get"] holt
JSON mit User-Agent und Zeitlimit und wirft ctx["SourceError"] mit einem
kurzen Code ("unreachable", "http:404", ...), den die Plugin-Seite anzeigt.
"""

import os
from urllib.parse import quote

BASE = os.environ.get("PEGEL_URL", "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations")


def fetch(config, ctx):
    station = str(config.get("station") or "").strip().upper()
    if not station:
        raise ctx["SourceError"]("no-url")
    row = ctx["get"](f"{BASE}/{quote(station)}.json",
                     params={"includeTimeseries": "true", "includeCurrentMeasurement": "true"})
    series = next((s for s in row.get("timeseries") or [] if s.get("shortname") == "W"), None)
    current = (series or {}).get("currentMeasurement") or {}
    if current.get("value") is None:
        raise ctx["SourceError"]("format", "kein Wasserstand")
    return {
        "station": str(row.get("longname") or station).title(),
        "water": str((row.get("water") or {}).get("longname") or "").title(),
        "cm": current["value"],
        "trend": current.get("trend"),               # -1, 0, 1
        "state": current.get("stateMnwMhw") or "",   # low | normal | high | unknown
        "at": current.get("timestamp"),
    }
