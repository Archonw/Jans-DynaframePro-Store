#!/usr/bin/env python3
"""
WebPageButtonPlugin for Dynaframe Pro.

A GPIO button shows web pages on top of the slideshow:
- Short press, browser closed: opens the first configured page (first address in Urls) full screen
  (kiosk window).
- Short press, browser open: switches to the next page. After the last page it starts again with
  the first one, or closes the browser if CloseAfterLastPage is enabled.
- Long press (LongPressSeconds, default 2 s): closes the browser, the slideshow is visible again.
- Optional automatic switching (off by default): only when the option AutoSwitch is active, the
  next page is shown automatically after AutoSwitchSeconds. Pressing the button switches
  immediately and restarts the timer. With the option off, pages change only with the button.

With only one configured page, a short press toggles it (open / close); the timer leaves it alone.

The pages are shown by a separate browser process (Chromium or Firefox), so the plugin does not
depend on the DynaFrame engine API. With Chromium every page gets its own tab and the plugin
switches between the tabs through the local DevTools HTTP interface (127.0.0.1 only), so a switch
is instant and the pages keep running in the background. A tab is created the first time its page
is shown. If switching tabs fails, or UseTabs is off, the browser is restarted for every switch.

Fresh pages without waiting (PreloadNext, on by default): while you look at a page, a background
thread prepares the page that comes next in a background tab. A page that was loaded more than
PreloadMaxAgeSeconds ago is reloaded in the background (through the DevTools WebSocket). When you
switch, the finished page appears instantly. Video pages are not prepared, because they would start
playing in the background. If preparing fails, switching still works as before.
Closing the window (instead of minimizing it) works the same on X11 and Wayland.

YouTube links (watch, youtu.be, shorts, live, playlist) are shown as an embedded player that fills
the whole screen and starts playing automatically. YouTube refuses to play an embedded player that
is opened without a referrer (error 153), so the plugin serves a tiny page on http://localhost
(127.0.0.1 only) that contains the player in an iframe. Videos stop when you switch to another page
(their tab is closed, so they do not keep playing in the background). Can be switched off with
YouTubeFullscreen.
"""

import os
import sys
import traceback
from datetime import datetime

# lgpio (the gpiozero backend on the Pi 5) creates a notify pipe file in the current
# working directory. Switch to a directory that is guaranteed to be writable first.
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
            f.write(f"sys.executable={sys.executable}\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _write_crash_log

import atexit
import base64
import glob
import html
import http.server
import json
import re
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from gpiozero import Button

sys.path.insert(0, str(Path(__file__).parent.parent))
from dynaframe_plugin_base import create_plugin

plugin = create_plugin()

import support_page

_PROFILE_DIR = os.path.join(_plugin_dir, "browser-profile")
_BROWSER_LOG = os.path.join(_plugin_dir, "browser.log")
_DEBOUNCE_SECONDS = 0.4
_PRELOAD_TICK = 2.0       # how often the background thread checks if the next page needs loading
_AUTO_TICK = 0.5          # how often the timer thread checks if the next page is due
_MIN_AUTO_SECONDS = 5.0  # shortest allowed AutoSwitchSeconds
_WRAPPER_PORT = 9334   # local page that embeds YouTube players (127.0.0.1 only)
_DEBUG_PORT = 9333   # Chromium DevTools port (127.0.0.1 only), used to switch tabs

_lock = threading.Lock()
_shutdown_event = threading.Event()
_proc = None
_index = -1          # index of the page that is currently shown (-1 = none)
_last_press = 0.0
_tabs = {}            # page index -> DevTools target id of its tab
_tabs_ready = False   # True once the tab the browser was started with is known
_wrapper_base = None  # e.g. http://localhost:9334 once the local page server is running
_loaded_at = {}       # page index -> time.monotonic() when its tab was last loaded
_preload_cfg = {"enabled": False, "max_age": 180.0, "tabs": True, "close_after_last": False}
_preload_blocked = False       # True if the tabs of this browser session cannot be prepared
_preload_pause_until = 0.0     # no preparing before this time (after an error)
_preload_error_logged = False
_first_index = 0     # page index of the tab the browser was started with
_session_urls = None # list of pages the current browser session was started with
_next_auto = None    # time.monotonic() value at which the next page is shown automatically
_long_pressed = False


# --------------------------------------------------------------------------
# GPIO chip detection (the chip number differs between kernels, e.g. gpiochip0,
# gpiochip4 or gpiochip15, but gpiozero only tries 4 and 0)
# --------------------------------------------------------------------------
def _find_gpio_pin_factory():
    try:
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
            plugin.log(f"GPIO chip found: gpiochip{chip} ({info[3]}).")
            return factory
    return None


# --------------------------------------------------------------------------
# Browser handling
# --------------------------------------------------------------------------
def normalize_url(raw):
    url = str(raw or "").strip()
    if not url:
        return ""
    if "://" not in url:
        # Accept "host", "host/path" and "host:port/path", reject "scheme:payload" such as javascript:...
        head = url.split("/", 1)[0]
        if ":" in head and not re.fullmatch(r"[^:]+:\d+", head):
            return ""
        url = "https://" + url
    if urlparse(url).scheme not in ("http", "https", "file"):
        return ""
    return url


_YT_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{6,20}")
_YT_LIST_ID = re.compile(r"[A-Za-z0-9_-]{6,64}")
_YT_EMBED_PREFIX = "https://www.youtube.com/embed/"


def _youtube_start_seconds(value):
    value = str(value or "").strip().lower()
    if value.isdigit():
        return int(value)
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", value)
    if match and any(match.groups()):
        hours, minutes, seconds = (int(g or 0) for g in match.groups())
        return hours * 3600 + minutes * 60 + seconds
    return 0


def youtube_to_embed(url):
    """Return the embedded player URL for a YouTube link, or None if it is not one."""
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    query = urllib.parse.parse_qs(parts.query)
    segments = [x for x in parts.path.split("/") if x]
    video = ""
    if host == "youtu.be":
        video = segments[0] if segments else ""
    elif host == "youtube.com" and segments:
        if segments[0] == "watch":
            video = (query.get("v") or [""])[0]
        elif segments[0] in ("shorts", "live", "v") and len(segments) > 1:
            video = segments[1]
        elif segments[0] != "playlist":
            return None
    else:
        return None
    playlist = (query.get("list") or [""])[0]
    if video and not _YT_VIDEO_ID.fullmatch(video):
        return None
    if playlist and not _YT_LIST_ID.fullmatch(playlist):
        playlist = ""
    if not video and not playlist:
        return None
    params = {"autoplay": "1", "controls": "0", "rel": "0", "modestbranding": "1",
              "playsinline": "1", "iv_load_policy": "3"}
    start = _youtube_start_seconds((query.get("t") or query.get("start") or [""])[0])
    if start:
        params["start"] = str(start)
    if playlist:
        params["list"] = playlist
    base = _YT_EMBED_PREFIX + (video if video else "videoseries")
    return base + "?" + urllib.parse.urlencode(params)


def youtube_page_url(url):
    """Address to open for a YouTube link: the local wrapper page (or the plain player if it is not running)."""
    embed = youtube_to_embed(url)
    if not embed:
        return None
    if _wrapper_base:
        return f"{_wrapper_base}/yt?src={urllib.parse.quote(embed, safe='')}"
    return embed


def is_video_page(url):
    url = str(url)
    if url.startswith(_YT_EMBED_PREFIX):
        return True
    parts = urlparse(url)
    return parts.hostname == "localhost" and parts.path == "/yt"


_WRAPPER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="referrer" content="strict-origin-when-cross-origin">
<title>YouTube</title>
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}iframe{border:0;width:100%;height:100%}</style>
</head><body><iframe src="{src}" allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></body></html>"""


class _WrapperHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        src = (urllib.parse.parse_qs(parsed.query).get("src") or [""])[0]
        if parsed.path != "/yt" or not src.startswith(_YT_EMBED_PREFIX):
            self.send_error(404)
            return
        body = _WRAPPER_HTML.replace("{src}", html.escape(src, quote=True)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_wrapper_server():
    """Serve the wrapper page on 127.0.0.1 so that YouTube players get a valid referrer."""
    global _wrapper_base
    server = None
    for port in (_WRAPPER_PORT, 0):
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _WrapperHandler)
            break
        except OSError:
            server = None
    if server is None:
        plugin.log("Could not start the local page for YouTube players; YouTube may show error 153.", level="error")
        return
    threading.Thread(target=server.serve_forever, name="youtube-wrapper", daemon=True).start()
    _wrapper_base = f"http://localhost:{server.server_address[1]}"


def _display_server():
    value = str(plugin.get_setting("DisplayServer", "wayland") or "wayland").strip().lower()
    return value if value in ("auto", "wayland", "x11") else "wayland"


def build_env():
    env = os.environ.copy()
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if os.path.isdir(runtime):
        env["XDG_RUNTIME_DIR"] = runtime

    server = _display_server()
    wayland_socket = os.path.join(runtime, env.get("WAYLAND_DISPLAY") or "wayland-0")

    if server == "x11":
        env.pop("WAYLAND_DISPLAY", None)
        env["DISPLAY"] = env.get("DISPLAY") or ":0"
    elif server == "wayland":
        env["WAYLAND_DISPLAY"] = "wayland-0"
    else:
        if not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
            if os.path.exists(wayland_socket):
                env["WAYLAND_DISPLAY"] = "wayland-0"
            else:
                env["DISPLAY"] = ":0"

    xauth = os.path.expanduser("~/.Xauthority")
    if not env.get("XAUTHORITY") and os.path.exists(xauth):
        env["XAUTHORITY"] = xauth
    return env


def find_browser():
    override = str(plugin.get_setting("BrowserCommand", "") or "").strip()
    if override:
        parts = shlex.split(override)
        if parts and shutil.which(parts[0]):
            return [shutil.which(parts[0])] + parts[1:]
        plugin.log(f"BrowserCommand '{override}' was not found.", level="error")
        return None
    for name in ("chromium", "chromium-browser", "google-chrome", "firefox"):
        path = shutil.which(name)
        if path:
            return [path]
    plugin.log("No supported browser found (chromium, chromium-browser, google-chrome, firefox).", level="error")
    return None


def build_command(url, remote_debugging=False):
    base = find_browser()
    if not base:
        return None
    os.makedirs(_PROFILE_DIR, exist_ok=True)
    name = os.path.basename(base[0]).lower()
    extra = shlex.split(str(plugin.get_setting("ExtraBrowserArgs", "") or ""))

    if "firefox" in name:
        return base + ["--kiosk", "--no-remote", "--profile", _PROFILE_DIR] + extra + [url]

    # Same flags as the manually tested command
    #   WAYLAND_DISPLAY=wayland-0 chromium --ozone-platform=wayland --kiosk \
    #       --noerrdialogs --password-store=basic <url>
    # plus a dedicated profile (so the plugin controls its own browser instance instead of
    # handing the URL to an already running Chromium), --no-first-run for that fresh profile
    # and --disable-session-crashed-bubble because closing the window ends the process.
    args = []
    if remote_debugging:
        args.append(f"--remote-debugging-port={_DEBUG_PORT}")
    server = _display_server()
    if server in ("wayland", "x11"):
        args.append(f"--ozone-platform={server}")
    args += [
        "--kiosk",
        "--noerrdialogs",
        "--password-store=basic",
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run",
        "--disable-session-crashed-bubble",
        f"--user-data-dir={_PROFILE_DIR}",
    ]
    return base + args + extra + [url]


def _clear_stale_locks():
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lock", ".parentlock"):
        try:
            os.remove(os.path.join(_PROFILE_DIR, name))
        except OSError:
            pass


def _kill_leftovers():
    """Stop browser processes of this plugin that survived an earlier run."""
    try:
        subprocess.run(["pkill", "-f", "--", _PROFILE_DIR], timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def is_open():
    return _proc is not None and _proc.poll() is None


def get_urls():
    """Pages from the Urls setting, separated by spaces, semicolons or line breaks."""
    raw = str(plugin.get_setting("Urls", "") or "").strip()
    if not raw:
        raw = str(plugin.get_setting("Url", "") or "").strip()  # setting name of version 0.1
    youtube_fullscreen = str(plugin.get_setting("YouTubeFullscreen", True)).lower() == "true"
    urls = []
    for part in re.split(r"[\s;]+", raw):
        if not part:
            continue
        url = normalize_url(part)
        if url:
            if youtube_fullscreen:
                url = youtube_page_url(url) or url
            urls.append(url)
        else:
            plugin.log(f"Ignoring invalid address: {part}", level="error")
    return urls


def open_page(url):
    global _proc
    cmd = build_command(url, remote_debugging=_use_tabs())
    if not cmd:
        return False
    _kill_leftovers()
    _clear_stale_locks()
    try:
        with open(_BROWSER_LOG, "w") as log_file:
            _proc = subprocess.Popen(
                cmd,
                env=build_env(),
                cwd=_plugin_dir,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except Exception as exc:
        _proc = None
        plugin.log(f"Could not start the browser: {exc}", level="error")
        return False
    plugin.log(f"Opened {url} (pid {_proc.pid}).")
    try:
        plugin.report_activity("Web page opened", url)
    except Exception:
        pass
    return True


def close_page(quiet=False):
    global _proc, _index, _session_urls, _next_auto, _tabs_ready, _preload_blocked, _preload_pause_until
    proc, _proc = _proc, None
    _index = -1
    _tabs.clear()
    _loaded_at.clear()
    _tabs_ready = False
    _preload_blocked = False
    _preload_pause_until = 0.0
    _session_urls = None
    _next_auto = None
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
    if not quiet:
        plugin.log("Web page closed.")
        try:
            plugin.report_activity("Web page closed", "")
        except Exception:
            pass


def _auto_seconds():
    """Display time per page in seconds, or 0 if automatic switching is not activated."""
    if str(plugin.get_setting("AutoSwitch", False)).lower() != "true":
        return 0.0
    try:
        value = float(plugin.get_setting("AutoSwitchSeconds", 30) or 0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if value <= 0 else max(_MIN_AUTO_SECONDS, value)


def _schedule_auto():
    """(Re)start the timer for the page that is shown now; does nothing if auto switching is off."""
    global _next_auto
    seconds = _auto_seconds()
    _next_auto = time.monotonic() + seconds if seconds > 0 else None


def _use_tabs():
    return str(plugin.get_setting("UseTabs", True)).lower() == "true"


def _devtools(path, method="GET", timeout=3):
    request = urllib.request.Request(f"http://127.0.0.1:{_DEBUG_PORT}{path}", method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    stripped = body.lstrip()
    return json.loads(body) if stripped[:1] in ("{", "[") else body


def _ws_frame(payload):
    """One masked WebSocket text frame (clients must mask)."""
    mask = os.urandom(4)
    length = len(payload)
    if length < 126:
        header = bytes([0x81, 0x80 | length])
    elif length < 65536:
        header = bytes([0x81, 0x80 | 126]) + struct.pack(">H", length)
    else:
        header = bytes([0x81, 0x80 | 127]) + struct.pack(">Q", length)
    return header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def _ws_read_exact(sock, buffer, count):
    while len(buffer) < count:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("connection closed")
        buffer.extend(chunk)
    data = bytes(buffer[:count])
    del buffer[:count]
    return data


def _ws_read_message(sock, buffer):
    message = b""
    while True:
        first, second = _ws_read_exact(sock, buffer, 2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", _ws_read_exact(sock, buffer, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _ws_read_exact(sock, buffer, 8))[0]
        mask = _ws_read_exact(sock, buffer, 4) if second & 0x80 else None
        payload = _ws_read_exact(sock, buffer, length)
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if opcode == 8:
            raise ConnectionError("closed by the browser")
        if opcode in (9, 10):
            continue
        message += payload
        if first & 0x80:
            return message


def _cdp(ws_url, method, params=None, timeout=5):
    """Run one Chrome DevTools Protocol command over a short-lived WebSocket (standard library only)."""
    parts = urlparse(ws_url)
    sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buffer = bytearray()
        while b"\r\n\r\n" not in buffer:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("handshake failed")
            buffer.extend(chunk)
        head, _, rest = bytes(buffer).partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError("the browser refused the WebSocket connection")
        buffer = bytearray(rest)
        sock.sendall(_ws_frame(json.dumps({"id": 1, "method": method, "params": params or {}}).encode()))
        while True:
            reply = json.loads(_ws_read_message(sock, buffer))
            if reply.get("id") == 1:
                if "error" in reply:
                    raise RuntimeError(reply["error"].get("message", reply["error"]))
                return reply.get("result", {})
    finally:
        sock.close()


def _map_first_tab():
    """Find the tab the browser was started with. False if the session has more than one tab."""
    global _tabs_ready
    pages = [t for t in _devtools("/json/list") if t.get("type") == "page"]
    if len(pages) != 1:
        return False
    _tabs[_first_index] = pages[0]["id"]
    _tabs_ready = True
    return True


def _devtools_switch(urls, index):
    """Show urls[index] in its own tab. Returns False if the browser has to be restarted instead."""
    try:
        if not _tabs_ready and not _map_first_tab():
            return False
        if index in _tabs:
            try:
                _devtools(f"/json/activate/{_tabs[index]}")
                return True
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                _tabs.pop(index, None)  # the tab was closed in the meantime: create it again
        target = _devtools("/json/new?" + urllib.parse.quote(urls[index], safe=""), method="PUT")
        _tabs[index] = target["id"]
        _loaded_at[index] = time.monotonic()
        return True
    except Exception as exc:
        plugin.log(f"Switching tabs failed ({exc}); restarting the browser instead.", level="error")
        return False


def _close_video_tab(urls, index):
    """A video keeps playing (with sound) in a background tab, so the tab of a video is closed when left."""
    if index < 0 or index >= len(urls) or index not in _tabs or not is_video_page(urls[index]):
        return
    try:
        _devtools(f"/json/close/{_tabs[index]}")
    except Exception as exc:
        plugin.log(f"Could not close the tab of page {index + 1}: {exc}", level="error")
    _tabs.pop(index, None)
    _loaded_at.pop(index, None)


def show_page(urls, index):
    """Start a fresh browser showing urls[index]; an open browser window is closed first."""
    global _index, _first_index, _session_urls, _tabs_ready, _preload_blocked
    if is_open():
        close_page(quiet=True)
    if open_page(urls[index]):
        _index = index
        _first_index = index
        _session_urls = list(urls)
        _tabs.clear()
        _loaded_at.clear()
        _loaded_at[index] = time.monotonic()
        _tabs_ready = False
        _preload_blocked = False
        plugin.log(f"Showing page {index + 1} of {len(urls)}.")
        _refresh_preload_cfg()
        _schedule_auto()
    else:
        _index = -1


def switch_to(urls, index):
    """Switch to urls[index]: through tabs if possible, otherwise by restarting the browser."""
    global _index
    previous = _index
    if is_open() and _use_tabs() and _session_urls == list(urls) and _devtools_switch(urls, index):
        if previous != index:
            _close_video_tab(urls, previous)
        _index = index
        plugin.log(f"Switched to page {index + 1} of {len(urls)} (tab).")
        _refresh_preload_cfg()
        _schedule_auto()
        return
    show_page(urls, index)


def _refresh_preload_cfg():
    """Read the preload settings (done whenever a page is shown, so the timer thread needs no settings access)."""
    global _preload_cfg
    try:
        max_age = max(0.0, float(plugin.get_setting("PreloadMaxAgeSeconds", 180)))
    except (TypeError, ValueError):
        max_age = 180.0
    _preload_cfg = {
        "enabled": str(plugin.get_setting("PreloadNext", True)).lower() == "true",
        "max_age": max_age,
        "tabs": _use_tabs(),
        "close_after_last": str(plugin.get_setting("CloseAfterLastPage", False)).lower() == "true",
    }


def _preload_tick():
    """Prepare the page that a switch would show next: load it in a background tab or reload an old one."""
    global _preload_blocked, _preload_pause_until, _preload_error_logged
    with _lock:
        cfg = _preload_cfg
        urls = _session_urls
        if (not cfg["enabled"] or not cfg["tabs"] or _preload_blocked or urls is None or not is_open()
                or _index < 0 or len(urls) < 2 or time.monotonic() < _preload_pause_until):
            return
        session = _proc
        try:
            if not _tabs_ready and not _map_first_tab():
                _preload_blocked = True  # the session has more than one tab: leave it alone
                return
        except Exception:
            return  # DevTools is not ready yet, try again at the next tick
        nxt = _index + 1
        if nxt >= len(urls):
            if cfg["close_after_last"]:
                return
            nxt = 0
        if nxt == _index or is_video_page(urls[nxt]):
            return
        tab_id = _tabs.get(nxt)
        if tab_id is not None and time.monotonic() - _loaded_at.get(nxt, 0.0) <= cfg["max_age"]:
            return
        url = urls[nxt]

    try:  # network calls without holding the lock, so button presses are never delayed
        if tab_id is None:
            browser_ws = _devtools("/json/version")["webSocketDebuggerUrl"]
            new_id = _cdp(browser_ws, "Target.createTarget", {"url": url, "background": True})["targetId"]
        else:
            _cdp(f"ws://127.0.0.1:{_DEBUG_PORT}/devtools/page/{tab_id}", "Page.reload", {"ignoreCache": True})
            new_id = tab_id
    except Exception as exc:
        with _lock:
            _preload_pause_until = time.monotonic() + 30
            if tab_id is not None and _tabs.get(nxt) == tab_id:
                _tabs.pop(nxt, None)  # the tab is gone; it will be created again
            if not _preload_error_logged:
                _preload_error_logged = True
                plugin.log(f"Preparing the next page in the background failed ({exc}); switching still works.",
                           level="error")
        return

    with _lock:
        if _proc is not session or _session_urls is not urls:
            return  # the browser was restarted or closed in the meantime
        if tab_id is None:
            if nxt in _tabs:  # a switch created the tab in the meantime: drop the duplicate
                try:
                    _devtools(f"/json/close/{new_id}")
                except Exception:
                    pass
            else:
                _tabs[nxt] = new_id
        _loaded_at[nxt] = time.monotonic()


def _preload_loop():
    while not _shutdown_event.wait(_PRELOAD_TICK):
        try:
            _preload_tick()
        except Exception as exc:
            plugin.log(f"Background preparation failed: {exc}", level="error")


def _advance(urls, auto):
    """Show the next page, start over, or close the browser after the last page."""
    current = _index if is_open() else -1
    next_index = current + 1
    if next_index >= len(urls):
        close_after_last = str(plugin.get_setting("CloseAfterLastPage", False)).lower() == "true"
        if current >= 0 and (close_after_last or (len(urls) == 1 and not auto)):
            close_page()
            return
        if current >= 0 and len(urls) == 1:
            _schedule_auto()  # automatic switching with a single page: nothing to switch to
            return
        next_index = 0
    switch_to(urls, next_index)


def on_short_press():
    global _last_press
    now = time.monotonic()
    with _lock:
        if now - _last_press < _DEBOUNCE_SECONDS:
            return
        _last_press = now
        try:
            urls = get_urls()
            if not urls:
                plugin.log("The Urls setting contains no valid http(s) address.", level="error")
                return
            _advance(urls, auto=False)
        except Exception as exc:
            plugin.log(f"Short press failed: {exc}", level="error")


def on_auto_advance():
    """Called by the timer thread when the display time of the current page is over."""
    global _next_auto
    with _lock:
        if _next_auto is None or time.monotonic() < _next_auto or not is_open():
            return
        try:
            urls = get_urls()
            if not urls:
                _next_auto = None
                return
            _advance(urls, auto=True)
        except Exception as exc:
            plugin.log(f"Automatic switch failed: {exc}", level="error")
            _next_auto = time.monotonic() + 10


def _auto_loop():
    while not _shutdown_event.wait(_AUTO_TICK):
        due = _next_auto
        if due is not None and time.monotonic() >= due:
            on_auto_advance()


def on_long_press():
    with _lock:
        try:
            if is_open():
                close_page()
        except Exception as exc:
            plugin.log(f"Long press failed: {exc}", level="error")


def on_held():
    global _long_pressed
    _long_pressed = True
    on_long_press()


def on_released():
    global _long_pressed
    if _long_pressed:
        _long_pressed = False
        return
    on_short_press()


def _shutdown(*_args):
    with _lock:
        close_page()
    _shutdown_event.set()


_button = None
_button_key = None
_pin_factory = None
_pin_factory_done = False


def _gpio_pin():
    """BCM pin from the settings, or None while no (valid) pin is entered."""
    raw = str(plugin.get_setting("GpioPin", "") or "").strip()
    try:
        pin = int(float(raw))
    except ValueError:
        return None
    return pin if 0 <= pin <= 27 else None


def _setup_button():
    """Create the button for the configured pin. Never raises; a busy pin is only logged."""
    global _button, _button_key, _pin_factory, _pin_factory_done
    pin = _gpio_pin()
    try:
        long_press = max(0.5, float(plugin.get_setting("LongPressSeconds", 2)))
    except (TypeError, ValueError):
        long_press = 2.0
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
        plugin.log("No GPIO pin set yet. Enter the BCM pin of your button under GpioPin "
                   "in the plugin settings (for example 20).", level="warning")
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
        plugin.log(f"GPIO{pin} cannot be used: {exc}. It is probably taken by another plugin "
                   "or device; choose a different pin under GpioPin.", level="error")
        return
    button.when_held = on_held
    button.when_released = on_released
    _button = button
    auto = _auto_seconds()
    plugin.log(f"WebPageButtonPlugin ready on GPIO{pin} (long press = {long_press} s, "
               f"automatic switching = {'off' if auto <= 0 else str(auto) + ' s'}).")


def _button_loop():
    """Apply a changed GpioPin or LongPressSeconds without restarting the plugin."""
    while True:
        try:
            _setup_button()
        except Exception as exc:
            plugin.log(f"Button setup failed: {exc}", level="error")
        if _shutdown_event.wait(5):
            break


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------
def main():
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    atexit.register(close_page)
    support_page.start(plugin)
    # The Plugins page only leaves "waiting for plugin to finish initializing"
    # once the plugin has its event connection; every working plugin opens it
    # before ready().
    plugin.connect_sse()
    # Report ready before touching the GPIO, so a missing or busy pin can never
    # leave the plugin stuck in "waiting for plugin to finish initializing".
    plugin.ready()
    _kill_leftovers()
    start_wrapper_server()

    threading.Thread(target=_auto_loop, name="auto-switch", daemon=True).start()
    _refresh_preload_cfg()
    threading.Thread(target=_preload_loop, name="preload", daemon=True).start()
    threading.Thread(target=_button_loop, name="button", daemon=True).start()

    _shutdown_event.wait()
    support_page.stop(plugin)

if __name__ == "__main__":
    main()
