# Headless-режим (без GUI)

Только если GUI не нужен вообще (например безголовая машина). Для обычного использования — `.app`, см. [README.md](README.md).

```bash
python3 -m venv venv
venv/bin/pip install -e .
venv/bin/macmqtt configure
venv/bin/macmqtt run
```

Автозапуск: `scripts/install_launchd.sh`.

GUI из venv (для разработки, без пересборки `.app`): `venv/bin/macmqtt-gui`.
