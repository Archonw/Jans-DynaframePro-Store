"""Playlists mit einem alten Namen bekommen den neuen, englischen Namen.

Seit 12.11.2026 heißen alle Plugins in allen Sprachen englisch (Jans Wunsch).
Beim ersten Start nach dem Update benennt dieses Modul Playlists um, die das
Plugin früher unter dem alten Namen angelegt hat. Es läuft einmal im
Hintergrund und versucht es bis zu zehn Minuten lang, falls die Engine noch
nicht antwortet.

    import renamed_playlists
    renamed_playlists.start(engine_call, log, {"Alter Name": "New name"})
"""

import threading
import time


def rename_all(engine_call, log, renames):
    rows = engine_call("GET", "/playlists") or []
    if isinstance(rows, dict):
        rows = rows.get("playlists") or []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        new = renames.get(row.get("name"))
        if not new:
            continue
        playlist_id = row["id"]
        full = engine_call("GET", f"/playlists/{playlist_id}")
        if isinstance(full, dict) and isinstance(full.get("playlist"), dict):
            full = full["playlist"]
        if not isinstance(full, dict) or str(full.get("id")) != str(playlist_id):
            continue
        # Vollständig zurückschreiben, damit PUT nichts anderes leert.
        body = {k: v for k, v in full.items() if k not in ("items", "itemCount", "createdAt", "updatedAt")}
        body["name"] = new
        engine_call("PUT", f"/playlists/{playlist_id}", body)
        log(f"Playlist {row.get('name')} in {new} umbenannt.", "info")


def start(engine_call, log, renames, tries=10, wait=60):
    def run():
        last = None
        for _ in range(tries):
            try:
                rename_all(engine_call, log, renames)
                return
            except Exception as exc:  # Engine noch nicht bereit o. ä.
                last = exc
                time.sleep(wait)
        log(f"Alte Playlists nicht umbenannt: {last}", "warning")

    threading.Thread(target=run, name="renamed-playlists", daemon=True).start()
