import subprocess

from .. import osascript as osascript_mod
from ..helpers.hass import HA_DEVICE_NAME, SOURCE_SLUGS, ha_device


def activate_app(bundle_id):
    osascript_mod.osascript(f'tell application id "{bundle_id}" to activate')


def list_shortcuts():
    # encoding explicit: GUI-launched apps have no LANG/LC_ALL, so text=True
    # alone falls back to ASCII and chokes on non-Latin shortcut names.
    result = subprocess.run(["shortcuts", "list"], capture_output=True, timeout=5)
    return [line for line in result.stdout.decode("utf-8").splitlines() if line.strip()]


def run_shortcut(name):
    subprocess.run(["shortcuts", "run", name], timeout=10)


# --- MQTT feature contract (see core/bridge.py) ---
# No poll()/publish_state() here — sources are fire-and-forget actions,
# there's no live state to report back.


def topics(cfg):
    return {"source_run": f"mac/{cfg['device_id']}/source/run"}


def subscribe_topics(cfg):
    return [topics(cfg)["source_run"]]


def discovery_configs(cfg, availability_topic):
    device_id = cfg["device_id"]
    t = topics(cfg)
    device = ha_device(device_id)
    configs = []
    for slug, source in zip(SOURCE_SLUGS, cfg["sources"]):
        topic = f"homeassistant/button/{device_id}_source_{slug}/config"
        kind = source.get("kind")
        valid = (kind == "app" and source.get("bundle_id")) or (kind == "shortcut" and source.get("shortcut"))
        if not valid:
            # Retained discovery messages never expire on their own — an
            # empty payload is the only way to remove a previously
            # published entity from HA once its slot is cleared.
            configs.append((topic, None))
            continue
        name = source.get("name") or f"MacBook Source {slug}"
        # HA derives entity_id by slugifying `name`, not unique_id — with
        # arbitrary app/shortcut names that's unpredictable (confirmed:
        # "Arc" -> button.macbook_arc). default_entity_id pins it
        # explicitly, but only takes effect the first time this entity is
        # ever created — an already-registered entity keeps its old
        # entity_id regardless.
        entity_id = f"button.{HA_DEVICE_NAME.lower()}_{device_id}_source_{slug}"
        configs.append(
            (
                topic,
                {
                    "name": name,
                    "unique_id": f"{device_id}_source_{slug}",
                    "default_entity_id": entity_id,
                    "command_topic": t["source_run"],
                    "payload_press": slug,
                    "availability_topic": availability_topic,
                    "device": device,
                },
            )
        )
    return configs


def handle(client, cfg, topic, payload):
    if topic != topics(cfg)["source_run"]:
        return False
    try:
        # payload is the slot's slug, not the bundle id/shortcut name
        # itself — keeps the actual action off the wire and out of
        # retained MQTT discovery config.
        source = cfg["sources"][SOURCE_SLUGS.index(payload)]
        kind = source.get("kind")
        if kind == "app" and source.get("bundle_id"):
            activate_app(source["bundle_id"])
        elif kind == "shortcut" and source.get("shortcut"):
            run_shortcut(source["shortcut"])
    except (ValueError, IndexError):
        pass
    except subprocess.TimeoutExpired:
        print(f"osascript/shortcuts завис при обработке {topic}, пропускаю команду")
    return True
