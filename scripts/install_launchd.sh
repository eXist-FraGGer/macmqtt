#!/bin/bash
# Headless-режим только: автозапуск macmqtt run через launchd.
# Для .app это не нужно — Настройки -> "Запускать при входе в систему".
set -e
cd "$(dirname "$0")/.."
DEST=~/Library/LaunchAgents/com.local.macmqtt.plist
sed "s|/path/to/macmqtt|$(pwd)|" launchd/com.local.macmqtt.plist > "$DEST"
launchctl load "$DEST"
echo "Установлено: $DEST"
