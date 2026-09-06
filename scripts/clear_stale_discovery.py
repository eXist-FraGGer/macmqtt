"""One-off cleanup for orphaned MQTT discovery entities. retain=True on
discovery configs means the broker keeps every version ever published
forever, across every rename/unique_id scheme this project has been
through — HA re-adopts them any time it resubscribes, even after deleting
the device in HA itself (that only clears HA's registry, not the broker).

Run once from the repo root after an entity id scheme changes:
    venv/bin/python3 scripts/clear_stale_discovery.py

Connects with the same credentials as the app (~/Library/Application
Support/macmqtt/config.json), listens for retained homeassistant/+/+/config
topics mentioning this device_id, and clears (empty-retained-publish)
whichever ones aren't part of the current valid set — computed straight
from features/*.discovery_configs(), so this never drifts from what the
app actually publishes. Safe to re-run.
"""
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from macmqtt.core import config as cfgmod
from macmqtt.core.bridge import FEATURES

cfg = cfgmod.load()
device_id = cfg["device_id"]
availability_topic = f"mac/{device_id}/status"

valid = {
    topic
    for feature in FEATURES
    for topic, payload in feature.discovery_configs(cfg, availability_topic)
    if payload is not None
}

seen = set()


def on_connect(client, userdata, flags, rc):
    client.subscribe("homeassistant/+/+/config")


def on_message(client, userdata, msg):
    if not msg.payload:
        return
    if device_id in msg.topic:
        seen.add(msg.topic)


client = mqtt.Client()
if cfg["mqtt_user"]:
    client.username_pw_set(cfg["mqtt_user"], cfg["mqtt_pass"])
client.on_connect = on_connect
client.on_message = on_message
client.connect(cfg["mqtt_host"], cfg["mqtt_port"], keepalive=10)
client.loop_start()
time.sleep(3)
client.loop_stop()

stale = seen - valid
if not stale:
    print("Мусора не найдено.")
else:
    for topic in sorted(stale):
        print("Удаляю:", topic)
        client.publish(topic, payload=None, retain=True)
    time.sleep(1)
    print(f"Удалено: {len(stale)}")
client.disconnect()
