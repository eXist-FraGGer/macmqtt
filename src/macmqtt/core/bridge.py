import ipaddress
import json
import threading

import paho.mqtt.client as mqtt

from ..features import nowplaying, sound, source

# Registry of MQTT-triggered domains. Adding a new one (say, brightness)
# means writing features/brightness.py with the same small contract
# (topics/subscribe_topics/discovery_configs/handle, optionally
# poll+INITIAL_POLL_STATE for features with live state to report) and
# adding it here — nothing else in this file changes.
FEATURES = (sound, source, nowplaying)

POLL_INTERVAL = 3


def host_kind(host):
    try:
        ipaddress.ip_address(host)
        return "IP"
    except ValueError:
        return "домен/hostname"


def run(cfg, stop_event=None):
    if stop_event is None:
        stop_event = threading.Event()
    availability_topic = f"mac/{cfg['device_id']}/status"

    def on_connect(client, userdata, flags, rc):
        client.publish(availability_topic, "online", retain=True)
        if cfg["ha_discovery"]:
            for feature in FEATURES:
                for topic, payload in feature.discovery_configs(cfg, availability_topic):
                    client.publish(topic, json.dumps(payload) if payload is not None else None, retain=True)
        for feature in FEATURES:
            for topic in feature.subscribe_topics(cfg):
                client.subscribe(topic)
        for feature in FEATURES:
            if hasattr(feature, "publish_state"):
                feature.publish_state(client, cfg)

    def on_message(client, userdata, msg):
        payload = msg.payload.decode().strip()
        for feature in FEATURES:
            if feature.handle(client, cfg, msg.topic, payload):
                return

    client = mqtt.Client()
    if cfg["mqtt_user"]:
        client.username_pw_set(cfg["mqtt_user"], cfg["mqtt_pass"])
    client.will_set(availability_topic, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    print(f"Брокер: {cfg['mqtt_host']}:{cfg['mqtt_port']} ({host_kind(cfg['mqtt_host'])})")
    while not stop_event.is_set():
        try:
            client.connect(cfg["mqtt_host"], cfg["mqtt_port"], keepalive=30)
            break
        except OSError as e:
            print(f"Не удалось подключиться ({e}), повтор через 5с")
            stop_event.wait(5)
    if stop_event.is_set():
        return
    client.loop_start()

    poll_state = {f: f.INITIAL_POLL_STATE for f in FEATURES if hasattr(f, "poll")}
    try:
        while not stop_event.is_set():
            for feature, state in poll_state.items():
                poll_state[feature] = feature.poll(client, cfg, state)
            stop_event.wait(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(availability_topic, "offline", retain=True)
        client.loop_stop()
        client.disconnect()
