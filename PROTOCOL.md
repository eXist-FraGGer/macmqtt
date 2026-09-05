# MQTT-протокол управления Mac

Хаб-агностичный контракт. `<id>` = `MAC_DEVICE_ID` (по умолчанию `macbook`).

| Топик                        | Направление             | Payload               | Описание                                   |
|------------------------------|-------------------------|-----------------------|---------------------------------------------|
| `mac/<id>/volume/set`        | -> бридж                | `0`-`100`             | точное значение, без анимации              |
| `mac/<id>/volume/step`       | -> бридж                | `+N`/`-N`             | тап клавиши, с анимацией                   |
| `mac/<id>/volume/state`      | <- бридж, retained      | `0`-`100`             | текущая громкость                          |
| `mac/<id>/mute/set`          | -> бридж                | `ON`/`OFF`/`true`/`1` | тап клавиши, если состояние меняется       |
| `mac/<id>/mute/toggle`       | -> бридж                | любой                 | тап клавиши                                |
| `mac/<id>/mute/state`        | <- бридж, retained      | `ON`/`OFF`            | текущий мьют                               |
| `mac/<id>/source/run`        | -> бридж                | слаг: `one`-`ten`     | запустить слот (app или Shortcut)          |
| `mac/<id>/media/play_pause`  | -> бридж                | любой                 | тап медиа-клавиши                          |
| `mac/<id>/media/next`        | -> бридж                | любой                 | тап клавиши следующего трека               |
| `mac/<id>/media/previous`    | -> бридж                | любой                 | тап клавиши предыдущего трека              |
| `mac/<id>/media/now_playing` | <- бридж, retained      | JSON                  | title/artist/album/artwork/state, см. ниже |
| `mac/<id>/status`            | <- бридж, LWT, retained | `online`/`offline`    | доступность Mac                            |

`volume/step`/`mute` — HID-эмуляция клавиш (нужен Accessibility). `volume/set` — через `osascript`, без анимации.

`media/now_playing` — определяется через AppleScript (Music.app/Spotify/Safari/Chromium-браузеры), не системный API (закрыт для сторонних процессов, см. `features/nowplaying.py`). `state`: `playing`/`idle`. Опрашивается раз в ~8с, отдельно от остального polling (может делать несколько osascript-вызовов за раз).

HA MQTT Discovery (`homeassistant/...`) — опциональный слой, флаг `HA_DISCOVERY`, другие хабы этих топиков не видят.

## Проверка вручную

```bash
mosquitto_sub -h <IP> -u <user> -P <pass> -t 'mac/#' -v
mosquitto_pub -h <IP> -u <user> -P <pass> -t 'mac/macbook/volume/set' -m 50
mosquitto_pub -h <IP> -u <user> -P <pass> -t 'mac/macbook/mute/toggle' -m 1
```

## Sprut.hub и другие хабы

Бинд напрямую на топики из таблицы, без Discovery.

## Расширение

Новый домен: `src/macmqtt/features/<имя>.py` по контракту `topics()`/`subscribe_topics()`/`discovery_configs()`/`handle()` (опционально `poll()`), зарегистрировать в `FEATURES` в [src/macmqtt/core/bridge.py](src/macmqtt/core/bridge.py).

Все сущности — в одном HA-устройстве «MacBook». Группировка по смыслу — на уровне Lovelace, не устройства.
