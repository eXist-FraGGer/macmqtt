import json
import os
import subprocess
import tempfile
import urllib.request

import macmqtt

_DOWNLOAD_CHUNK = 256 * 1024

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


def _cache_path(brew, timeout=10):
    # The exact path `brew upgrade --cask` itself would download to — a
    # stable, public brew command, not a guess at brew's internal hashing.
    # Pre-filling it (see _download_with_progress) makes the following
    # `brew upgrade` find the file already there with a matching sha256
    # and skip its own download, going straight to the (fast) install step.
    result = subprocess.run([brew, "--cache", "--cask", "macmqtt"], capture_output=True, text=True, timeout=timeout)
    path = result.stdout.strip()
    if result.returncode != 0 or not path:
        raise RuntimeError(result.stderr.strip() or "brew --cache не вернул путь")
    return path


def _download_with_progress(version, dest, on_progress):
    # brew's own download output isn't a percentage when it's not attached
    # to a TTY (which it never is here) — downloading it ourselves is the
    # only way to show real byte progress instead of just a spinner.
    url = f"https://github.com/eXist-FraGGer/macmqtt/releases/download/v{version}/macmqtt-{version}.zip"
    request = urllib.request.Request(url, headers={"User-Agent": "macmqtt-updater"})
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with urllib.request.urlopen(request, timeout=30) as resp, open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(_DOWNLOAD_CHUNK)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            on_progress(done, total)
    os.replace(tmp, dest)


def run_upgrade(on_progress=None, on_phase=None):
    # Blocking on purpose — the old fire-and-forget version quit the app
    # immediately and let `brew upgrade` (which downloads the whole .app,
    # can take a while) run detached in the background. From the user's
    # side that just looked like the app crashed and vanished with no
    # feedback. Caller is expected to run this off the main thread and
    # show progress, then only quit+relaunch once it actually returns.
    def phase(text):
        if on_phase:
            on_phase(text)

    brew = brew_path()

    phase("Скачивание обновления…")
    try:
        latest = latest_version()
        cache_path = _cache_path(brew)
        _download_with_progress(latest, cache_path, on_progress or (lambda done, total: None))
    except Exception as e:
        return False, f"Не удалось скачать обновление: {e}"

    phase("Устанавливаю…")
    # stdout/stderr go to a real temp file, not PIPE: brew's cask install
    # step can spawn a helper (Spotlight reindex, lsregister, ...) that
    # inherits the pipe's write end and outlives brew itself — with PIPE,
    # subprocess.run() then blocks waiting for EOF that never comes, well
    # past brew actually finishing (confirmed live: Caskroom + /Applications
    # already showed the new version while this was still "running").
    # A file has no such "wait for the writer to close it" behavior.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as out:
        try:
            result = subprocess.run(
                [brew, "upgrade", "--cask", "macmqtt"],
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return False, "brew upgrade завис (5+ минут) — проверь вручную в терминале."
        if result.returncode != 0:
            out.seek(0)
            return False, out.read().strip() or "brew upgrade завершился с ошибкой."

    # brew doesn't always strip the quarantine flag from a freshly-installed
    # cask app (observed live: still present right after a successful
    # upgrade) — left on, relaunch()'s `open` can silently lose to
    # Gatekeeper's first-run check instead of actually reopening the app.
    # Our own ad-hoc-signed build has nothing to hide from it.
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", APP_PATH], capture_output=True)
    return True, ""


def relaunch():
    # run(), not Popen(): waits for `open` to actually hand the app off to
    # LaunchServices before the caller quits itself. Popen() (fire and
    # forget) let the caller terminate before `open` necessarily finished,
    # which — together with the quarantine flag above — could leave the
    # app not actually relaunched (observed live).
    subprocess.run(["open", "-a", APP_PATH])


def open_release_page():
    # No Homebrew (installed via manually-downloaded .app) — can't script
    # a replace-in-place, so just hand the user the same download page
    # they used the first time.
    subprocess.run(["open", RELEASE_PAGE])
