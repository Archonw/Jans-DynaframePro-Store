#!/usr/bin/env python3
"""
PlaylistButtonPlugin fuer Dynaframe Pro (v3 - auf Basis von dynaframe_plugin_base.py).

Verhalten (GPIO21, per Settings konfigurierbar):
- Erster kurzer Tastendruck: oeffnet ein Text-Overlay mit allen Playlisten
  (alphabetisch nach Name sortiert), die aktuell aktive Playlist ist markiert.
- Jeder weitere kurze Tastendruck bei geoeffnetem Overlay: springt zur naechsten
  Playlist in der Liste (nur Markierung, aendert noch NICHT die aktive Playlist).
- 10 Sekunden (konfigurierbar) ohne weiteren Tastendruck: Overlay wird
  ausgeblendet, die tatsaechlich aktive Playlist bleibt unveraendert.
- Langer Tastendruck: aktiviert die aktuell im Menue markierte Playlist ueber
  POST /slideshow/start/{playlistId} und schliesst das Overlay.

Genutzte Engine-Endpunkte (bestaetigt per swagger.json):
  GET  /playlists              -> Liste aller Playlisten (id, name, isEnabled, ...)
  GET  /slideshow/status       -> u.a. activePlaylistId
  POST /slideshow/start/{id}   -> startet die Playlist mit dieser id (kein Body)
  POST /renderer/overlay/settings -> Overlay-Layout ein-/ausschalten (enabled, currentOverlay)
Genutzte Plugin-Base-Methoden:
  plugin.engine_url            -> Basis-URL der Engine (aus DYNAFRAME_ENGINE_URL)
  page.settings()              -> Einstellungen von der eigenen Plugin-Seite (data/settings.json)
  plugin.update_overlay_text() -> setzt den Text der PlaylistButtonPlugin.MenuText-Overlay-Quelle
  plugin.log() / plugin.ready() / plugin.is_running()
"""

import os
import sys
import traceback
from datetime import datetime

# lgpio (Backend von gpiozero auf dem Pi 5) legt beim Initialisieren eine
# Notify-Pipe-Datei im aktuellen Arbeitsverzeichnis an. Falls der Prozess mit
# einem fuer den pi-User nicht beschreibbaren cwd gestartet wird (z.B. "/"),
# crasht die GPIO-Initialisierung lautlos. Deshalb explizit in ein garantiert
# beschreibbares Verzeichnis wechseln, bevor gpiozero verwendet wird.
_plugin_dir = os.environ.get("DYNAFRAME_PLUGIN_DIR") or os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(_plugin_dir)
except Exception:
    pass

_crash_log_path = os.path.join(_plugin_dir, "crash.log")


def _write_crash_log(exc_type, exc_value, exc_tb):
    try:
        with open(_crash_log_path, "a") as f:
            f.write(f"\n=== Crash at {datetime.now().isoformat()} ===\n")
            f.write(f"cwd={os.getcwd()}\n")
            f.write(f"__file__={os.path.abspath(__file__)}\n")
            f.write(f"sys.executable={sys.executable}\n")
            f.write(f"sys.path={sys.path}\n")
            f.write(f"env DYNAFRAME_PLUGIN_DIR={os.environ.get('DYNAFRAME_PLUGIN_DIR')}\n")
            f.write(f"env DYNAFRAME_ENGINE_URL={os.environ.get('DYNAFRAME_ENGINE_URL')}\n")
            f.write(f"env PYTHONPATH={os.environ.get('PYTHONPATH')}\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _write_crash_log

import json
import threading
import time
import uuid
from pathlib import Path

import requests
from gpiozero import Button

sys.path.insert(0, str(Path(__file__).parent.parent))
from dynaframe_plugin_base import create_plugin

TEXT_SERVICE_ID = "PlaylistButtonPlugin.MenuText"
MENU_TEXT_ELEMENT_ID = "playlist-menu-text-element"
MENU_TEXTS = {
    "de": {"more": "weitere", "active": "aktiv"},
    "en": {"more": "more", "active": "active"},
    "es": {"more": "más", "active": "activa"},
}

plugin = create_plugin()

import page

# Persistent HTTP session — reuses TCP connections instead of opening a new one
# per request, avoiding repeated DNS lookups, TCP handshakes, and TLS negotiation.
_http = requests.Session()

# --------------------------------------------------------------------------
# Zustand (durch Lock geschuetzt, da Callbacks aus gpiozero-Threads kommen)
# --------------------------------------------------------------------------
state_lock = threading.Lock()
state = {
    "overlay_visible": False,
    "selected_index": 0,
    "playlists": [],
    "active_playlist_id": None,
    "active_playlist_name": None,
    "inactivity_timer": None,
    "long_press_triggered": False,
}

# Event used to wake the main loop for a clean shutdown instead of busy-polling.
_shutdown_event = threading.Event()


def fetch_saved_playlists(only_enabled):
    try:
        resp = _http.get(f"{plugin.engine_url}/playlists", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        plugin.log(f"Playlisten-Abfrage fehlgeschlagen: {exc}", level="error")
        return []

    return [
        {"kind": "playlist", "id": p["id"], "name": p.get("name") or f"Playlist {p['id']}"}
        for p in data
        if not only_enabled or p.get("isEnabled", True)
    ]


_folder_cache = {"items": None, "fetched_at": 0.0}
_folder_cache_lock = threading.Lock()


def fetch_folder_playlists(cache_seconds):
    """Holt alle Ordner-Playlisten (Folder Playlists) von der Engine.
    Wird kurzzeitig zwischengespeichert, da dieser Aufruf (Vorschaubilder fuer
    potenziell viele Ordner) spuerbar langsamer ist als die uebrigen Abfragen
    und sich Ordnerinhalte selten kurzfristig aendern."""
    with _folder_cache_lock:
        age = time.monotonic() - _folder_cache["fetched_at"]
        if _folder_cache["items"] is not None and age < cache_seconds:
            return _folder_cache["items"]

    try:
        resp = _http.get(f"{plugin.engine_url}/media/folder-sources", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = [
            {"kind": "folder", "path": s["path"], "name": s.get("label") or s["path"]}
            for s in data.get("sources", [])
        ]
        with _folder_cache_lock:
            _folder_cache["items"] = items
            _folder_cache["fetched_at"] = time.monotonic()
        return items
    except Exception as exc:
        plugin.log(f"Ordner-Playlisten-Abfrage fehlgeschlagen: {exc}", level="error")
        with _folder_cache_lock:
            return _folder_cache["items"] or []


def fetch_menu_items(only_enabled, show_folders, folder_cache_seconds):
    items = fetch_saved_playlists(only_enabled)
    if show_folders:
        items += fetch_folder_playlists(folder_cache_seconds)
    items.sort(key=lambda p: p["name"].casefold())
    return items


def fetch_active_playlist_info():
    try:
        resp = _http.get(f"{plugin.engine_url}/slideshow/status", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("activePlaylistId"), data.get("playlistName")
    except Exception as exc:
        plugin.log(f"Status-Abfrage fehlgeschlagen: {exc}", level="warning")
        return None, None


def is_active(item, active_playlist_id, active_playlist_name):
    if item["kind"] == "playlist":
        return item["id"] == active_playlist_id
    return item["name"] == active_playlist_name


def compute_window_start(total, selected_index, window_size, anchor_index):
    if total <= window_size:
        return 0
    start = selected_index - anchor_index
    start = max(0, start)
    start = min(start, total - window_size)
    return start


def render_menu_text(items, selected_index, active_playlist_id, active_playlist_name,
                      window_size, anchor_index, lang="de"):
    words = MENU_TEXTS.get(lang, MENU_TEXTS["de"])
    total = len(items)
    anchor_index = max(0, min(anchor_index, window_size - 1))
    start = compute_window_start(total, selected_index, window_size, anchor_index)
    end = min(start + window_size, total)

    lines = []
    if start > 0:
        lines.append(f"   ↑ {start} {words['more']}")
    for i in range(start, end):
        item = items[i]
        marker = "➤ " if i == selected_index else "   "
        suffix = f"  ({words['active']})" if is_active(item, active_playlist_id, active_playlist_name) else ""
        lines.append(f"{marker}{item['name']}{suffix}")
    remaining_below = total - end
    if remaining_below > 0:
        lines.append(f"   ↓ {remaining_below} {words['more']}")

    return "\n".join(lines)


def push_overlay_text(value):
    """Setzt den Overlay-Text direkt ueber unsere wiederverwendete Session,
    statt ueber plugin.update_overlay_text() (Basisklasse) zu gehen. Die
    Basisklasse baut dafuer bei jedem Aufruf eine neue TCP-Verbindung auf statt
    eine bestehende wiederzuverwenden - das faellt v.a. beim Scrollen (dem mit
    Abstand haeufigsten Call) spuerbar ins Gewicht. Der Payload entspricht
    exakt dem, was update_overlay_text() intern verwendet."""
    try:
        resp = _http.post(
            f"{plugin.engine_url}/plugins/overlay/update",
            json={"PluginDataId": TEXT_SERVICE_ID, "Value": value},
            timeout=5,
        )
        if resp.status_code != 200:
            plugin.log(f"Overlay-Text-Update fehlgeschlagen (HTTP {resp.status_code})", level="error")
    except Exception as exc:
        plugin.log(f"Overlay-Text-Update fehlgeschlagen: {exc}", level="error")


def push_menu_overlay(settings):
    with state_lock:
        text = render_menu_text(
            state["playlists"],
            state["selected_index"],
            state["active_playlist_id"],
            state["active_playlist_name"],
            settings["visible_lines"],
            settings["anchor_line"] - 1,
            settings["language"],
        )
    push_overlay_text(text)


def set_overlay_enabled(overlay_file, enabled):
    try:
        resp = _http.post(
            f"{plugin.engine_url}/renderer/overlay/settings",
            json={"enabled": enabled, "currentOverlay": overlay_file},
            timeout=5,
        )
        if resp.status_code != 200:
            plugin.log(
                f"Overlay-Umschalten fehlgeschlagen (HTTP {resp.status_code}): {resp.text[:200]}",
                level="error",
            )
    except Exception as exc:
        plugin.log(f"Overlay {'ein' if enabled else 'aus'}schalten fehlgeschlagen: {exc}", level="error")


def activate_item(item):
    if item["kind"] == "playlist":
        try:
            resp = _http.post(f"{plugin.engine_url}/slideshow/start/{item['id']}", timeout=5)
            if resp.status_code == 200:
                plugin.log(f"Playlist gewechselt zu: {item['name']} (id={item['id']})")
                return True
            plugin.log(
                f"Playlist-Wechsel fehlgeschlagen (HTTP {resp.status_code}): {resp.text[:200]}",
                level="error",
            )
        except Exception as exc:
            plugin.log(f"Playlist-Wechsel fehlgeschlagen: {exc}", level="error")
        return False

    try:
        resp = _http.post(
            f"{plugin.engine_url}/playlists/play-selection",
            json={
                "quickMixState": {
                    "selectedFolders": [item["path"]],
                    "selectedPlugins": [],
                    "enabledSavedPlaylistIds": [],
                },
                "playlistName": item["name"],
                "startPlayback": True,
            },
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("success"):
            plugin.log(f"Ordner-Playlist gewechselt zu: {item['name']} ({item['path']})")
            return True
        plugin.log(
            f"Ordner-Playlist-Wechsel fehlgeschlagen (HTTP {resp.status_code}): {resp.text[:200]}",
            level="error",
        )
    except Exception as exc:
        plugin.log(f"Ordner-Playlist-Wechsel fehlgeschlagen: {exc}", level="error")
    return False


def cancel_inactivity_timer():
    if state["inactivity_timer"] is not None:
        state["inactivity_timer"].cancel()
        state["inactivity_timer"] = None


def start_inactivity_timer(timeout_seconds, overlay_file):
    cancel_inactivity_timer()
    timer = threading.Timer(timeout_seconds, hide_overlay, args=(overlay_file,))
    timer.daemon = True
    state["inactivity_timer"] = timer
    timer.start()


def hide_overlay(overlay_file):
    with state_lock:
        if not state["overlay_visible"]:
            return
        state["overlay_visible"] = False
        cancel_inactivity_timer()
    set_overlay_enabled(overlay_file, False)
    plugin.log("Overlay ausgeblendet (Timeout oder Playlist-Wechsel).")


def handle_short_press(settings):
    # Check current state without holding the lock during HTTP calls.
    with state_lock:
        was_visible = state["overlay_visible"]

    if not was_visible:
        # Fetch data OUTSIDE the lock so GPIO callbacks aren't blocked on network I/O.
        items = fetch_menu_items(
            settings["only_enabled"], settings["show_folders"], settings["folder_cache_seconds"]
        )
        if not items:
            plugin.log("Keine Playlisten gefunden.", level="warning")
            return
        active_id, active_name = fetch_active_playlist_info()
        # Neue oder umbenannte Playlisten koennen den Kasten breiter oder hoeher
        # machen; nur dann wird das Overlay-Design neu gespeichert.
        style = current_style(items)
        if _synced_style["file"] != settings["overlay_file"] or _synced_style["style"] != style:
            sync_overlay_style(settings["overlay_file"], style)

        with state_lock:
            # Re-check: another thread may have opened the overlay while we fetched.
            if state["overlay_visible"]:
                if state["playlists"]:
                    state["selected_index"] = (state["selected_index"] + 1) % len(state["playlists"])
            else:
                state["playlists"] = items
                state["active_playlist_id"] = active_id
                state["active_playlist_name"] = active_name
                state["selected_index"] = next(
                    (i for i, it in enumerate(items) if is_active(it, active_id, active_name)), 0
                )
                state["overlay_visible"] = True

        push_menu_overlay(settings)
        set_overlay_enabled(settings["overlay_file"], True)
    else:
        with state_lock:
            if state["playlists"]:
                state["selected_index"] = (state["selected_index"] + 1) % len(state["playlists"])

        # Only push the updated text — the overlay is already enabled.
        push_menu_overlay(settings)

    start_inactivity_timer(settings["overlay_timeout_seconds"], settings["overlay_file"])


def handle_long_press(settings):
    with state_lock:
        if not state["overlay_visible"] or not state["playlists"]:
            plugin.log("Langer Druck ignoriert: kein Menue geoeffnet.")
            return
        target = state["playlists"][state["selected_index"]]

    success = activate_item(target)
    if success:
        with state_lock:
            if target["kind"] == "playlist":
                state["active_playlist_id"] = target["id"]
                state["active_playlist_name"] = None
            else:
                state["active_playlist_id"] = None
                state["active_playlist_name"] = target["name"]

    hide_overlay(settings["overlay_file"])


MENU_PADDING = 16
LINE_HEIGHT = 1.35   # Zeilenhoehe des Overlay-Textes, relativ zur Schriftgroesse
CHAR_WIDTH = 0.56    # mittlere Zeichenbreite von Arial, relativ zur Schriftgroesse


def menu_box_size(items, values):
    """Breite und Hoehe des Menue-Kastens passend zu Schriftgroesse, Zeilenzahl
    und laengstem Playlist-Namen, damit der farbige Hintergrund den Text genau
    umschliesst, statt bei grosser Schrift zu klein oder bei kleiner zu gross
    zu sein."""
    font_size = values["FontSize"]
    total = len(items)
    window = values["VisibleLines"]
    lines = max(1, min(total, window)) + (2 if total > window else 0)
    words = MENU_TEXTS.get(values["Language"], MENU_TEXTS["de"])
    suffix = len(words["active"]) + 4
    longest = max((len(it["name"]) for it in items), default=12)
    chars = max(longest + 3 + suffix, len(words["more"]) + 8)
    width = int(round(chars * CHAR_WIDTH * font_size + 2 * MENU_PADDING))
    height = int(round(lines * LINE_HEIGHT * font_size + 2 * MENU_PADDING))
    return width, height


def current_style(items=None):
    values = page.settings()
    if items is None:
        items = fetch_menu_items(values["OnlyEnabledPlaylists"], values["ShowFolderPlaylists"],
                                 values["FolderCacheSeconds"])
    width, height = menu_box_size(items, values)
    return {
        "fontSize": values["FontSize"],
        "backgroundColor": values["BackgroundColor"],
        "backgroundOpacity": values["BackgroundOpacity"],
        "padding": MENU_PADDING,
        "width": width,
        "height": height,
    }


_synced_style = {"file": None, "style": None}


def ensure_overlay_design(overlay_file):
    try:
        resp = _http.get(f"{plugin.engine_url}/overlay/list", timeout=5)
        resp.raise_for_status()
        existing = resp.json()
        if any(d.get("fileName") == overlay_file for d in existing):
            plugin.log(f"Overlay-Design '{overlay_file}' bereits vorhanden.")
            return
    except Exception as exc:
        plugin.log(f"Konnte Overlay-Liste nicht abrufen: {exc}", level="warning")
        return

    style = current_style()
    config = {
        "id": 0,
        "designId": uuid.uuid4().hex,
        "variantId": uuid.uuid4().hex,
        "name": "Playlist Menu",
        "description": "Zeigt das Playlist-Auswahlmenue des PlaylistButtonPlugin an",
        "elements": [
            {
                "$type": "plugin-text",
                "pluginDataId": TEXT_SERVICE_ID,
                "pluginName": "PlaylistButtonPlugin",
                "pluginFriendlyName": "Playlist-Auswahlmenue",
                "prefixText": "",
                "defaultValue": "",
                "fontFamily": "Arial",
                "fontSize": style["fontSize"],
                "fontWeight": 400,
                "color": "#FFFFFF",
                "backgroundColor": style["backgroundColor"],
                "backgroundOpacity": style["backgroundOpacity"],
                "textAlign": "left",
                "bold": False,
                "italic": False,
                "opacity": 100,
                "padding": style["padding"],
                "borderRadius": 8,
                "dropShadowEnabled": True,
                "dropShadowAngle": 45,
                "dropShadowDistance": 4,
                "dropShadowBlur": 2,
                "dropShadowColor": "#000000",
                "dropShadowOpacity": 70,
                "id": MENU_TEXT_ELEMENT_ID,
                "x": 0,
                "y": 0,
                "xPercent": 5,
                "yPercent": 55,
                "width": style["width"],
                "height": style["height"],
                "zIndex": 10,
                "visible": True,
                "locked": False,
                "animateIn": "none",
                "animateOut": "none",
                "inAnimationTime": 500,
                "outAnimationTime": 500,
                "matchInDuration": False,
                "matchOutDuration": False,
                "syncOutWithTransition": False,
                "delayBeforeStart": 0,
                "delayBeforeExit": "none",
            }
        ],
        "orientation": "landscape",
        "padding": None,
        "ownerPlugin": None,
        "templateId": None,
        "templateVersion": None,
        "categoryKey": "uncategorized",
        "origin": "user",
        "sourceId": None,
        "basedOnDesignId": None,
        "isCustomThumbnail": False,
        "isReadOnly": False,
    }

    try:
        resp = _http.post(
            f"{plugin.engine_url}/overlay/save",
            json={"config": config, "fileName": overlay_file},
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("success"):
            plugin.log(f"Overlay-Design '{overlay_file}' automatisch angelegt.")
        else:
            plugin.log(
                f"Anlegen des Overlay-Designs fehlgeschlagen: {resp.text[:200]}",
                level="error",
            )
    except Exception as exc:
        plugin.log(f"Anlegen des Overlay-Designs fehlgeschlagen: {exc}", level="error")


def sync_overlay_style(overlay_file, style):
    try:
        resp = _http.get(f"{plugin.engine_url}/overlay/load/{overlay_file}", timeout=5)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            plugin.log("Overlay-Design zum Style-Sync nicht gefunden.", level="warning")
            return
        config = payload["config"]
    except Exception as exc:
        plugin.log(f"Konnte Overlay-Design nicht laden (Style-Sync): {exc}", level="warning")
        return

    changed = False
    for el in config.get("elements", []):
        if el.get("id") != MENU_TEXT_ELEMENT_ID:
            continue
        for key, value in style.items():
            if el.get(key) != value:
                el[key] = value
                changed = True

    if not changed:
        _synced_style.update(file=overlay_file, style=dict(style))
        return

    try:
        resp = _http.post(
            f"{plugin.engine_url}/overlay/save",
            json={"config": config, "fileName": overlay_file},
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("success"):
            _synced_style.update(file=overlay_file, style=dict(style))
            plugin.log(
                f"Overlay-Stil aktualisiert: {style['fontSize']}px, Kasten {style['width']}x{style['height']}, Hintergrund "
                f"{style['backgroundColor']} mit {style['backgroundOpacity']}% Deckkraft."
            )
        else:
            plugin.log(f"Style-Sync fehlgeschlagen: {resp.text[:200]}", level="error")
    except Exception as exc:
        plugin.log(f"Style-Sync fehlgeschlagen: {exc}", level="error")


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------
def runtime_settings():
    """Die Einstellungen von der Plugin-Seite, unter den Namen, die die
    Tastenlogik verwendet. Wird bei jedem Tastendruck neu gelesen, damit
    Aenderungen sofort gelten."""
    values = page.settings()
    return {
        "long_press_seconds": values["LongPressSeconds"],
        "overlay_timeout_seconds": values["OverlayTimeoutSeconds"],
        "overlay_file": values["OverlayFileName"],
        "only_enabled": values["OnlyEnabledPlaylists"],
        "show_folders": values["ShowFolderPlaylists"],
        "visible_lines": values["VisibleLines"],
        "anchor_line": values["AnchorLine"],
        "folder_cache_seconds": values["FolderCacheSeconds"],
        "language": values["Language"],
    }


_status = {"button": "", "buttonOk": False}
STYLE_SETTINGS = {"FontSize", "BackgroundColor", "BackgroundOpacity", "VisibleLines", "Language",
                  "OnlyEnabledPlaylists", "ShowFolderPlaylists"}


def on_settings_changed(changed):
    changed = set(changed)
    overlay_file = page.settings()["OverlayFileName"]
    if "OverlayFileName" in changed:
        ensure_overlay_design(overlay_file)
    if changed & (STYLE_SETTINGS | {"OverlayFileName"}):
        sync_overlay_style(overlay_file, current_style())
    with state_lock:
        visible = state["overlay_visible"]
    if visible:
        push_menu_overlay(runtime_settings())
    if changed & {"GpioPin", "LongPressSeconds"}:
        _button_wake.set()


def show_menu():
    """Wie ein kurzer Tastendruck: oeffnet das Menue oder springt eine Zeile weiter."""
    threading.Thread(target=on_released, name="show-menu", daemon=True).start()
    return {"success": True}


def page_state():
    with state_lock:
        visible = state["overlay_visible"]
    return {"version": _version(), "button": _status["button"], "buttonOk": _status["buttonOk"],
            "menuVisible": visible}


def _version():
    try:
        manifest = json.loads((Path(__file__).resolve().parent / "manifest.json").read_text(encoding="utf-8"))
        return str(manifest.get("Version") or "")
    except Exception:
        return ""


_button_wake = threading.Event()
page.migrate(plugin)
plugin.on_action("show-menu", lambda _context=None: show_menu())
plugin.connect_sse()

# Report ready before touching the overlay or the GPIO, so a missing or busy pin
# can never leave the plugin stuck in "waiting for plugin to finish initializing".
page.start(plugin, state=page_state, changed=on_settings_changed, show=show_menu)
plugin.ready()

try:
    ensure_overlay_design(page.settings()["OverlayFileName"])
    sync_overlay_style(page.settings()["OverlayFileName"], current_style())
except Exception as exc:
    plugin.log(f"Overlay-Design konnte nicht vorbereitet werden: {exc}", level="error")


def on_held():
    with state_lock:
        state["long_press_triggered"] = True
    try:
        handle_long_press(runtime_settings())
    except Exception as exc:
        plugin.log(f"Fehler bei Langdruck-Verarbeitung: {exc}", level="error")


def on_released():
    with state_lock:
        was_long = state["long_press_triggered"]
        state["long_press_triggered"] = False
    if was_long:
        return
    try:
        handle_short_press(runtime_settings())
    except Exception as exc:
        plugin.log(f"Fehler bei Kurzdruck-Verarbeitung: {exc}", level="error")


def _find_gpio_pin_factory():
    """Sucht den GPIO-Chip des Pin-Headers und gibt eine passende lgpio-Factory zurueck.

    Die Chip-Nummer ist nicht fest: Aeltere Kernel verwenden gpiochip4 (Pi 5), neuere
    gpiochip0, und manche Systeme nummerieren die Chips anders (z.B. gpiochip15).
    gpiozero probiert aber nur 4 und 0. Deshalb wird der Chip ueber sein Label
    ("pinctrl-rp1", "pinctrl-bcm2711", "pinctrl-bcm2835") gefunden.
    Gibt None zurueck, wenn nichts gefunden wird; dann gilt das gpiozero-Standardverhalten.
    """
    try:
        import glob
        import lgpio
        from gpiozero.pins.lgpio import LGPIOFactory
    except Exception:
        return None

    chips = []
    for path in glob.glob("/dev/gpiochip*"):
        suffix = path[len("/dev/gpiochip"):]
        if suffix.isdigit():
            chips.append(int(suffix))

    for chip in sorted(chips):
        try:
            handle = lgpio.gpiochip_open(chip)
        except Exception:
            continue
        try:
            info = lgpio.gpio_get_chip_info(handle)
        except Exception:
            info = None
        finally:
            try:
                lgpio.gpiochip_close(handle)
            except Exception:
                pass
        if isinstance(info, (list, tuple)) and len(info) >= 4 and str(info[3]).startswith("pinctrl-"):
            try:
                factory = LGPIOFactory(chip=chip)
            except Exception:
                continue
            plugin.log(f"GPIO-Chip gefunden: gpiochip{chip} ({info[3]}).")
            return factory
    return None


_button = None
_button_key = None
_pin_factory = None
_pin_factory_done = False


def _gpio_pin():
    """BCM-Pin aus den Settings, oder None solange kein (gueltiger) Pin eingetragen ist."""
    raw = page.settings()["GpioPin"]
    return int(raw) if raw else None


def _setup_button():
    """Legt den Taster fuer den eingestellten Pin an. Wirft nie; ein belegter Pin wird nur geloggt."""
    global _button, _button_key, _pin_factory, _pin_factory_done
    pin = _gpio_pin()
    long_press = page.settings()["LongPressSeconds"]
    key = (pin, long_press)
    if key == _button_key:
        return
    _button_key = key
    if _button is not None:
        try:
            _button.close()
        except Exception:
            pass
        _button = None
    if pin is None:
        _status.update(button="nopin", buttonOk=False)
        plugin.log("No GPIO pin set yet. Enter the BCM pin of your button on the plugin page "
                   "(for example 21).", level="warning")
        return
    if not _pin_factory_done:
        _pin_factory = _find_gpio_pin_factory()
        _pin_factory_done = True
    try:
        button = Button(
            pin,
            pull_up=True,
            bounce_time=0.05,
            hold_time=long_press,
            hold_repeat=False,
            pin_factory=_pin_factory,
        )
    except Exception as exc:
        _status.update(button=f"busy:{pin}:{exc}", buttonOk=False)
        plugin.log(f"GPIO{pin} cannot be used: {exc}. It is probably taken by another plugin "
                   "or device; choose a different pin on the plugin page.", level="error")
        return
    button.when_held = on_held
    button.when_released = on_released
    _button = button
    _status.update(button=f"ready:{pin}", buttonOk=True)
    plugin.log(f"PlaylistButtonPlugin bereit auf GPIO{pin} (lang={long_press}s).")


def _button_loop():
    """Uebernimmt geaenderte GpioPin/LongPressSeconds ohne Neustart des Plugins."""
    while True:
        try:
            _setup_button()
        except Exception as exc:
            plugin.log(f"Taster-Einrichtung fehlgeschlagen: {exc}", level="error")
        _button_wake.wait(5)
        _button_wake.clear()
        if _shutdown_event.is_set():
            break


threading.Thread(target=_button_loop, name="button", daemon=True).start()

_shutdown_event.wait()
page.stop(plugin)
