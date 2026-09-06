import subprocess
import threading

# Shared by every feature that shells out via osascript (sound.py,
# source.py, nowplaying.py) — serializes calls so the polling loop and
# MQTT message handling in core/bridge.py don't invoke osascript
# concurrently.
_lock = threading.Lock()


def osascript(expr, timeout=5):
    with _lock:
        # encoding="utf-8" explicitly — text=True decodes via the process's
        # locale, and a GUI app launched by LaunchServices (not a shell) has
        # no LANG/LC_ALL set, so Python falls back to ASCII and throws on
        # any non-ASCII osascript output (Cyrillic track titles, etc).
        return subprocess.run(
            ["osascript", "-e", expr], capture_output=True, encoding="utf-8", timeout=timeout
        ).stdout.strip()


def osascript_js(expr, timeout=5):
    # Same as osascript() but -l JavaScript (JXA) — nowplaying.py's
    # MediaRemote query needs the ObjC bridge JXA gives access to, which
    # plain AppleScript can't do.
    with _lock:
        return subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", expr], capture_output=True, encoding="utf-8", timeout=timeout
        ).stdout.strip()
