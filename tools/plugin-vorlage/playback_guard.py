"""Restart the owner's slideshow when Dynaframe fails to after a takeover.

A workaround for a Dynaframe Engine bug, not part of this plugin's job, and
written to be deleted: remove this file and the plugin carries on without it
(plugin.py imports it optionally). Nothing else here depends on it.

The bug: when a display session is released while the owner is playing a
Quick Mix, the Engine sometimes restores to the temporary "Selected Media"
playlist it built for the mix. That playlist has been deleted and rebuilt
with a new id in the meantime, so playback ends with no playlist at all and
the last takeover frame stays on screen. Once stopped, every later takeover
snapshots "stopped" and restores "stopped", so it never recovers by itself.
Measured on frame2 2026-09-21 and 2026-09-24; reported to Dynaframe.

What this does, starting a few seconds after a release:
  - asks /slideshow/status whether anything is playing, once a second;
  - if nothing is on two checks in a row, the frame is awake and not paused,
    and no other plugin holds the screen, reads the owner's
    own selection from the Engine's playback_selection_state.json;
  - if that says the owner asked for a Quick Mix to be playing
    (PlaybackRequested), plays that same selection again through
    POST /playlists/play-selection - what the owner would do by hand.

Soon rather than at the end of a fixed wait, because what a stalled frame
shows meanwhile is the last thing the takeover left in the renderer - for a
dynamic scene, its loading poster. At 12 s that read as "the weather's logo
came up and then my photos came back" (frame2, 2026-09-25).

It never picks what to play, never acts while something is playing or while
another plugin holds the screen (/display-sessions/status), and never touches a stop the owner asked for:
stopping from the UI clears PlaybackRequested. Saved playlists used to be
restored correctly by the Engine; on the Kueche frame (2026-11-16, Engine
2026.11.14) they ended stopped too, so a saved playlist the owner asked for is
started again with POST /slideshow/start/<id>.

A second Engine bug, measured on the Kueche frame 2026-11-16 (Engine
2026.11.14): when nothing was playing before a takeover, the Engine restores
"stopped" on release but does not tell the renderer to go idle
(StopSlideshowAsync with notifyRendererIdle: false). The takeover's scene
stays on screen for good while /slideshow/status says nothing is playing.
So when the owner did not ask for anything to play and the renderer still
shows something, this sends POST /slideshow/stop - the same as pressing Stop:
the frame shows its usual "No playlist is playing" screen again.

Self-contained on purpose so other plugins can copy it unchanged; the only
dependency is requests. Master copy: tools/plugin-vorlage/playback_guard.py.
"""

import json
import os
import threading
import time
from pathlib import Path

import requests

# The Engine keeps its state in the service user's data folder; plugins run as
# that same user, so the file is readable.
DATA_DIR = Path(os.environ.get("DFR_DATA_DIR",
                               Path.home() / ".local" / "share" / "dfr"))
SELECTION_FILE = DATA_DIR / "playback_selection_state.json"

# The Engine restores within about a second when it works (measured on
# frame2: photo back one second after the release). The first look is at 3 s,
# then once a second; two stopped answers in a row are needed, so a restore
# that is merely slow is not trampled. 12 s is how long it keeps looking.
FIRST_CHECK_SECONDS = 3
POLL_SECONDS = 1
STOPPED_CHECKS = 2
DEFAULT_WAIT_SECONDS = 12

# The renderer only listens on the frame itself. /debug/runtime says whether
# it still shows something (hasMedia); when it cannot be asked, the guard
# assumes it does, because the Engine already reported "stopped".
RENDERER_URL = os.environ.get("DFR_RENDERER_URL", "http://127.0.0.1:8080")

_pending = threading.Lock()


def _someone_has_the_screen(base, hdrs):
    """True while a display session is held - another plugin's takeover.

    Asked because the slideshow status alone cannot tell "stopped" from
    "another plugin is just taking over". An Engine without the endpoint
    answers as if nobody does, which is how this guard behaved before.
    """
    try:
        answer = requests.get(base + "/display-sessions/status", headers=hdrs,
                              timeout=(3, 10))
        return answer.status_code == 200 and bool(answer.json().get("active"))
    except (requests.RequestException, ValueError, AttributeError):
        return False


def renderer_shows_something(renderer_url=None):
    """False only when the renderer says it shows nothing."""
    try:
        answer = requests.get(str(renderer_url or RENDERER_URL).rstrip("/") + "/debug/runtime",
                              timeout=(2, 5))
        if answer.status_code != 200:
            return True
        return bool(answer.json().get("hasMedia", True))
    except (requests.RequestException, ValueError, AttributeError):
        return True


def show_idle_screen(base, hdrs, log, renderer_url=None):
    """Clear a takeover picture the Engine left behind. True if it did."""
    if not renderer_shows_something(renderer_url):
        return False
    try:
        answer = requests.post(base + "/slideshow/stop", headers=hdrs, timeout=(3, 15))
    except requests.RequestException as exc:
        log(f"Playback guard: could not clear the screen after the takeover: {exc}",
            level="warning")
        return False
    if answer.status_code >= 400:
        log(f"Playback guard: the Engine refused to clear the screen after the takeover "
            f"(HTTP {answer.status_code}).", level="warning")
        return False
    log("Playback guard: nothing was playing before the takeover, and Dynaframe left "
        "the takeover's last picture on screen, so the frame was sent back to its "
        "idle screen.")
    return True


def _restart_saved_playlist(base, hdrs, log, playlist_id):
    """Start the owner's saved playlist again, as the owner would by hand."""
    try:
        response = requests.post(f"{base}/slideshow/start/{int(playlist_id)}", headers=hdrs,
                                 timeout=(3, 30))
        result = response.json() if response.content else {}
    except (requests.RequestException, ValueError, TypeError) as exc:
        log(f"Playback guard: could not restart the saved playlist: {exc}", level="warning")
        return "failed"
    if response.status_code >= 400 or not result.get("success", False):
        log(f"Playback guard: the Engine refused to restart the saved playlist "
            f"(HTTP {response.status_code}): {str(result)[:200]}", level="warning")
        return "failed"
    log(f"Playback guard: Dynaframe did not resume the saved playlist {playlist_id} after "
        "the display was handed back, so it was restarted.", level="warning")
    return "restarted"


def read_selection(path=None):
    """The owner's last selection as the Engine saved it, or None."""
    try:
        with open(path or SELECTION_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def restore_if_stalled(engine_url, headers=None, log=None,
                       wait_seconds=DEFAULT_WAIT_SECONDS, stop_event=None,
                       selection_path=None, first_check_seconds=FIRST_CHECK_SECONDS,
                       poll_seconds=POLL_SECONDS):
    """Watch the seconds after a release, and replay the owner's mix if needed.

    Returns one word saying what happened, for the caller to log or show:
      "playing"       - the Engine resumed, or another plugin has the screen
      "not-requested" - nothing is playing, and the owner did not ask for it;
                        a picture left on screen was cleared
      "skipped"       - asleep, paused, not a Quick Mix, or a check is
                        already waiting
      "restarted"     - this put the owner's Quick Mix back on
      "failed"        - it needed restarting and the Engine refused
    Blocks for up to wait_seconds; call it from a thread.
    """
    log = log or (lambda message, level="info": None)
    if not _pending.acquire(blocking=False):
        return "skipped"  # a release a moment ago is already being checked
    try:
        wait = stop_event.wait if stop_event is not None else threading.Event().wait
        if wait(min(first_check_seconds, wait_seconds)):
            return "skipped"
        deadline = time.monotonic() + max(0, wait_seconds - first_check_seconds)

        base = str(engine_url).rstrip("/")
        hdrs = headers() if callable(headers) else (headers or {})
        stopped_in_a_row = 0
        while True:
            try:
                status = requests.get(base + "/slideshow/status", headers=hdrs,
                                      timeout=(3, 10)).json()
            except (requests.RequestException, ValueError) as exc:
                log(f"Playback guard: could not read the slideshow status: {exc}",
                    level="warning")
                return "skipped"
            if (status.get("playNow") or {}).get("isActive"):
                return "playing"  # Play Now has the screen; it hands back itself
            if status.get("isRunning"):
                stopped_in_a_row = 0
            elif status.get("isPaused") or status.get("isSleeping") or \
                    str(status.get("sleepState") or "Awake") != "Awake":
                return "skipped"
            elif _someone_has_the_screen(base, hdrs):
                return "playing"  # theirs to hand back, and the Engine's to restore
            else:
                stopped_in_a_row += 1
                if stopped_in_a_row >= STOPPED_CHECKS:
                    break
            if stopped_in_a_row == 0 and time.monotonic() >= deadline:
                return "playing"
            if wait(poll_seconds):
                return "skipped"

        selection = read_selection(selection_path)
        if not selection or not selection.get("PlaybackRequested"):
            show_idle_screen(base, hdrs, log)
            return "not-requested"
        mix = selection.get("QuickMixState")
        if selection.get("Mode") == "saved_playlist" and selection.get("SavedPlaylistId"):
            return _restart_saved_playlist(base, hdrs, log, selection["SavedPlaylistId"])
        if selection.get("Mode") != "quick_mix" or not isinstance(mix, dict):
            return "skipped"

        body = {"quickMixState": {
            "SelectedFolders": list(mix.get("SelectedFolders") or []),
            "SelectedPlugins": list(mix.get("SelectedPlugins") or []),
            "EnabledSavedPlaylistIds": list(mix.get("EnabledSavedPlaylistIds") or []),
        }}
        try:
            response = requests.post(base + "/playlists/play-selection",
                                     json=body, headers=hdrs, timeout=(3, 30))
            result = response.json() if response.content else {}
        except (requests.RequestException, ValueError) as exc:
            log(f"Playback guard: could not restart the Quick Mix: {exc}",
                level="warning")
            return "failed"
        if response.status_code >= 400 or not result.get("success", False):
            log(f"Playback guard: the Engine refused to restart the Quick Mix "
                f"(HTTP {response.status_code}): {str(result)[:200]}",
                level="warning")
            return "failed"
        log("Playback guard: Dynaframe did not resume the Quick Mix after the "
            "display was handed back, so it was restarted "
            f"(playlists {body['quickMixState']['EnabledSavedPlaylistIds']}, "
            f"{result.get('itemCount', '?')} items).", level="warning")
        return "restarted"
    finally:
        _pending.release()
