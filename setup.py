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
        "CFBundleShortVersionString": "0.1.0",
        # Menu bar only app: no Dock icon, no app switcher entry.
        "LSUIElement": True,
    },
    "packages": ["macmqtt", "rumps"],
}

setup(
    name="macmqtt",
    app=APP,
    options={"py2app": OPTIONS},
)
