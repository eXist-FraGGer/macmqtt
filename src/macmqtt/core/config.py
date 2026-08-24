import json
import os
from pathlib import Path

APP_NAME = "macmqtt"
CONFIG_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS = {
    "mqtt_host": "",
    "mqtt_port": 1883,
    "mqtt_user": "",
    "mqtt_pass": "",
    "device_id": "macbook",
    "ha_discovery": True,
    "hide_menu_bar_icon": False,
    # Up to 10 user-configured actions ("Источник 1".."10" in Settings).
    # kind == "app" -> activate bundle_id; kind == "shortcut" -> run the
    # named Shortcuts.app scenario. Slot is unset when kind == "". Maps
    # 1:1 onto Yandex's fixed mode vocabulary (one..ten) for
    # devices.capabilities.mode — see bridge.py SOURCE_SLUGS.
    "sources": [{"name": "", "kind": "", "bundle_id": "", "shortcut": ""} for _ in range(10)],
}

ENV_MAP = {
    "mqtt_host": "MQTT_HOST",
    "mqtt_port": "MQTT_PORT",
    "mqtt_user": "MQTT_USER",
    "mqtt_pass": "MQTT_PASS",
    "device_id": "MAC_DEVICE_ID",
    "ha_discovery": "HA_DISCOVERY",
}


def load():
    cfg = DEFAULTS.copy()
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    for key, env_key in ENV_MAP.items():
        if env_key not in os.environ:
            continue
        raw = os.environ[env_key]
        if isinstance(DEFAULTS[key], bool):
            cfg[key] = raw.lower() == "true"
        elif isinstance(DEFAULTS[key], int):
            cfg[key] = int(raw)
        else:
            cfg[key] = raw
    return cfg


def save(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    CONFIG_PATH.chmod(0o600)
