import argparse
import getpass
import os
import sys

from .core import config as cfgmod
from .core.bridge import run
from .system import permission


def cmd_check_permissions():
    if permission.accessibility_trusted():
        print("Accessibility уже разрешена — анимация громкости будет работать.")
        return
    permission.request_accessibility()
    interpreter = os.path.realpath(sys.executable)
    print(f"Открой System Settings -> Privacy & Security -> Accessibility и включи:\n{interpreter}")
    print("(или нажми Open System Settings в появившемся диалоге). После этого перезапусти демон.")


def cmd_configure():
    cfg = cfgmod.load()
    host = input(f"MQTT host [{cfg['mqtt_host']}]: ").strip() or cfg["mqtt_host"]
    port = input(f"MQTT port [{cfg['mqtt_port']}]: ").strip() or cfg["mqtt_port"]
    user = input(f"MQTT user [{cfg['mqtt_user']}]: ").strip() or cfg["mqtt_user"]
    pw_hint = "заданный" if cfg["mqtt_pass"] else "нет"
    pw = getpass.getpass(f"MQTT password [{pw_hint}]: ") or cfg["mqtt_pass"]
    device_id = input(f"Device ID [{cfg['device_id']}]: ").strip() or cfg["device_id"]
    cfg.update(
        mqtt_host=host,
        mqtt_port=int(port),
        mqtt_user=user,
        mqtt_pass=pw,
        device_id=device_id,
    )
    cfgmod.save(cfg)
    print(f"Сохранено: {cfgmod.CONFIG_PATH}")


def main():
    parser = argparse.ArgumentParser(prog="macmqtt")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="запустить демон")
    sub.add_parser("configure", help="настроить брокер интерактивно")
    sub.add_parser("check-permissions", help="запросить Accessibility у системы")
    args = parser.parse_args()

    if args.cmd == "configure":
        cmd_configure()
        return
    if args.cmd == "check-permissions":
        cmd_check_permissions()
        return

    cfg = cfgmod.load()
    if not cfg["mqtt_host"]:
        print("Брокер не настроен. Запусти: macmqtt configure", file=sys.stderr)
        sys.exit(1)
    if not permission.accessibility_trusted():
        permission.request_accessibility()
        print("Accessibility не разрешена — тише/громче/мьют не будут работать, пока не разрешишь (диалог macOS уже показан).")
    run(cfg)


if __name__ == "__main__":
    main()
