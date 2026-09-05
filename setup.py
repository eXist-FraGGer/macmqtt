# Builds a standalone macmqtt.app with its own embedded Python, so people
# installing via brew don't need Python installed and macOS permissions
# (Accessibility etc.) attach to "macmqtt", not to a random interpreter.
# Build with: venv/bin/python3 setup.py py2app
from setuptools import setup

APP = ["scripts/run_gui.py"]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "src/macmqtt/assets/icon_app.icns",
    "plist": {
        "CFBundleIdentifier": "com.macmqtt.app",
        "CFBundleName": "macmqtt",
        "CFBundleDisplayName": "macmqtt",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSHumanReadableCopyright": "Copyright © eXist-FraGGer, 2026",
        # Menu bar only app: no Dock icon, no app switcher entry.
        "LSUIElement": True,
        # SMAppService (Launch at Login) needs Ventura — refuse to open on
        # older macOS with a clear system message instead of crashing.
        "LSMinimumSystemVersion": "13.0",
        # Shown on the Automation permission prompt (activate_app / mute
        # /volume via osascript send Apple Events) — without this the
        # prompt has no context, or the app just gets silently blocked
        # on some macOS versions.
        "NSAppleEventsUsageDescription": "Нужно, чтобы включать/выключать звук и переключаться на приложения по MQTT-командам.",
    },
    "packages": ["macmqtt", "rumps"],
}

setup(
    name="macmqtt",
    app=APP,
    options={"py2app": OPTIONS},
)
