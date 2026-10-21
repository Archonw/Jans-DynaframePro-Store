"""Jellyfin für Dynaframe's Magic Mirror: was gerade läuft.

Fragt /Sessions des Jellyfin-Servers mit einem API-Schlüssel ab (wie das
Plugin Jellyfin Now Playing) und sucht die passende Wiedergabe: Musik, Filme,
Serienfolgen oder Live-TV. Das Modul holt nur, solange die Szene läuft, dann
alle 10 Sekunden; dazwischen läuft der Fortschrittsbalken in module.js weiter.
Die Bilder lädt die Szene direkt vom Server (Jellyfin liefert sie ohne Anmeldung).
"""

import time
from urllib.parse import urlencode, urlparse

TICKS = 10_000_000   # Jellyfin rechnet in 100-ns-Schritten
VIDEO = ("Movie", "Episode", "Video", "MusicVideo", "TvChannel", "Trailer")


def server_url(config):
    server = str(config.get("server") or "").strip().rstrip("/")
    if not server:
        return ""
    if "://" not in server:
        server = "http://" + server
    parts = urlparse(server)
    if parts.port is None and parts.scheme == "http" and not parts.path.strip("/"):
        server += ":8096"   # Standard-Port von Jellyfin
    return server


def headers(key):
    return {"Authorization": f'MediaBrowser Client="Dynaframe Magic Mirror", Device="Dynaframe", '
                             f'DeviceId="dynaframe-magic-mirror", Version="1.0.0", Token="{key}"',
            "X-Emby-Token": key, "Accept": "application/json"}


def wanted(item, media):
    kind = item.get("Type")
    if media == "music":
        return kind == "Audio" or item.get("MediaType") == "Audio"
    if media == "video":
        return kind in VIDEO or item.get("MediaType") == "Video"
    return True


def pick_session(sessions, user, media):
    user = str(user or "").strip().lower()
    found = []
    for s in sessions or []:
        item = s.get("NowPlayingItem")
        if not item or (user and str(s.get("UserName") or "").lower() != user):
            continue
        if not wanted(item, media):
            continue
        found.append(s)
    # erst was spielt, dann was pausiert; jeweils die zuletzt aktive Sitzung
    found.sort(key=lambda s: (not (s.get("PlayState") or {}).get("IsPaused"), str(s.get("LastActivityDate") or "")),
               reverse=True)
    return found[0] if found else None


def describe(item):
    """Titel, zweite Zeile (Interpret, Serie, Jahr), dritte (Album, Staffel) und Art."""
    kind = item.get("Type")
    name = item.get("Name") or ""
    if kind == "Audio":
        artists = item.get("Artists") or [a.get("Name") for a in item.get("ArtistItems") or [] if a.get("Name")]
        artist = ", ".join(a for a in artists if a) or item.get("AlbumArtist") or ""
        return name, artist, item.get("Album") or "", "music"
    if kind == "Episode":
        season, number = item.get("ParentIndexNumber"), item.get("IndexNumber")
        code = f"S{season:02d}E{number:02d}" if isinstance(season, int) and isinstance(number, int) else ""
        return name, item.get("SeriesName") or "", code or item.get("SeasonName") or "", "episode"
    if kind == "TvChannel":
        program = (item.get("CurrentProgram") or {}).get("Name") or ""
        return program or name, name if program else "", "", "tv"
    year = item.get("ProductionYear")
    extra = str(year) if year else ""
    if kind == "Movie":
        return name, extra, "", "movie"
    return name, extra, "", "video"


def image(item, server, episode_image, size):
    """URL des Bildes und seine Form (square, poster, wide)."""
    kind = item.get("Type")
    tags = item.get("ImageTags") or {}
    candidates = []
    if kind == "Audio":
        candidates += [(item.get("AlbumId"), item.get("AlbumPrimaryImageTag"), "square"),
                       (item.get("Id"), tags.get("Primary"), "square")]
    elif kind == "Episode":
        own = (item.get("Id"), tags.get("Primary"), "wide")
        series = (item.get("SeriesId"), item.get("SeriesPrimaryImageTag"), "poster")
        candidates += [own, series] if episode_image == "episode" else [series, own]
    elif kind == "TvChannel":
        candidates.append((item.get("Id"), tags.get("Primary"), "wide"))
    else:
        ratio = item.get("PrimaryImageAspectRatio") or (0.67 if kind == "Movie" else 1.78)
        shape = "poster" if ratio < 0.9 else "square" if ratio < 1.2 else "wide"
        candidates.append((item.get("Id"), tags.get("Primary"), shape))
    for item_id, tag, shape in candidates:
        if item_id and tag:
            query = urlencode({"tag": tag, "maxHeight": size, "quality": 90})
            return f"{server}/Items/{item_id}/Images/Primary?{query}", shape
    return "", ""


def next_item(session, server, key, get):
    """Das nächste Stück in der Warteschlange (nur Titel und Interpret)."""
    queue = session.get("NowPlayingQueue") or []
    current = session.get("PlaylistItemId")
    ids = [q.get("Id") for q in queue]
    at = next((i for i, q in enumerate(queue) if current and q.get("PlaylistItemId") == current), None)
    if at is None:
        item_id = (session.get("NowPlayingItem") or {}).get("Id")
        at = ids.index(item_id) if item_id in ids else None
    if at is None or at + 1 >= len(ids) or not ids[at + 1]:
        return None
    try:
        found = get(f"{server}/Items", params={"Ids": ids[at + 1], "Fields": "ProductionYear"}, headers=headers(key))
    except Exception:   # "Als Nächstes" ist nur Beiwerk
        return None
    rows = (found or {}).get("Items") or []
    if not rows:
        return None
    title, line2, _, _ = describe(rows[0])
    return {"title": title, "artist": line2}


def fetch(config, ctx):
    SourceError, get = ctx["SourceError"], ctx["get"]
    server, key = server_url(config), str(config.get("apikey") or "").strip()
    if not server or not key:
        raise SourceError("no-key")
    sessions = get(f"{server}/Sessions", params={"activeWithinSeconds": 960}, headers=headers(key))
    if not isinstance(sessions, list):
        raise SourceError("format", "keine Liste von Sitzungen")
    users = sorted({str(s.get("UserName") or "") for s in sessions} - {""})[:30]
    session = pick_session(sessions, config.get("user"), config.get("media") or "all")
    if not session:
        return {"state": "idle", "users": users}
    item = session["NowPlayingItem"]
    play = session.get("PlayState") or {}
    title, line2, line3, kind = describe(item)
    size = 600 if config.get("layout") == "background" or config.get("cover") == "large" else 360
    url, shape = image(item, server, config.get("episodeImage"), size)
    live = kind == "tv" or not item.get("RunTimeTicks")
    out = {
        "state": "paused" if play.get("IsPaused") else "playing",
        "kind": kind,
        "title": title, "line2": line2, "line3": line3,
        "user": session.get("UserName") or "",
        "device": session.get("DeviceName") or session.get("Client") or "",
        "duration": 0 if live else (item.get("RunTimeTicks") or 0) / TICKS,
        "elapsed": (play.get("PositionTicks") or 0) / TICKS,
        "elapsedAt": time.time(),
        "image": url, "shape": shape,
        "next": None,
        "users": users,
    }
    if config.get("showNext", True):
        out["next"] = next_item(session, server, key, get)
    return out
