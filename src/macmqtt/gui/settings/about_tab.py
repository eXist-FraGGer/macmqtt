import threading

from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApp,
    NSBackingStoreBuffered,
    NSColor,
    NSFont,
    NSImage,
    NSImageView,
    NSLineBreakByWordWrapping,
    NSMakeRect,
    NSProgressIndicator,
    NSProgressIndicatorStyleBar,
    NSView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from PyObjCTools import AppHelper

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
    alert.setInformativeText_(f"Установлена {current}. Обновить через brew?")
    alert.addButtonWithTitle_("Обновить")
    alert.addButtonWithTitle_("Отмена")
    if alert.runModal() != NSAlertFirstButtonReturn:
        return

    _run_upgrade_with_progress()


def _show_progress_window():
    # Plain feedback window, no buttons — `brew upgrade` downloads the
    # whole .app and can take a while. The old flow quit the app the
    # instant it kicked this off, so from the user's side the app just
    # vanished with no explanation until the download finished in the
    # background. This keeps the app visibly alive and working instead.
    # Closable: brew upgrade can hang well past actually finishing (known
    # issue — a helper process it spawns can hold its output pipe open,
    # see run_upgrade()'s comment), and this used to have no way out of the
    # wait at all. The red close button lets the user bail without force-
    # quitting the whole app; _upgrade_finished() checks isVisible() and
    # skips the restart prompt if they already dismissed this.
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 300, 100), NSWindowStyleMaskTitled | NSWindowStyleMaskClosable, NSBackingStoreBuffered, False
    )
    win.setTitle_("Обновление macmqtt")
    win.center()
    content = win.contentView()

    label = widgets.label(NSMakeRect(20, 55, 260, 20), "Скачивание обновления…", center=True)
    content.addSubview_(label)

    # Real byte progress during the download (update.run_upgrade downloads
    # the zip itself instead of leaving it to brew, specifically so this
    # can show an actual percentage) — switches to indeterminate for the
    # brief install step afterward, where there's nothing to measure.
    bar = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(20, 30, 260, 16))
    bar.setStyle_(NSProgressIndicatorStyleBar)
    bar.setMinValue_(0)
    bar.setMaxValue_(100)
    bar.setIndeterminate_(False)
    bar.setDoubleValue_(0)
    content.addSubview_(bar)

    # NSWindow isn't ours to subclass here — a plain dict avoids trying to
    # stash Python attributes on a bare AppKit object.
    NSApp.activateIgnoringOtherApps_(True)
    win.makeKeyAndOrderFront_(None)
    return {"window": win, "label": label, "bar": bar}


def _run_upgrade_with_progress():
    progress = _show_progress_window()

    def on_progress(done, total):
        if not total:
            return
        pct = min(100, int(done * 100 / total))
        AppHelper.callAfter(_set_progress, progress, pct)

    def on_phase(text):
        AppHelper.callAfter(_set_phase, progress, text)

    def worker():
        ok, message = update.run_upgrade(on_progress=on_progress, on_phase=on_phase)
        AppHelper.callAfter(_upgrade_finished, progress, ok, message)

    threading.Thread(target=worker, daemon=True).start()


def _set_progress(progress, pct):
    bar = progress["bar"]
    if bar.isIndeterminate():
        bar.setIndeterminate_(False)
        bar.stopAnimation_(None)
    bar.setDoubleValue_(pct)
    progress["label"].setStringValue_(f"Скачивание обновления… {pct}%")


def _set_phase(progress, text):
    progress["label"].setStringValue_(text)
    if text.startswith("Устанавл"):
        bar = progress["bar"]
        bar.setIndeterminate_(True)
        bar.startAnimation_(None)


def _upgrade_finished(progress, ok, message):
    # User may have already closed the (now closable) progress window
    # themselves while brew kept running in the background — respect that
    # instead of popping up a restart prompt for a wait they bailed on.
    win = progress["window"]
    dismissed = not win.isVisible()
    win.close()
    if dismissed:
        return
    if not ok:
        widgets.show_info_popup("Не удалось обновить", [(message or "Неизвестная ошибка.", False)])
        return

    alert = NSAlert.alloc().init()
    alert.setMessageText_("Обновление загружено")
    alert.setInformativeText_("Перезапустить macmqtt сейчас?")
    alert.addButtonWithTitle_("Перезапустить")
    alert.addButtonWithTitle_("Позже")
    if alert.runModal() == NSAlertFirstButtonReturn:
        update.relaunch()
        NSApp.terminate_(None)
