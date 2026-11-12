"""Die eigene Playlist eines Plugins, wie bei Growing Up.

Auf der Plugin-Seite steht ganz unten die Karte „Eine Playlist dafür“ mit der
Auswahl Nein / Ja, anlegen. Steht sie auf Ja, legt das Plugin eine
eingeschaltete Playlist an, die nur seine Szene enthält. Löscht jemand die
Playlist, springt die Auswahl auf Nein und sie wird nicht neu angelegt.

Eine Playlist, die früher über den Knopf „Playlist anlegen“ entstanden ist,
übernimmt das Modul beim ersten Lauf (Auswahl steht dann auf Ja).

Einbau (Beispiel):

    import own_playlist
    OWN = own_playlist.OwnPlaylist(
        state_file=DATA_DIR / "own_playlist.json",
        names=PLAYLIST_NAMES.values(),                 # alle Namen, die sie je hatte
        name=lambda: PLAYLIST_NAMES[settings()["Language"]],
        description=lambda: tr("..."),
        scene_id=lambda: (find_scene() or {}).get("id"),
        seconds=lambda: settings()["PlaylistSeconds"],
        wanted=lambda: settings()["MakePlaylist"],
        set_wanted=lambda on: save_settings({"MakePlaylist": on}),
        engine_call=engine_call,
        language=lambda: settings()["Language"],
        log=lambda text, level="info": log(text, level),
        held=screen_held,                              # nur bei Takeover-Plugins
    )

    SCHEMA["MakePlaylist"] = bool, Standard False
    state_payload():   "ownPlaylist": OWN.text()  (ruft OWN.maintain() auf)
    /api/settings:     if "MakePlaylist" in changed: OWN.changed()
    Aktion "playlist": OWN.create_now()
"""

import json
import threading
import time
from pathlib import Path

LANGS = ("de", "en", "es")

TEXTS = {
    "created": ("Angelegt: die Playlist {name} steht unter Playlists.",
                "Created: the {name} playlist is listed under Playlists.",
                "Creada: la lista {name} aparece en Playlists."),
    "pending": ("Noch nicht angelegt; das passiert innerhalb einer Minute.",
                "Not created yet; that happens within a minute.",
                "Aún no creada; ocurrirá en menos de un minuto."),
    "deleted": ("Die Playlist wurde gelöscht, deshalb steht das wieder auf Nein.",
                "The playlist was deleted, so this is set back to No.",
                "La lista se borró, por eso vuelve a estar en No."),
    "left": ("Die früher angelegte Playlist steht noch unter Playlists; das Plugin pflegt sie nicht mehr.",
             "The playlist created earlier is still under Playlists; the plugin no longer maintains it.",
             "La lista creada antes sigue en Playlists; el plugin ya no la mantiene."),
    "noScene": ("Die Szene ist auf diesem Rahmen nicht installiert. Installiere das Paket noch einmal.",
                "The scene is not installed on this frame. Install the pack again.",
                "La escena no está instalada en este marco. Instala el paquete de nuevo."),
    "held": ("Wartet, bis der Bildschirm wieder frei ist.",
             "Waiting until the screen is free again.",
             "Esperando a que la pantalla quede libre."),
    "failed": ("Konnte die Playlist nicht anlegen: {exc}",
               "Could not create the playlist: {exc}",
               "No se pudo crear la lista: {exc}"),
    "notCreated": ("Der Rahmen hat die Playlist {name} nicht angelegt.",
                   "The frame did not create the playlist {name}.",
                   "El marco no creó la lista {name}."),
}


class OwnPlaylist:
    def __init__(self, *, state_file, names, name, description, scene_id, seconds, wanted, set_wanted,
                 engine_call, language, log, held=None, every=30):
        self.state_file = Path(state_file)
        self.names = tuple(names)
        self.name = name
        self.description = description
        self.scene_id = scene_id
        self.seconds = seconds
        self.wanted = wanted
        self.set_wanted = set_wanted
        self.engine_call = engine_call
        self.language = language
        self.log = log
        self.held = held
        self.every = every
        self.note = ""
        self.at = 0.0
        self.lock = threading.Lock()

    # -- Texte und Zustand -------------------------------------------------

    def t(self, key, **values):
        try:
            lang = str(self.language() or "en")
        except Exception:
            lang = "en"
        row = TEXTS[key]
        text = row[LANGS.index(lang)] if lang in LANGS else row[1]
        return text.format(**values) if values else text

    def load(self):
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, data):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self.state_file)

    def playlists(self):
        rows = self.engine_call("GET", "/playlists") or []
        if isinstance(rows, dict):
            rows = rows.get("playlists") or []
        return [p for p in rows if isinstance(p, dict) and p.get("id") is not None]

    # -- Pflege -------------------------------------------------------------

    def maintain(self, force=False):
        """Anlegen, wenn gewünscht; merken, wenn sie gelöscht wurde. Höchstens
        alle `every` Sekunden, außer mit force."""
        with self.lock:
            if not force and time.time() - self.at < self.every:
                return
            self.at = time.time()
            try:
                self._maintain()
            except Exception as exc:  # Engine nicht erreichbar o. ä.
                self.note = self.t("failed", exc=exc)
                self.log(f"Playlist: {exc}", "warning")

    def _maintain(self):
        state = self.load()
        rows = self.playlists()
        by_name = next((p for p in rows if p.get("name") in self.names), None)
        if not state.get("adopted"):
            # Einmalig: eine früher per Knopf angelegte Playlist übernehmen.
            state["adopted"] = True
            if by_name is not None and not state.get("id"):
                state.update(id=by_name["id"], name=by_name.get("name"))
                self.set_wanted(True)
                self.log(f"Playlist {by_name.get('name')} ({by_name['id']}) übernommen.")
            self.save(state)
        wanted = bool(self.wanted())
        if state.get("id"):
            if not any(str(p["id"]) == str(state["id"]) for p in rows):
                state["id"] = None
                state["deleted"] = wanted
                if wanted:
                    self.set_wanted(False)
                    self.log("Die Playlist wurde gelöscht; sie wird nicht neu angelegt.")
                self.save(state)
            self.note = ""
            return
        if not wanted:
            self.note = ""
            return
        if by_name is not None:
            state.update(id=by_name["id"], name=by_name.get("name"), deleted=False)
            self.save(state)
            self.note = ""
            return
        scene = self.scene_id()
        if scene is None:
            self.note = self.t("noScene")
            return
        if self.held is not None and self.held():
            # Takeover-Plugins: nichts anlegen, solange etwas den Bildschirm hält
            # (der Rahmen baut danach den Quick Mix neu).
            self.note = self.t("held")
            return
        name = self.name()
        created = self.engine_call("POST", "/playlists", {"name": name, "description": self.description()}) or {}
        playlist_id = created.get("id") or (created.get("playlist") or {}).get("id")
        if not playlist_id:
            raise RuntimeError(self.t("notCreated", name=name))
        self.engine_call("POST", f"/playlists/{playlist_id}/items",
                         {"dynamicSceneId": scene, "customDurationSeconds": int(self.seconds())})
        state.update(id=playlist_id, name=name, deleted=False)
        self.save(state)
        self.note = ""
        self.log(f"Playlist {name} angelegt ({playlist_id}), eingeschaltet.")

    def changed(self):
        """Die Auswahl wurde auf der Seite geändert."""
        if self.wanted():
            state = self.load()
            if state.get("deleted"):
                state["deleted"] = False
                self.save(state)
        self.maintain(force=True)

    def create_now(self):
        """Für die Aktion „Playlist anlegen“ auf der Plugins-Seite."""
        if not self.wanted():
            self.set_wanted(True)
        self.changed()
        if self.load().get("id"):
            return {"success": True, "message": self.text()}
        return {"success": False, "error": self.note or self.t("pending")}

    def text(self):
        self.maintain()
        state = self.load()
        playlist_id = state.get("id")
        if self.wanted():
            if playlist_id:
                return self.t("created", name=self.name())
            return self.note or self.t("pending")
        if state.get("deleted"):
            return self.t("deleted")
        if playlist_id:
            return self.t("left")
        return ""
