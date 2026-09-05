import subprocess

from Quartz import CGEventPost, NSEvent, NSSystemDefined, kCGHIDEventTap

from .. import osascript as osascript_mod
from ..helpers.hass import ha_device

NX_KEYTYPE_SOUND_UP = 0
NX_KEYTYPE_SOUND_DOWN = 1
NX_KEYTYPE_PLAY = 16
NX_KEYTYPE_NEXT = 17
NX_KEYTYPE_PREVIOUS = 18
NX_KEYTYPE_MUTE = 7

# poll()'s starting (last_volume, last_muted) — both unknown, so the first
# poll always publishes.
INITIAL_POLL_STATE = (None, None)


def _media_key(key_code):
    for key_down in (True, False):
        data1 = (key_code << 16) | ((0xA if key_down else 0xB) << 8)
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            NSSystemDefined, (0, 0), 0xA00 if key_down else 0xB00, 0, 0, 0, 8, data1, -1
        )
        CGEventPost(kCGHIDEventTap, ev.CGEvent())


def volume_up():
    _media_key(NX_KEYTYPE_SOUND_UP)


def volume_down():
    _media_key(NX_KEYTYPE_SOUND_DOWN)


def tap_mute():
    _media_key(NX_KEYTYPE_MUTE)


def tap_play_pause():
    # Same key the physical media/F8 button sends — toggles whatever app
    # currently owns "Now Playing" system-wide. No public API exists to
    # ask macOS what's playing or to target a specific app, so this can
    # only toggle, not report or force a specific play/pause state.
    _media_key(NX_KEYTYPE_PLAY)


def tap_next():
    _media_key(NX_KEYTYPE_NEXT)


def tap_previous():
    _media_key(NX_KEYTYPE_PREVIOUS)


def get_volume():
    return int(osascript_mod.osascript("output volume of (get volume settings)"))


def get_muted():
    return osascript_mod.osascript("output muted of (get volume settings)") == "true"


def set_volume(v):
    v = max(0, min(100, int(v)))
    osascript_mod.osascript(f"set volume output volume {v}")


def set_muted(m):
    osascript_mod.osascript(f"set volume output muted {'true' if m else 'false'}")


# --- MQTT feature contract (see core/bridge.py) ---


def topics(cfg):
    base = f"mac/{cfg['device_id']}"
    return {
        "volume_set": f"{base}/volume/set",
        "volume_step": f"{base}/volume/step",
        "volume_state": f"{base}/volume/state",
        "mute_set": f"{base}/mute/set",
        "mute_toggle": f"{base}/mute/toggle",
        "mute_state": f"{base}/mute/state",
        "media_play_pause": f"{base}/media/play_pause",
        "media_next": f"{base}/media/next",
        "media_previous": f"{base}/media/previous",
    }


def subscribe_topics(cfg):
    t = topics(cfg)
    return [
        t["volume_set"],
        t["volume_step"],
        t["mute_set"],
        t["mute_toggle"],
        t["media_play_pause"],
        t["media_next"],
        t["media_previous"],
    ]


def discovery_configs(cfg, availability_topic):
    device_id = cfg["device_id"]
    t = topics(cfg)
    device = ha_device(device_id)
    return [
        (
            f"homeassistant/number/{device_id}_volume/config",
            {
                "name": "MacBook Volume",
                "unique_id": f"{device_id}_volume",
                "command_topic": t["volume_set"],
                "state_topic": t["volume_state"],
                "availability_topic": availability_topic,
                "min": 0,
                "max": 100,
                "step": 1,
                "device": device,
            },
        ),
        (
            f"homeassistant/switch/{device_id}_mute/config",
            {
                "name": "MacBook Mute",
                "unique_id": f"{device_id}_mute",
                "command_topic": t["mute_set"],
                "state_topic": t["mute_state"],
                "availability_topic": availability_topic,
                "payload_on": "ON",
                "payload_off": "OFF",
                "device": device,
            },
        ),
        (
            f"homeassistant/button/{device_id}_volume_up/config",
            {
                "name": "MacBook Volume Up",
                "unique_id": f"{device_id}_volume_up",
                "command_topic": t["volume_step"],
                "payload_press": "+1",
                "availability_topic": availability_topic,
                "device": device,
            },
        ),
        (
            f"homeassistant/button/{device_id}_volume_down/config",
            {
                "name": "MacBook Volume Down",
                "unique_id": f"{device_id}_volume_down",
                "command_topic": t["volume_step"],
                "payload_press": "-1",
                "availability_topic": availability_topic,
                "device": device,
            },
        ),
        (
            f"homeassistant/button/{device_id}_play_pause/config",
            {
                "name": "MacBook Play/Pause",
                "unique_id": f"{device_id}_play_pause",
                "command_topic": t["media_play_pause"],
                "payload_press": "TOGGLE",
                "availability_topic": availability_topic,
                "device": device,
            },
        ),
        (
            f"homeassistant/button/{device_id}_next_track/config",
            {
                "name": "MacBook Next Track",
                "unique_id": f"{device_id}_next_track",
                "command_topic": t["media_next"],
                "payload_press": "PRESS",
                "availability_topic": availability_topic,
                "device": device,
            },
        ),
        (
            f"homeassistant/button/{device_id}_previous_track/config",
            {
                "name": "MacBook Previous Track",
                "unique_id": f"{device_id}_previous_track",
                "command_topic": t["media_previous"],
                "payload_press": "PRESS",
                "availability_topic": availability_topic,
                "device": device,
            },
        ),
    ]


def handle(client, cfg, topic, payload):
    t = topics(cfg)
    try:
        if topic == t["volume_set"]:
            set_volume(payload)
        elif topic == t["volume_step"]:
            (volume_up if int(payload) > 0 else volume_down)()
        elif topic == t["mute_set"]:
            want_muted = payload.upper() in ("ON", "TRUE", "1")
            if want_muted != get_muted():
                tap_mute()
        elif topic == t["mute_toggle"]:
            tap_mute()
        elif topic == t["media_play_pause"]:
            tap_play_pause()
            return True
        elif topic == t["media_next"]:
            tap_next()
            return True
        elif topic == t["media_previous"]:
            tap_previous()
            return True
        else:
            return False
    except subprocess.TimeoutExpired:
        print(f"osascript завис при обработке {topic}, пропускаю команду")
        return True
    publish_state(client, cfg)
    return True


def publish_state(client, cfg):
    t = topics(cfg)
    try:
        client.publish(t["volume_state"], str(get_volume()), retain=True)
        client.publish(t["mute_state"], "ON" if get_muted() else "OFF", retain=True)
    except subprocess.TimeoutExpired:
        print("osascript завис при публикации состояния, пропускаю")


def poll(client, cfg, state):
    t = topics(cfg)
    last_volume, last_muted = state
    try:
        v, m = get_volume(), get_muted()
        if v != last_volume:
            client.publish(t["volume_state"], str(v), retain=True)
            last_volume = v
        if m != last_muted:
            client.publish(t["mute_state"], "ON" if m else "OFF", retain=True)
            last_muted = m
    except subprocess.TimeoutExpired:
        print("osascript завис на этом цикле опроса, пропускаю")
    return (last_volume, last_muted)
