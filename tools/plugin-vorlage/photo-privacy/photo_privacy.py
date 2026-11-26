"""Schalter „Fotopositionen bleiben auf dem Rahmen“ (tools/plugin-vorlage/photo-privacy).

Ist er an, schickt das Plugin keine GPS-Position eines Fotos mehr an einen
Online-Dienst (Ortsnamen, Wetter oder Höhe von damals, Sehenswürdigkeiten).
Was schon im Cache liegt, wird weiter gezeigt. Die selbst eingetragene
Heimat ist kein Foto und bleibt erlaubt.

    import photo_privacy
    SCHEMA.update(photo_privacy.SCHEMA)
    photo_privacy.bind(settings)               # nach def settings()
    if photo_privacy.blocks(lat, lon): return ""   # vor jeder Anfrage mit Fotoposition
    photo_privacy.active()                      # Schalter an?
    photo_privacy.note()                        # Text für die Verbindungskarte
"""

KEY = "KeepPhotoPlaces"
SCHEMA = {KEY: {"kind": "bool", "default": False}}

NOTE = {
    "de": "Fotopositionen bleiben auf dem Rahmen: Hier geht keine Fotoposition raus, darum keine Prüfung.",
    "en": "Photo locations stay on the frame: no photo position goes out here, so no check.",
    "es": "Las ubicaciones de las fotos se quedan en el marco: aquí no sale ninguna posición de foto, así que no hay comprobación.",
}

_getter = None


def bind(getter):
    """getter() liefert die Einstellungen des Plugins (dict)."""
    global _getter
    _getter = getter


def _values():
    try:
        values = _getter() if _getter else {}
    except Exception:  # noqa: BLE001 - Einstellungen kaputt: lieber blockieren als senden
        return {KEY: True}
    return values if isinstance(values, dict) else {}


def active():
    return bool(_values().get(KEY))


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def blocks(lat, lon):
    """True, wenn eine Anfrage mit dieser Position nicht raus darf (Schalter an und nicht die Heimat)."""
    values = _values()
    if not values.get(KEY):
        return False
    home_lat, home_lon = _num(values.get("HomeLat")), _num(values.get("HomeLon"))
    lat, lon = _num(lat), _num(lon)
    if None in (home_lat, home_lon, lat, lon) or (home_lat == 0 and home_lon == 0):
        return True
    return abs(lat - home_lat) > 0.02 or abs(lon - home_lon) > 0.02


def note(lang=None):
    if lang is None:
        lang = _values().get("Language")
    return NOTE.get(str(lang or "")[:2], NOTE["en"])
