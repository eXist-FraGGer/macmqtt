# Three detection "engines", tried in order, first playing source wins:
#   1. native apps (Music/Spotify) — same AppleScript dictionary shape
#      (`player state`, `current track`), extremely stable/long-documented.
#   2. Safari — `do JavaScript ... in`, its own dialect.
#   3. Chromium family (Arc/Chrome/Brave/Edge/Vivaldi/Opera/...) — one
#      shared AppleScript dictionary (`execute ... javascript`), verified
#      live against Arc this session. Covers any Chromium browser just by
#      adding its bundle id below — no per-browser code.
#
# System-wide "now playing" (MediaRemote.framework, what Control Center's
# widget uses) was tried and is blocked: confirmed empirically this
# session — the call completes but returns nil even while syslog shows
# the OS itself actively receiving now-playing data from the browser, a
# signature of an entitlement check silently failing, not "nothing
# playing". No user-grantable permission for it exists (no prompt is ever
# shown), so there's nothing to fix here — it's a hard wall, not a bug.
#
# CRITICAL: querying an app that hasn't had Automation permission granted
# yet can *hang* (confirmed live with Safari — >120s, not a quick error).
# Every osascript call here has a short, explicit timeout for exactly
# that reason — never remove it.
import json
import time

from AppKit import NSWorkspace

from .. import osascript as osascript_mod
from ..helpers.hass import HA_DEVICE_NAME, ha_device

NATIVE_APPS = (
    "com.apple.Music",
    "com.spotify.client",
)
SAFARI_BUNDLE_ID = "com.apple.Safari"
CHROMIUM_BROWSERS = (
    "company.thebrowser.Browser",  # Arc
    "com.google.Chrome",
    "com.brave.Browser",
    "com.microsoft.edgemac",
    "com.vivaldi.Vivaldi",
    "com.operasoftware.Opera",
)

CALL_TIMEOUT = 2  # seconds, per osascript call — see CRITICAL note above.
# Separate, coarser cadence than the 3s bridge poll (sound.py) — one check
# here can mean several osascript round-trips; no need to hammer that
# every cycle, and it shares sound.py's osascript lock.
CHECK_INTERVAL = 8

INITIAL_POLL_STATE = (None, 0.0)

# Field separator for AppleScript results — safer than hand-rolling JSON
# escaping in AppleScript string concatenation. \x01 won't appear in
# real track metadata.
_SEP = "\x01"

_NATIVE_SCRIPT = '''\
tell application id "%(bundle_id)s"
  if player state is playing then
    set t to current track
    return (name of t) & "%(sep)s" & (artist of t) & "%(sep)s" & (album of t)
  else
    return "null"
  end if
end tell
'''

_SAFARI_SCRIPT = '''\
tell application id "com.apple.Safari"
  set winCount to count of windows
  set foundResult to "null"
  repeat with i from 1 to winCount
    try
      set jsResult to do JavaScript "%(js)s" in current tab of window i
      if jsResult is not "null" then
        set foundResult to jsResult
        exit repeat
      end if
    end try
  end repeat
  foundResult
end tell
'''

_CHROMIUM_SCRIPT = '''\
tell application id "%(bundle_id)s"
  set winCount to count of windows
  set foundResult to "null"
  repeat with i from 1 to winCount
    try
      set jsResult to execute (active tab of window i) javascript "%(js)s"
      if jsResult is not "null" then
        set foundResult to jsResult
        exit repeat
      end if
    end try
  end repeat
  foundResult
end tell
'''

# Media Session API — a real web standard, populated by most streaming
# sites (YouTube, Spotify Web, etc.) specifically so the OS/browser can
# show now-playing controls. Returns "null" unless actively playing.
_MEDIA_SESSION_JS = (
    "JSON.stringify((function(){"
    "var m=navigator.mediaSession&&navigator.mediaSession.metadata;"
    "var s=navigator.mediaSession?navigator.mediaSession.playbackState:null;"
    "if(s!==\\\"playing\\\")return null;"
    "return {title:(m&&m.title)||document.title,artist:(m&&m.artist)||\\\"\\\","
    "album:(m&&m.album)||\\\"\\\","
    "artwork:(m&&m.artwork&&m.artwork[0])?m.artwork[0].src:\\\"\\\"};"
    "})())"
)


def _running_bundle_ids():
    # NSWorkspace, not `System Events` — confirmed the AppleScript route
    # can hang waiting on an Automation prompt nobody answers; this is a
    # plain public API, no permission involved, instant.
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    return {str(a.bundleIdentifier()) for a in apps if a.bundleIdentifier()}


def _unwrap(raw):
    # osascript's CLI prints a plain AppleScript string result wrapped in
    # its own quoting/escaping (e.g. `null` comes back as the 6-char
    # `"null"`) — that format happens to be valid JSON string syntax, so
    # one json.loads() reverses it and hands back the real text.
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _native_now_playing(bundle_id):
    try:
        raw = osascript_mod.osascript(_NATIVE_SCRIPT % {"bundle_id": bundle_id, "sep": _SEP}, timeout=CALL_TIMEOUT)
    except Exception:
        return None
    result = _unwrap(raw)
    if result == "null" or not result:
        return None
    parts = result.split(_SEP)
    if len(parts) != 3:
        return None
    title, artist, album = parts
    return {"title": title, "artist": artist, "album": album, "artwork": ""}


def _browser_now_playing(script_template, bundle_id):
    try:
        raw = osascript_mod.osascript(script_template % {"bundle_id": bundle_id, "js": _MEDIA_SESSION_JS}, timeout=CALL_TIMEOUT)
    except Exception:
        return None
    result = _unwrap(raw)
    if result == "null" or not result:
        return None
    try:
        data = json.loads(result)
    except ValueError:
        return None
    if not data:
        return None
    return {
        "title": data.get("title") or "",
        "artist": data.get("artist") or "",
        "album": data.get("album") or "",
        "artwork": data.get("artwork") or "",
    }


def current_track():
    """First actively-playing source wins. None if nothing is playing anywhere known."""
    running = _running_bundle_ids()

    for bundle_id in NATIVE_APPS:
        if bundle_id in running:
            info = _native_now_playing(bundle_id)
            if info:
                return info

    if SAFARI_BUNDLE_ID in running:
        info = _browser_now_playing(_SAFARI_SCRIPT, SAFARI_BUNDLE_ID)
        if info:
            return info

    for bundle_id in CHROMIUM_BROWSERS:
        if bundle_id in running:
            info = _browser_now_playing(_CHROMIUM_SCRIPT, bundle_id)
            if info:
                return info

    return None


def _snapshot():
    info = current_track()
    if info is None:
        return {"state": "idle", "title": "", "artist": "", "album": "", "artwork": ""}
    return {
        "state": "playing",
        "title": info["title"],
        "artist": info["artist"],
        "album": info["album"],
        "artwork": info["artwork"],
    }


# --- MQTT feature contract (see core/bridge.py) ---
# Read-only: nothing to command, so no subscribe_topics/handle work to do.


def topics(cfg):
    return {"now_playing": f"mac/{cfg['device_id']}/media/now_playing"}


def subscribe_topics(cfg):
    return []


def discovery_configs(cfg, availability_topic):
    device_id = cfg["device_id"]
    t = topics(cfg)
    device = ha_device(device_id)
    entity_id = f"sensor.{HA_DEVICE_NAME.lower()}_{device_id}_now_playing"
    return [
        (
            f"homeassistant/sensor/{device_id}_now_playing/config",
            {
                "name": "MacBook Now Playing",
                "unique_id": f"{device_id}_now_playing",
                "default_entity_id": entity_id,
                "state_topic": t["now_playing"],
                "value_template": "{{ value_json.state }}",
                "json_attributes_topic": t["now_playing"],
                "availability_topic": availability_topic,
                "device": device,
            },
        )
    ]


def handle(client, cfg, topic, payload):
    return False


def poll(client, cfg, state):
    last_snapshot, last_check = state
    now = time.monotonic()
    if now - last_check < CHECK_INTERVAL:
        return state
    snapshot = _snapshot()
    if snapshot != last_snapshot:
        client.publish(topics(cfg)["now_playing"], json.dumps(snapshot), retain=True)
    return (snapshot, now)
