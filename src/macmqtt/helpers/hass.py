# Everything HA/Yandex-integration-specific lives here: the YAML text
# generators for Settings -> Помощь, and the constants describing how HA
# derives entity_id / what Yandex's mode vocabulary looks like — features/
# (the actual MQTT discovery publishers) import these from here rather
# than the other way around, so this module has no dependency on core/ or
# features/ and can't create an import cycle with either.
# %-formatting is used on purpose: the YAML itself is full of Jinja
# "{{ }}" that would need heavy escaping in an f-string.

# HA device friendly name — every discovered entity's `device` dict uses
# this, and HA glues its slug onto each entity's unique_id/name when it
# assigns the real entity_id (see entity_prefix()).
HA_DEVICE_NAME = "MacBook"

# Matches Yandex Smart Home's fixed devices.capabilities.mode vocabulary
# (input_source: one..ten) exactly — one Source slot per slug.
SOURCE_SLUGS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def ha_device(device_id):
    """The MQTT discovery `device` block shared by every entity we publish,
    so HA groups them all under one device card instead of one per entity."""
    return {"identifiers": [f"{device_id}_bridge"], "name": HA_DEVICE_NAME, "manufacturer": "Apple"}


_TEMPLATE_YAML = '''\
# templates/%(device_id)s_volume.yaml — put in templates/, needs
# `template: !include_dir_merge_list templates/` in configuration.yaml.
- sensor:
    - name: "%(display_name)s Volume Fraction"
      unique_id: %(device_id)s_volume_fraction
      # media_player.volume_level must be 0.0-1.0, not 0-100.
      state: "{{ (states('number.%(prefix)s_volume') | float(0) / 100) | round(2) }}"
'''

_MEDIA_PLAYER_YAML = '''\
# media_players/%(device_id)s.yaml — put in media_players/, needs
# `media_player: !include_dir_merge_list media_players/` in configuration.yaml.
- platform: universal
  name: %(display_name)s
  unique_id: %(device_id)s_media_player
  device_class: tv
  # Real state now (Music/Spotify/Safari/Chromium — see features/nowplaying.py),
  # not a guess: "playing"/"paused"/"idle", whichever the sensor below reports.
  state_template: "{{ states('sensor.%(prefix)s_now_playing') }}"
  # media_title/media_artist/media_album_name are NOT read through
  # `attributes:` below — Universal's own source (_child_attr, in HA core's
  # universal/media_player.py) only pulls those three from a real child
  # entity's state attributes, ignoring any override for them specifically
  # (unlike volume_level/is_volume_muted/entity_picture, which do use the
  # override and worked fine without this). Pointing active_child_template
  # at our own sensor makes Universal treat it as that child, so those
  # three finally read from its attributes too — without this, they always
  # come back empty no matter what attributes: says.
  active_child_template: "sensor.%(prefix)s_now_playing"
  attributes:
    volume_level: sensor.%(device_id)s_volume_fraction
    is_volume_muted: switch.%(prefix)s_mute
    entity_picture: sensor.%(prefix)s_now_playing|artwork
  commands:
    volume_set:
      action: number.set_value
      target:
        entity_id: number.%(prefix)s_volume
      data:
        value: "{{ (volume_level * 100) | round(0) }}"
    volume_up:
      action: button.press
      target:
        entity_id: button.%(prefix)s_volume_up
    volume_down:
      action: button.press
      target:
        entity_id: button.%(prefix)s_volume_down
    volume_mute:
      action: "{{ 'switch.turn_on' if is_volume_muted else 'switch.turn_off' }}"
      target:
        entity_id: switch.%(prefix)s_mute
    media_play:
      action: button.press
      target:
        entity_id: button.%(prefix)s_play_pause
    media_pause:
      action: button.press
      target:
        entity_id: button.%(prefix)s_play_pause
    # Universal treats this as its own command, not an automatic
    # combination of media_play/media_pause (see HA core's
    # universal/media_player.py _async_call_service — media_play_pause
    # only resolves via a real child entity's own service otherwise, which
    # we don't have) — cards/dashboards that call the single toggle
    # service (e.g. mini-media-player's main button) silently no-op
    # without this exact key.
    media_play_pause:
      action: button.press
      target:
        entity_id: button.%(prefix)s_play_pause
    media_next_track:
      action: button.press
      target:
        entity_id: button.%(prefix)s_next_track
    media_previous_track:
      action: button.press
      target:
        entity_id: button.%(prefix)s_previous_track
'''

_YANDEX_YAML = '''\
# yandex_smart_home/%(device_id)s.yaml
media_player.%(device_id)s:
  name: %(display_name)s
  type: devices.types.media_device.tv
  # Обязательно для Universal MediaPlayer — автоопределение supported_features
  # для него ненадёжно, HA/yaha-cloud docs просят перечислять руками.
  features:
    - volume_mute
    - volume_set
    - play_pause
    - next_previous_track
  custom_ranges:
    volume:
      state_entity_id: number.%(prefix)s_volume
      range:
        min: 0
        max: 100
        precision: 1
      set_value:
        action: media_player.volume_set
        target:
          entity_id: media_player.%(device_id)s
        data:
          volume_level: "{{ value / 100 }}"
      increase_value:
        action: media_player.volume_up
        target:
          entity_id: media_player.%(device_id)s
      decrease_value:
        action: media_player.volume_down
        target:
          entity_id: media_player.%(device_id)s
%(focus_modes)s'''

_FOCUS_MODE_ENTRY = '      %(slug)s: "%(slug)s"\n'

_FOCUS_MODES_BLOCK = '''\
  # Яндекс подставляет выбранный режим в set_mode как {{ mode }} — та же
  # схема, что у custom_ranges/{{ value }} выше. Не проверено на
  # реальной HA (по аналогии с value, не прямое подтверждение из доков).
  modes:
    input_source:
%(entries)s\
  custom_modes:
    input_source:
      set_mode:
        action: button.press
        target:
          entity_id: "button.%(prefix)s_source_{{ mode }}"
'''


def entity_prefix(device_id):
    # HA glues its own (fixed) device name onto each MQTT-discovered
    # entity's unique_id (which already contains device_id) — this is
    # exactly how HA derives the real entity_id, not a guess.
    return f"{HA_DEVICE_NAME.lower()}_{device_id}"


def _display_name(device_id):
    return device_id.replace("_", " ").replace("-", " ").title()


def generate_ha_config(device_id):
    prefix = entity_prefix(device_id)
    values = {
        "device_id": device_id,
        "display_name": _display_name(device_id),
        "prefix": prefix,
    }
    return _TEMPLATE_YAML % values + "\n" + (_MEDIA_PLAYER_YAML % values)


def generate_yandex_config(device_id, sources):
    prefix = entity_prefix(device_id)
    entries = "".join(
        _FOCUS_MODE_ENTRY % {"slug": slug}
        for slug, source in zip(SOURCE_SLUGS, sources)
        if source.get("bundle_id") or source.get("shortcut")
    )
    focus_modes = _FOCUS_MODES_BLOCK % {"entries": entries, "prefix": prefix} if entries else ""
    values = {
        "device_id": device_id,
        "display_name": _display_name(device_id),
        "prefix": prefix,
        "focus_modes": focus_modes,
    }
    return _YANDEX_YAML % values
