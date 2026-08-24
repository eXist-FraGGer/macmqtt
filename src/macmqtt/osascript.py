import subprocess
import threading

# Shared by every feature that shells out via AppleScript (sound.py,
# source.py) — serializes calls so the polling loop and MQTT message
# handling in core/bridge.py don't invoke osascript concurrently.
_lock = threading.Lock()


def osascript(expr):
    with _lock:
        return subprocess.run(
            ["osascript", "-e", expr], capture_output=True, text=True, timeout=5
        ).stdout.strip()
