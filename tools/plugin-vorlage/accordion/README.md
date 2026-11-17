# Aufklappen (Akkordeon) für Plugin-Seiten

Jans Regel (17.11.2026, Wunsch aus dem Discord): **Lange Plugin-Seiten klappen
Karten zu, die gerade nicht gebraucht werden.** Wer Immich nicht als Quelle
gewählt hat, sieht von der Immich-Karte nur die Kopfzeile „Immich-Server · Nur
mit Immich als Quelle nötig“. Wählt man Immich, klappt die Karte von selbst auf.
Gilt für jede neue Plugin-Seite; bestehende Seiten werden angeglichen.

## Einbau

    python3 tools/plugin-vorlage/accordion/apply.py <pack-ordner> [extra.json]

Hängt `accordion.js` an `studio.js` und `accordion.css` an `studio.css` (zwischen
Marken, ein zweiter Lauf erneuert den Stand) und markiert die Standard-Karten.
An `render()` muss nichts geändert werden: Das Skript liest die Felder selbst
(bei jeder Eingabe und jede Sekunde) und wartet mit dem Zuklappen, bis
`#factVersion` eine Version zeigt, also der Stand geladen ist. Eigene Texte
(DE/EN/ES) stehen im Skript, die Sprache kommt aus `<html lang>`.

## Was standardmäßig zuklappt

| Karte / Abschnitt (data-i18n der Überschrift) | Verhalten | Plakette |
|---|---|---|
| Welche Fotos aus DynaFrame (`dfTitle`) | nur offen, wenn man sie aufklappt; ohne DynaFrame-Quelle grau | „2 aktiv“ / „Keine Filter“ |
| Immich-Server (`serverTitle`) | offen, sobald eine Quelle Immich ist, sonst zu | „Nur mit Immich als Quelle nötig“ |
| Welche Fotos aus Immich (`h3.sub filterTitle`) | Abschnitt in der Immich-Karte, zu | „3 aktiv“ / „Keine Filter“ |
| Volle Auflösung für WebDAV-Fotos (`davTitle`) | zu (freiwillig) | „Eingerichtet“ / „Optional“ |
| Weitere Ordner auf dem Rahmen (`foldersTitle`) | zu, nur bei „Alle Fotos in DynaFrame“ gebraucht | „2 eingetragen“ / „Optional“ |
| Verbindungen (`servicesTitle`) | zu, **geht von selbst auf, wenn etwas rot ist** | „Alles erreichbar“ / „1 Problem“ |

Nie zuklappen: Kopf, Status-Karte, die Haupt-Karte des Plugins (Quelle, was es
zeigt) und „Eine Playlist dafür“ (bleibt letzte Karte, kurz genug).

Eine Wahl von Hand (auf- oder zuklappen) merkt sich der Browser je Seite, bis
sich die Quelle ändert; dann gilt wieder die Regel.

## Attribute (für eigene Karten)

    <section class="card" data-fold="look" data-fold-start="closed">          → zuklappbar, startet zu
    <section class="card" data-fold="immich" data-fold-when="uses:immich">    → offen nur, wenn gebraucht
    <h3 class="sub" data-i18n="advTitle" data-fold="adv" data-fold-start="closed">  → Abschnitt bis zum nächsten h3.sub/<details>

- `data-fold="<id>"`: eindeutige ID auf der Seite (für das Merken).
- `data-fold-when`: `uses:immich`, `uses:dynaframe`, `uses:library` (Quellen-Auswahl =
  jedes `<select>` mit einer Option `immich…`, auch Quellen-Zeilen) oder `Feld=wert1,wert2`;
  mehrere mit `|`. Nicht gebraucht = zu, grau, mit Grund als Plakette.
- `data-fold-start="closed"`: auch wenn gebraucht erst zu (freiwillige Karten, „Erweitert“).
- `data-fold-badge`: `count` (Filter aktiv), `filled` (Adresse eingetragen), `lines`
  (Zeilen im Textfeld), `services` (Verbindungsliste `.svc.ok/.warn/.bad`).
- Mit `extra.json` setzt `apply.py` das für weitere Überschriften, z. B.
  `{"advTitle": {"fold": "adv", "start": "closed"}}`.
- Aus `studio.js`: `Fold.open("immich")` klappt eine Karte auf (z. B. nach „Verbindung testen“ mit Fehler).

## Wofür noch

- „Erweitert“-Einstellungen, die fast niemand ändert: eigener Abschnitt `h3.sub` mit `data-fold-start="closed"`.
- Logins je Quelle (Immich, WebDAV, Spotify, Home Assistant …): `data-fold-when` auf die Quelle.
- Lange Erklärungen: weiter `<details>` („So bekommst du einen API-Schlüssel“).
