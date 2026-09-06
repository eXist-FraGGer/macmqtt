# PRIMARY: system-wide "now playing", via MediaRemote.framework's
# MRNowPlayingRequest.localNowPlayingItem — read through a JXA (`osascript
# -l JavaScript`) subprocess, NOT called in-process. This distinction is
# the whole trick: calling MRMediaRemoteGetNowPlayingInfo() ourselves is
# entitlement-blocked (confirmed empirically — completes but returns nil
# even while syslog shows the OS itself actively receiving the same data),
# with no user-grantable permission for it. But `localNowPlayingItem` reads
# a LOCAL cache that mediaremoted already pushed into whichever process
# asks — and asking via osascript (an Apple-signed system binary, not our
# own ad-hoc-signed app) gets a real answer. Confirmed live: works for any
# app (native or web/Media-Session-based), independent of which app/window
# is frontmost, which Space is showing, or which tab is active — the exact
# focus/Space dependence that makes the fallback engines below unreliable.
# Also the only source with a real play/pause signal (`playbackRate`: 0 =
# paused).
#
# Fallback engines, tried only if the above finds nothing:
#   - native apps (Music/Spotify) — same AppleScript dictionary shape
#     (`player state`, `current track`), extremely stable/long-documented.
#   - Safari — `do JavaScript ... in`, its own dialect.
#   - Chromium family (Arc/Chrome/Brave/Edge/Vivaldi/Opera/...) — one
#     shared AppleScript dictionary (`execute ... javascript`), verified
#     live against Arc. Covers any Chromium browser just by adding its
#     bundle id below — no per-browser code.
#   - Window-title fallback — the three above only ever check each
#     window's *active* tab, and (like the primary engine's window-facing
#     cousins) go blind the moment its Space isn't the one on screen. A
#     fullscreen/PiP video player names its OS window after the video
#     (confirmed live) — CGWindowListCopyWindowInfo reads that instantly,
#     no subprocess, for any window owned by a process we already trust.
#     Title only, no artist/album/artwork.
#
# CRITICAL: querying an app that hasn't had Automation permission granted
# yet can *hang* (confirmed live with Safari — >120s, not a quick error).
# Every osascript call here has a short, explicit timeout for exactly
# that reason — never remove it.
import json
import time

from AppKit import NSScreen, NSWorkspace
from Quartz import CGWindowListCopyWindowInfo, kCGNullWindowID, kCGWindowListOptionOnScreenOnly

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

# For the app-icon artwork fallback (see _app_icon_url) — HA's media_player
# entity_picture is always fetched server-side by HA itself (aiohttp, via
# its /api/media_player_proxy proxy), never rendered directly by the
# browser, so it has to be a real http(s) URL; a data: URI silently fails
# there (confirmed against HA core's async_fetch_image — plain
# websession.get(url), no data: scheme support).
#
# Independent of NATIVE_APPS/CHROMIUM_BROWSERS above — the primary
# MediaRemote engine reports a bundle id for whatever app actually owns
# "now playing" system-wide, not just the ones this file knows how to
# query directly, so this list is deliberately broader. Bundle ids
# confirmed either on this machine (`mdls -name kMDItemCFBundleIdentifier`)
# or straight from the app's own repo/Info.plist — not guessed.
#
# thesvg.org's icon set (raw files pulled via jsdelivr's GitHub CDN — a
# stable, widely-used way to hotlink a repo's files) hosts real,
# brand-colored app/service logos — tried first since a plain per-domain
# favicon is often useless: confirmed live that Safari/Music/TV/Podcasts/
# QuickTime all sit on apple.com, so a favicon-by-domain lookup made all
# five show the exact same generic Apple logo, none of them recognizable
# as the app that was actually playing. Every slug below confirmed live
# (HTTP 200) against https://cdn.jsdelivr.net/gh/glincker/thesvg@main/
# public/icons/<slug>/default.svg.
_APP_ICON_SLUGS = {
    "com.apple.Music": "apple-music",
    "com.apple.podcasts": "apple-podcasts",
    "com.apple.TV": "apple-tv",
    "com.apple.QuickTimePlayerX": "quicktime",
    "com.spotify.client": "spotify",
    "tv.plex.desktop": "plex",
    "org.videolan.vlc": "vlc-media-player",
    "io.mpv": "mpv",
    "com.apple.Safari": "safari",
    "org.mozilla.firefox": "firefox",
    "company.thebrowser.Browser": "arc",
    "com.google.Chrome": "chrome",
    "com.brave.Browser": "brave",
    "com.microsoft.edgemac": "edge",
    "com.vivaldi.Vivaldi": "vivaldi",
    "com.operasoftware.Opera": "opera",
}

# Favicon-by-domain fallback — only for apps thesvg.org has no icon for
# (confirmed: HTTP 404 for every slug variant tried). Worse than a real
# brand icon (just the company's generic site logo) but still better than
# nothing.
_APP_FAVICON_DOMAINS = {
    "com.colliderli.iina": "iina.io",
}

# Safari's actual video/audio playback is frequently attributed to one of
# its own internal helper processes, not com.apple.Safari itself —
# confirmed live: MediaRemote reported "com.apple.WebKit.GPU" as the
# bundle id for a plain YouTube video played in Safari. Any of these
# helpers means "this is Safari" for icon purposes.
_SAFARI_HELPER_PREFIX = "com.apple.WebKit"

CALL_TIMEOUT = 2  # seconds, per osascript call — see CRITICAL note above.
# There's no push/event path here — confirmed live that MediaRemote's real
# updates travel over a private XPC channel opened by
# MRMediaRemoteRegisterForNowPlayingNotifications, not a public
# NSDistributedNotificationCenter broadcast anyone can just listen to, and
# that registration call needs a raw dispatch_queue_t that's crashed this
# process twice (SIGSEGV, SIGTRAP) trying to hand-roll its ABI through
# PyObjC/ctypes — not something to risk shipping. So reacting to a manual
# pause/play click made *inside the browser itself* (not through our own
# MQTT command) can only happen via polling. A check itself is cheap
# (~0.1-0.4s), so this just needs to be <= core/bridge.py's POLL_INTERVAL
# (currently both 1s) — the settings tab's own auto-refresh timer also
# runs at this same rate. 250ms was considered and rejected: no perceptible
# benefit over 1s, just a needlessly busier CPU.
CHECK_INTERVAL = 1

INITIAL_POLL_STATE = (None, 0.0)

# JXA, not AppleScript — only JXA's ObjC bridge (`$.NSClassFromString`, ...)
# can reach MRNowPlayingRequest. Two non-obvious JXA traps, both hit live:
#   - `isNil()` matters everywhere here: a nil ObjC value comes back from
#     the bridge as a JS-truthy wrapper, not JS null/undefined — a plain
#     `v ? ... : null` check silently treats real nils as present.
#   - console.log() writes to *stderr* in JXA, not stdout — osascript()
#     only captures stdout, so that looked like the query always failing
#     until switching to a bare trailing expression instead (which JXA,
#     like AppleScript, auto-prints to stdout as the script's result).
_LOCAL_NOW_PLAYING_JS = '''\
ObjC.import('AppKit');
const MediaRemote = $.NSBundle.bundleWithPath('/System/Library/PrivateFrameworks/MediaRemote.framework/');
MediaRemote.load;
const Req = $.NSClassFromString('MRNowPlayingRequest');
const item = Req.localNowPlayingItem;
function isNil(v) { try { return v.isNil(); } catch (e) { return v === null || v === undefined; } }
var out;
if (isNil(item)) {
  out = 'null';
} else {
  const info = item.nowPlayingInfo;
  const get = key => { const v = info.valueForKey(key); return isNil(v) ? null : ObjC.unwrap(v); };
  let artwork = '';
  const artData = info.valueForKey('kMRMediaRemoteNowPlayingInfoArtworkData');
  if (!isNil(artData)) {
    const b64 = ObjC.unwrap(artData.base64EncodedStringWithOptions(0));
    if (b64 && b64.length > 0) {
      const mime = get('kMRMediaRemoteNowPlayingInfoArtworkMIMEType') || 'image/jpeg';
      artwork = 'data:' + mime + ';base64,' + b64;
    }
  }
  const player = Req.localNowPlayingPlayerPath;
  const client = isNil(player) ? null : player.client;
  const bundleId = client && !isNil(client) ? ObjC.unwrap(client.bundleIdentifier) : '';
  const result = {
    title: get('kMRMediaRemoteNowPlayingInfoTitle') || '',
    artist: get('kMRMediaRemoteNowPlayingInfoArtist') || '',
    album: get('kMRMediaRemoteNowPlayingInfoAlbum') || '',
    playbackRate: get('kMRMediaRemoteNowPlayingInfoPlaybackRate'),
    artwork: artwork,
    bundleId: bundleId
  };
  out = JSON.stringify(result);
}
out
'''

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


def _candidate_pids():
    # pid, not bundle id, to cross-reference against CGWindowList's
    # kCGWindowOwnerPID below.
    known = set(NATIVE_APPS) | {SAFARI_BUNDLE_ID} | set(CHROMIUM_BROWSERS)
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    return {a.processIdentifier() for a in apps if str(a.bundleIdentifier()) in known}


def _is_fullscreen_bounds(bounds):
    # A genuine fullscreen window's bounds match some display's frame
    # near-exactly (confirmed live: 1920x1080 for a video fullscreened on
    # a 1920x1080 display, origin at that display's origin).
    width, height = bounds.get("Width", 0), bounds.get("Height", 0)
    for screen in NSScreen.screens():
        size = screen.frame().size
        if abs(width - size.width) <= 4 and abs(height - size.height) <= 4:
            return True
    return False


def _fullscreen_or_pip_title():
    pids = _candidate_pids()
    if not pids:
        return None
    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    for w in windows:
        if w.get("kCGWindowOwnerPID") not in pids:
            continue
        name = (w.get("kCGWindowName") or "").strip()
        if not name:
            continue
        # A titled window alone isn't enough — confirmed live: a plain
        # pinned/utility browser window can have a non-empty kCGWindowName
        # too (e.g. a small window showing a dashboard) and would
        # otherwise beat the real fullscreen player depending on
        # z-order at the moment of the check. Only trust the title if the
        # window is actually shaped like a fullscreen player (bounds match
        # a display) or a PiP float (non-zero window layer).
        if _is_fullscreen_bounds(w.get("kCGWindowBounds") or {}) or w.get("kCGWindowLayer", 0) != 0:
            return {"title": name, "artist": "", "album": "", "artwork": ""}
    return None


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


def _local_now_playing():
    try:
        raw = osascript_mod.osascript_js(_LOCAL_NOW_PLAYING_JS, timeout=CALL_TIMEOUT)
    except Exception:
        return None
    if not raw or raw == "null":
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    # A paused player still has a real nowPlayingItem (confirmed live:
    # title/artist stick around, only playbackRate drops to 0) — genuinely
    # nothing loaded is what "null" above means, not this. Reporting only
    # playing/idle collapsed that distinction, which broke HA cards (like
    # mini-media-player) that check for a real "paused" state before
    # sending media_play: seeing "idle" instead, they assumed the player
    # was off and sent a command we don't support, so pressing play did
    # nothing. "playing" here reflects that instead of folding into state.
    artwork = data.get("artwork") or ""
    if not artwork:
        # Real artwork bytes only show up here for apps that push them into
        # MediaRemote directly (Music, Spotify, ...) — a lot of web/Media
        # Session content doesn't (confirmed live: mime type present, 0
        # actual bytes). Getting the real poster for those would mean
        # querying the browser tab directly again, reintroducing exactly
        # the focus/Space dependence this engine exists to avoid.
        artwork = _app_icon_url(data.get("bundleId") or "")
    return {
        "title": data.get("title") or "",
        "artist": data.get("artist") or "",
        "album": data.get("album") or "",
        "artwork": artwork,
        "playing": bool(data.get("playbackRate")),
    }


def _app_icon_url(bundle_id):
    if bundle_id.startswith(_SAFARI_HELPER_PREFIX):
        bundle_id = SAFARI_BUNDLE_ID
    slug = _APP_ICON_SLUGS.get(bundle_id)
    if slug:
        return f"https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/{slug}/default.svg"
    domain = _APP_FAVICON_DOMAINS.get(bundle_id)
    if domain:
        return f"https://www.google.com/s2/favicons?sz=128&domain={domain}"
    return ""


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
    info = _local_now_playing()
    if info:
        return info

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

    # Last resort: catches fullscreen/PiP video whose tab isn't the
    # active one (or is unreachable among hundreds of tabs) — see module
    # docstring. Title only, but instant and no subprocess.
    return _fullscreen_or_pip_title()


def _snapshot():
    info = current_track()
    if info is None:
        return {"state": "idle", "media_title": "", "media_artist": "", "media_album_name": "", "artwork": ""}
    # Only the MediaRemote engine can tell paused from playing (see
    # _local_now_playing) — the fallback engines never return anything
    # unless they already believe it's actively playing, so default True
    # is exactly their existing behavior, unchanged.
    state = "playing" if info.get("playing", True) else "paused"
    # media_title/media_artist/media_album_name — named to match HA's own
    # MediaPlayerEntityStateAttribute constants exactly (not just "title"),
    # because Universal's active_child_template (see helpers/hass.py) reads
    # them straight off this entity's attributes by that literal name.
    return {
        "state": state,
        "media_title": info["title"],
        "media_artist": info["artist"],
        "media_album_name": info["album"],
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
