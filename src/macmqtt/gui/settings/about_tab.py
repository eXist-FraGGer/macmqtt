from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApp,
    NSColor,
    NSFont,
    NSImage,
    NSImageView,
    NSLineBreakByWordWrapping,
    NSMakeRect,
    NSView,
)

from ...system import update
from . import widgets
from .constants import APP_ICON_PATH, BTN_H, PAD


def build(controller, w, h):
    # Centered "About" layout: icon, name, version, description —
    # vertically centered as a block, like a native macOS about panel.
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    inner_w = w - PAD * 2

    icon_size = 80
    name_h = 26
    version_h = 18
    desc_h = 34
    gaps = (14, 4, 16)  # icon->name, name->version, version->desc
    total_h = icon_size + name_h + version_h + desc_h + sum(gaps)
    top_margin = max(PAD, (h - total_h) / 2)

    y = h - top_margin - icon_size
    icon_view = NSImageView.alloc().initWithFrame_(
        NSMakeRect((w - icon_size) / 2, y, icon_size, icon_size)
    )
    icon_image = NSImage.alloc().initWithContentsOfFile_(APP_ICON_PATH)
    if icon_image is not None:
        icon_view.setImage_(icon_image)
    view.addSubview_(icon_view)

    y -= gaps[0] + name_h
    name_lbl = widgets.label(NSMakeRect(PAD, y, inner_w, name_h), "macmqtt", bold=True, center=True)
    name_lbl.setFont_(NSFont.boldSystemFontOfSize_(20))
    view.addSubview_(name_lbl)

    y -= gaps[1] + version_h
    version_lbl = widgets.label(NSMakeRect(PAD, y, inner_w, version_h), f"Версия {widgets.version()}", center=True)
    version_lbl.setTextColor_(NSColor.secondaryLabelColor())
    view.addSubview_(version_lbl)

    y -= gaps[2] + desc_h
    desc_lbl = widgets.label(
        NSMakeRect(PAD, y, inner_w, desc_h),
        "MQTT-мост для управления Mac из любого умного дома "
        "(Home Assistant, Sprut.hub и т.п.)",
        center=True,
    )
    desc_lbl.setTextColor_(NSColor.secondaryLabelColor())
    desc_lbl.setFont_(NSFont.systemFontOfSize_(11))
    desc_lbl.cell().setWraps_(True)
    desc_lbl.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    view.addSubview_(desc_lbl)

    y -= 16 + BTN_H
    btn_w = 180
    view.addSubview_(
        widgets.button(NSMakeRect((w - btn_w) / 2, y, btn_w, BTN_H), "Проверить обновление", controller, "checkUpdate:")
    )

    # Pinned to the bottom, independent of the centered block above.
    copyright_lbl = widgets.label(NSMakeRect(PAD, PAD, inner_w, 14), "Copyright © eXist-FraGGer, 2026", center=True)
    copyright_lbl.setTextColor_(NSColor.tertiaryLabelColor())
    copyright_lbl.setFont_(NSFont.systemFontOfSize_(10))
    view.addSubview_(copyright_lbl)

    return view


def check_update(controller, sender):
    try:
        latest = update.latest_version()
    except Exception:
        widgets.show_info_popup("Не удалось проверить обновление", [("Нет сети или недоступен GitHub.", False)])
        return

    current = update.current_version()
    if not update.is_newer(latest, current):
        widgets.show_info_popup("Обновлений нет", [(f"Установлена последняя версия {current}.", False)])
        return

    if update.brew_path() is None:
        # Installed via manually-downloaded .app, not brew — nothing to
        # script safely, just point at the same download page as before.
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"Доступна версия {latest}")
        alert.setInformativeText_(f"Установлена {current}. Homebrew не найден — открыть страницу релиза?")
        alert.addButtonWithTitle_("Открыть")
        alert.addButtonWithTitle_("Отмена")
        if alert.runModal() == NSAlertFirstButtonReturn:
            update.open_release_page()
        return

    alert = NSAlert.alloc().init()
    alert.setMessageText_(f"Доступна версия {latest}")
    alert.setInformativeText_(f"Установлена {current}. Обновить через brew? Приложение перезапустится само.")
    alert.addButtonWithTitle_("Обновить")
    alert.addButtonWithTitle_("Отмена")
    if alert.runModal() != NSAlertFirstButtonReturn:
        return

    update.upgrade_and_relaunch()
    NSApp.terminate_(None)
