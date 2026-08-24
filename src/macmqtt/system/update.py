import json
import os
import subprocess
import urllib.request

import macmqtt

RELEASES_API = "https://api.github.com/repos/eXist-FraGGer/macmqtt/releases/latest"
RELEASE_PAGE = "https://github.com/eXist-FraGGer/macmqtt/releases/latest"
APP_PATH = "/Applications/macmqtt.app"

# GUI-launched apps get a minimal PATH (confirmed earlier: no /opt/homebrew/bin,
# same class of bug that broke `shortcuts` before) — brew won't resolve by
# bare name, so check the two standard install locations explicitly.
_BREW_CANDIDATES = ("/opt/homebrew/bin/brew", "/usr/local/bin/brew")


def current_version():
    return macmqtt.__version__


def latest_version():
    with urllib.request.urlopen(RELEASES_API, timeout=5) as resp:
        data = json.load(resp)
    return data["tag_name"].lstrip("v")


def is_newer(latest, current):
    parse = lambda v: tuple(int(p) for p in v.split("."))
    return parse(latest) > parse(current)


def brew_path():
    for candidate in _BREW_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def upgrade_and_relaunch():
    # Detached: survives this process quitting (NSApp.terminate_ right
    # after this call). File replacement works fine on a running .app
    # (proven all session via manual rm -rf + cp -R) — the point of
    # quitting first isn't the upgrade itself, it's so the final `open`
    # starts the NEW code instead of just refocusing the old process.
    brew = brew_path()
    script = f'{brew} upgrade --cask macmqtt; open -a "{APP_PATH}"'
    subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True)


def open_release_page():
    # No Homebrew (installed via manually-downloaded .app) — can't script
    # a replace-in-place, so just hand the user the same download page
    # they used the first time.
    subprocess.run(["open", RELEASE_PAGE])
