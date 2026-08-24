#!/bin/bash
# Builds dist/macmqtt.app and zips it as release/macmqtt-<version>.zip,
# printing the sha256 the Cask needs. Version comes from src/macmqtt/__init__.py.
set -e
cd "$(dirname "$0")/.."

VERSION=$(venv/bin/python3 -c "import sys; sys.path.insert(0, 'src'); import macmqtt; print(macmqtt.__version__)")
scripts/build_app.sh

mkdir -p release
ZIP="release/macmqtt-$VERSION.zip"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent dist/macmqtt.app "$ZIP"

echo "Собрано: $ZIP"
echo "sha256:"
shasum -a 256 "$ZIP"
