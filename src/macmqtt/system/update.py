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


def run_upgrade():
    # Blocking on purpose — the old fire-and-forget version quit the app
    # immediately and let `brew upgrade` (which downloads the whole .app,
    # can take a while) run detached in the background. From the user's
    # side that just looked like the app crashed and vanished with no
    # feedback. Caller is expected to run this off the main thread and
    # show progress, then only quit+relaunch once it actually returns.
    brew = brew_path()
    try:
        result = subprocess.run(
            [brew, "upgrade", "--cask", "macmqtt"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "brew upgrade завис (5+ минут) — проверь вручную в терминале."
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or "brew upgrade завершился с ошибкой."
    return True, ""


def relaunch():
    subprocess.Popen(["open", "-a", APP_PATH])


def open_release_page():
    # No Homebrew (installed via manually-downloaded .app) — can't script
    # a replace-in-place, so just hand the user the same download page
    # they used the first time.
    subprocess.run(["open", RELEASE_PAGE])
