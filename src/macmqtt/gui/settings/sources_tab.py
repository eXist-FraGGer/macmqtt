import os
import subprocess

from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSAlertSecondButtonReturn,
    NSColor,
    NSFont,
    NSImage,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSOpenPanel,
    NSPopUpButton,
    NSView,
)
from Foundation import NSBundle, NSURL

from ...features import source
from ...helpers.hass import SOURCE_SLUGS
from . import widgets
from .constants import BTN_GAP, BTN_H, BTN_W, FIELD_H, PAD, SRC_ROW_H


def normalize_source(raw):
    # Defensive against config.json saved by an older version of this
    # feature (name/bundle_id only, no kind/shortcut keys yet).
    return {
        "name": raw.get("name", ""),
        "kind": raw.get("kind") or ("app" if raw.get("bundle_id") else ""),
        "bundle_id": raw.get("bundle_id", ""),
        "shortcut": raw.get("shortcut", ""),
    }


def build(controller, cfg, w, h):
    # Each slot is either "app" (features.source.activate_app() —
    # open+focus in one osascript call) or "shortcut" (a named
    # Shortcuts.app scenario).
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    inner_w = w - PAD * 2

    stored = cfg.get("sources", [])
    controller.source_slots = [
        normalize_source(stored[i]) if i < len(stored) else normalize_source({})
        for i in range(len(SOURCE_SLUGS))
    ]
    controller.source_name_fields = {}

    label_w = 95
    pick_w = 78
    clear_w = 22
    gap = 6
    name_w = inner_w - label_w - pick_w - clear_w - gap * 3

    y = h - PAD - FIELD_H
    for i in range(len(SOURCE_SLUGS)):
        view.addSubview_(widgets.label(NSMakeRect(PAD, y, label_w, FIELD_H), f"Источник {i + 1}"))

        name_field = widgets.label(NSMakeRect(PAD + label_w + gap, y, name_w, FIELD_H), "")
        name_field.setTextColor_(NSColor.secondaryLabelColor())
        name_field.setFont_(NSFont.systemFontOfSize_(11))
        name_field.cell().setLineBreakMode_(NSLineBreakByTruncatingTail)
        view.addSubview_(name_field)
        controller.source_name_fields[i] = name_field

        pick_x = PAD + label_w + gap + name_w + gap
        pick_btn = widgets.button(NSMakeRect(pick_x, y, pick_w, FIELD_H), "Выбрать…", controller, "pickSource:")
        pick_btn.setTag_(i)
        view.addSubview_(pick_btn)

        clear_btn = widgets.info_button(NSMakeRect(pick_x + pick_w + gap, y, clear_w, FIELD_H), controller, "clearSource:")
        clear_btn.setImage_(NSImage.imageWithSystemSymbolName_accessibilityDescription_("xmark.circle", None))
        clear_btn.setTag_(i)
        view.addSubview_(clear_btn)

        update_source_label(controller, i)
        y -= SRC_ROW_H

    view.addSubview_(
        widgets.button(NSMakeRect(w - PAD - BTN_W, PAD, BTN_W, BTN_H), "Сохранить", controller, "save:")
    )
    view.addSubview_(
        widgets.button(
            NSMakeRect(w - PAD - BTN_W * 2 - BTN_GAP, PAD, BTN_W, BTN_H), "Отмена", controller, "cancel:"
        )
    )
    return view


def update_source_label(controller, index):
    slot = controller.source_slots[index]
    field = controller.source_name_fields[index]
    if slot["kind"] == "app" and slot["bundle_id"]:
        field.setStringValue_(slot["name"] or slot["bundle_id"])
    elif slot["kind"] == "shortcut" and slot["shortcut"]:
        field.setStringValue_(slot["name"] or slot["shortcut"])
    else:
        field.setStringValue_("не выбрано")


def pick_source(controller, sender):
    index = sender.tag()
    alert = NSAlert.alloc().init()
    alert.setMessageText_(f"Источник {index + 1}")
    alert.setInformativeText_("Что запускать при активации?")
    alert.addButtonWithTitle_("Приложение…")
    alert.addButtonWithTitle_("Ярлык (Команды)…")
    alert.addButtonWithTitle_("Отмена")
    response = alert.runModal()
    if response == NSAlertFirstButtonReturn:
        _pick_app(controller, index)
    elif response == NSAlertSecondButtonReturn:
        _pick_shortcut(controller, index)


def _pick_app(controller, index):
    panel = NSOpenPanel.openPanel()
    panel.setCanChooseFiles_(True)
    panel.setCanChooseDirectories_(False)
    panel.setAllowsMultipleSelection_(False)
    panel.setAllowedFileTypes_(["app"])
    panel.setDirectoryURL_(NSURL.fileURLWithPath_("/Applications"))
    if panel.runModal() != 1:  # NSModalResponseOK / NSFileHandlingPanelOKButton
        return
    path = str(panel.URLs()[0].path())
    bundle = NSBundle.bundleWithPath_(path)
    bundle_id = str(bundle.bundleIdentifier()) if bundle is not None and bundle.bundleIdentifier() else ""
    if not bundle_id:
        widgets.show_info_popup("Не удалось определить bundle id", [(path, True)])
        return
    name = os.path.splitext(os.path.basename(path))[0]
    controller.source_slots[index] = {"name": name, "kind": "app", "bundle_id": bundle_id, "shortcut": ""}
    update_source_label(controller, index)


def _pick_shortcut(controller, index):
    try:
        names = source.list_shortcuts()
    except (subprocess.SubprocessError, FileNotFoundError, UnicodeDecodeError):
        names = []
    if not names:
        widgets.show_info_popup(
            "Ярлыки не найдены",
            [("В приложении «Команды» нет ни одного сценария, либо CLI shortcuts недоступен.", False)],
        )
        return

    popup = NSPopUpButton.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 26))
    popup.addItemsWithTitles_(names)
    slot = controller.source_slots[index]
    if slot["kind"] == "shortcut" and slot["shortcut"] in names:
        popup.selectItemWithTitle_(slot["shortcut"])

    alert = NSAlert.alloc().init()
    alert.setMessageText_(f"Источник {index + 1}: ярлык")
    alert.setInformativeText_("Выбери сценарий из приложения «Команды».")
    alert.setAccessoryView_(popup)
    alert.addButtonWithTitle_("Выбрать")
    alert.addButtonWithTitle_("Отмена")
    if alert.runModal() != NSAlertFirstButtonReturn:
        return
    name = str(popup.titleOfSelectedItem())
    controller.source_slots[index] = {"name": name, "kind": "shortcut", "bundle_id": "", "shortcut": name}
    update_source_label(controller, index)


def clear_source(controller, sender):
    index = sender.tag()
    controller.source_slots[index] = {"name": "", "kind": "", "bundle_id": "", "shortcut": ""}
    update_source_label(controller, index)
