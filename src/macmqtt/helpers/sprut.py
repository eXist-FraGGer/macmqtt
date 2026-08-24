# Beta: Sprut.hub has no MQTT auto-discovery like HA — a device is
# recognized by matching a custom accessory template (JSON file on the
# hub's own filesystem) against retained topics via regex. Verified from
# wiki.spruthub.ru examples: Switch/On (mute) is a confirmed-working
# pattern. Speaker/Volume is inferred by analogy (Sprut's characteristic
# names mirror Apple HomeKit's HAP spec, which does define Speaker/Volume)
# but NOT confirmed against Sprut's own registry — flagged to the user in
# settings_window's popup, not silently presented as fact.
import json

from ..features.sound import topics as sound_topics


def generate_sprut_template(device_id):
    t = sound_topics({"device_id": device_id})
    template = {
        "name": "MacBook",
        "manufacturer": "Apple",
        "model": "macmqtt",
        "modelId": f"mac/{device_id}/(.*)",
        "services": [
            {
                "type": "Switch",
                "characteristics": [
                    {
                        "type": "On",
                        "link": [
                            {
                                "type": "String",
                                "topicGet": t["mute_state"],
                                "topicSet": t["mute_set"],
                                "map": {"false": "OFF", "true": "ON"},
                            }
                        ],
                    }
                ],
            },
            {
                "type": "Speaker",
                "characteristics": [
                    {
                        "type": "Volume",
                        "link": [
                            {
                                "type": "Double",
                                "topicGet": t["volume_state"],
                                "topicSet": t["volume_set"],
                            }
                        ],
                    }
                ],
            },
        ],
    }
    return json.dumps(template, indent=2, ensure_ascii=False)
