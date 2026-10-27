"""Bordcomputer-Skin für Dynaframe's Magic Mirror: Wetter am Ort oben auf der
Plugin-Seite (jetzt, Sonne, die nächsten Tage) für die eigenen Felder. Holt
dasselbe wie die eingebauten Skins; Uhr, Datum und Sternzeit rechnet die Szene."""


def fetch(config, ctx):
    if "weather" not in ctx:
        raise RuntimeError("Für das Wetter im Skin bitte Dynaframe's Magic Mirror auf 0.6.0 oder neuer aktualisieren.")
    return ctx["weather"]()
