import os
import threading

import objc
import rumps

from . import settings as settings_window
from ..core import config as cfgmod
from ..core.bridge import run as bridge_run

PACKAGE_DIR = os.path.dirname(os.path.dirname(__file__))
ICON_PATH = os.path.join(PACKAGE_DIR, "assets", "icon_menubar.png")

# Set by MacMqttBridgeApp.__init__ so the patched NSApp delegate below (a
# plain Cocoa delegate object, not our App instance) has a way to reach the
# running app — rumps gives the delegate a raw dict of it (self._app), not
# the instance itself, so a module-level ref is the simplest safe path.
_current_app = None


class _ReopenAwareNSApp(rumps.rumps.NSApp):
    """Patched in place of rumps' own NSApp delegate class (see below) to
    add two behaviors every other menu-bar utility already has:
    - relaunching the app (Spotlight/Finder) while it's running re-shows
      Settings instead of doing nothing (LSUIElement apps have no window
      to "reopen" otherwise);
    - applies the saved menu-bar-icon-hidden state once the status item
      actually exists (it's created inside App.run(), so __init__ is too
      early for this).
    """

    def applicationDidFinishLaunching_(self, notification):
        objc.super(_ReopenAwareNSApp, self).applicationDidFinishLaunching_(notification)
        if _current_app is not None:
            hidden = cfgmod.load().get("hide_menu_bar_icon", False)
            self.nsstatusitem.setVisible_(not hidden)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, sender, has_visible_windows):
        if _current_app is not None:
            _current_app.open_settings(None)
        return True


rumps.rumps.NSApp = _ReopenAwareNSApp


class MacMqttBridgeApp(rumps.App):
    def __init__(self):
        # icon_menubar.png is a square (padded) template silhouette — rumps
        # forces every icon into a 20x20 square, so a non-square source got
        # visibly distorted. template=True lets macOS recolor it per theme.
        super().__init__("macmqtt", icon=ICON_PATH, template=True, quit_button="Выход")
        self.status_item = rumps.MenuItem("Статус: остановлен")
        self.toggle_item = rumps.MenuItem("Запустить", callback=self.toggle)
        self.menu = [
            self.status_item,
            self.toggle_item,
            None,
            rumps.MenuItem("Настройки...", callback=self.open_settings),
        ]
        self._stop_event = None
        self._thread = None
        self._settings_controller = None

        global _current_app
        _current_app = self

        if cfgmod.load()["mqtt_host"]:
            self.start_bridge()

    def toggle(self, sender):
        if self._thread and self._thread.is_alive():
            self.stop_bridge()
        else:
            self.start_bridge()

    def start_bridge(self):
        cfg = cfgmod.load()
        if not cfg["mqtt_host"]:
            rumps.alert("Брокер не настроен", "Сначала открой Настройки и укажи host/user/pass.")
            return
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=bridge_run, args=(cfg, self._stop_event), daemon=True)
        self._thread.start()
        self.status_item.title = f"Статус: работает ({cfg['mqtt_host']})"
        self.toggle_item.title = "Остановить"

    def stop_bridge(self):
        if self._stop_event:
            self._stop_event.set()
        self.status_item.title = "Статус: остановлен"
        self.toggle_item.title = "Запустить"

    def open_settings(self, sender):
        # Singleton window: reuse the open one instead of stacking new windows.
        if self._settings_controller is not None and self._settings_controller.window.isVisible():
            self._settings_controller.show()
            return
        self._settings_controller = settings_window.show(
            cfgmod.load(), self._on_settings_saved, self._set_menu_bar_icon_hidden
        )

    def _set_menu_bar_icon_hidden(self, hidden):
        cfg = cfgmod.load()
        cfg["hide_menu_bar_icon"] = hidden
        cfgmod.save(cfg)
        nsapp = getattr(self, "_nsapp", None)
        if nsapp is not None:
            nsapp.nsstatusitem.setVisible_(not hidden)

    def _on_settings_saved(self, values):
        try:
            port = int(values["mqtt_port"].strip() or 1883)
        except ValueError:
            rumps.alert("Ошибка", "MQTT port должен быть числом.")
            return

        cfg = cfgmod.load()
        cfg.update(
            mqtt_host=values["mqtt_host"].strip(),
            mqtt_port=port,
            mqtt_user=values["mqtt_user"].strip(),
            mqtt_pass=values["mqtt_pass"],
            device_id=values["device_id"].strip() or "macbook",
            sources=values["sources"],
        )
        cfgmod.save(cfg)

        if self._thread and self._thread.is_alive():
            self.stop_bridge()
            self.start_bridge()


def main():
    MacMqttBridgeApp().run()


if __name__ == "__main__":
    main()
