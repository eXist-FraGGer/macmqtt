#!/bin/bash
# Builds dist/macmqtt.app via py2app.
# py2app uses a legacy setup.py, and setuptools refuses to run it if a
# pyproject.toml with [project] metadata sits in the same directory
# (static vs. dynamic metadata conflict) — so pyproject.toml is moved
# aside for the build and always restored, even if the build fails.
set -e
cd "$(dirname "$0")/.."

mv pyproject.toml pyproject.toml.bak
trap 'mv pyproject.toml.bak pyproject.toml' EXIT

rm -rf build dist
venv/bin/python3 setup.py py2app

# py2app hardcodes sys.executable (the build machine's real venv path)
# into PythonInfoDict:PythonExecutable, unconditionally, after merging our
# plist options — not overridable from setup.py. Scrub it so a public
# release doesn't leak the developer's local filesystem path.
/usr/libexec/PlistBuddy -c "Set :PythonInfoDict:PythonExecutable python3" \
  dist/macmqtt.app/Contents/Info.plist

# Editing Info.plist after py2app's own (ad-hoc) signing invalidates that
# signature — codesign --verify fails with "plist or signature have been
# modified" otherwise. Re-sign ad-hoc (same as py2app's own default).
codesign --force --deep -s - dist/macmqtt.app

echo "Built: dist/macmqtt.app"
