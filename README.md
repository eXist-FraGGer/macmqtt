# macmqtt — MQTT-мост для управления Mac

Громкость, мьют, play/pause/next/prev, Now Playing (заголовок/исполнитель/обложка), запуск приложений и Shortcuts — из любого MQTT-хаба (HA, Sprut.hub, Node-RED). Протокол: [PROTOCOL.md](PROTOCOL.md).

## Установка

```bash
brew tap eXist-FraGGer/macmqtt
brew install --cask macmqtt
```

Или из исходников:

```bash
python3 -m venv venv
venv/bin/pip install -e ".[build]"
scripts/build_app.sh
cp -R dist/macmqtt.app /Applications/
```

Запустить, Настройки → Общие: host/port/user/pass брокера, Device ID.

## MQTT-брокер

Любой, доступный с Mac по сети. Например Mosquitto в HA: Settings → Add-ons → Mosquitto broker.

## HA

Discovery включён по умолчанию — устройство «MacBook» появится само (Settings → Devices → MQTT).

## Yandex Smart Home

1. Настройки → Помощь → «Сгенерировать конфиг (плеер + сенсор)»
2. Настройки → Помощь → «Сгенерировать Yandex Smart Home»

Оба генератора берут текущий Device ID и Источники — при изменении сгенерировать заново.

## Доступ HA из интернета

Нужен для Alice (сам HA, не брокер). Способ — DDNS/port forward/Cloudflare Tunnel/Nabu Casa — не забота macmqtt.

## Голосовые команды

«Алиса, тише на маке», «громче», «поставь звук на маке 30», «выключи звук на маке».

Без GUI (headless, автозапуск через launchd): [ADVANCED.md](ADVANCED.md).
