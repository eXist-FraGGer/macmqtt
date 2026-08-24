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

echo "Built: dist/macmqtt.app"
