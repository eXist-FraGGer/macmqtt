from AppKit import NSMakeRect, NSSecureTextField, NSSwitch, NSTextField, NSView

from ...system import login
from . import widgets
from .constants import BTN_GAP, BTN_H, BTN_W, FIELD_H, GENERAL_FIELDS, LABEL_W, PAD, ROW_H


def build(controller, cfg, w, h):
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    input_w = w - PAD * 2 - LABEL_W
    info_btn_w = 20
    y = h - PAD - FIELD_H
    for key, field_label in GENERAL_FIELDS:
        view.addSubview_(widgets.label(NSMakeRect(PAD, y, LABEL_W, FIELD_H), field_label))
        # Device ID gets an (i) button explaining what it actually
        # affects — shrink its field to make room, other rows unaffected.
        has_info = key == "device_id"
        field_w = input_w - info_btn_w - 4 if has_info else input_w
        field_cls = NSSecureTextField if key == "mqtt_pass" else NSTextField
        field = field_cls.alloc().initWithFrame_(NSMakeRect(PAD + LABEL_W, y, field_w, FIELD_H))
        field.setStringValue_(str(cfg.get(key, "")))
        view.addSubview_(field)
        controller.inputs[key] = field
        if has_info:
            info_btn = widgets.info_button(
                NSMakeRect(PAD + LABEL_W + field_w + 4, y, info_btn_w, FIELD_H),
                controller,
                "showDeviceIdInfo:",
            )
            view.addSubview_(info_btn)
        y -= ROW_H

    # Launch at login row: label on the left, native switch on the right.
    y -= 10
    view.addSubview_(widgets.label(NSMakeRect(PAD, y, w - PAD - 60, 20), "Запускать при входе в систему"))
    controller.launch_switch = NSSwitch.alloc().initWithFrame_(NSMakeRect(w - PAD - 40, y - 3, 40, 24))
    controller.launch_switch.setState_(1 if login.launch_at_login_enabled() else 0)
    controller.launch_switch.setTarget_(controller)
    controller.launch_switch.setAction_("toggleLaunchAtLogin:")
    view.addSubview_(controller.launch_switch)

    # Hide menu-bar icon row — applies immediately on toggle (not
    # gated behind Save), same as launch-at-login above: waiting for
    # Save to hide the only way to reach Settings would be confusing.
    y -= ROW_H
    view.addSubview_(widgets.label(NSMakeRect(PAD, y, w - PAD - 60, 20), "Скрыть иконку в трее"))
    controller.hide_icon_switch = NSSwitch.alloc().initWithFrame_(NSMakeRect(w - PAD - 40, y - 3, 40, 24))
    controller.hide_icon_switch.setState_(1 if cfg.get("hide_menu_bar_icon") else 0)
    controller.hide_icon_switch.setTarget_(controller)
    controller.hide_icon_switch.setAction_("toggleMenuBarIcon:")
    view.addSubview_(controller.hide_icon_switch)

    # Save/Cancel only make sense on this section (they act on these fields).
    view.addSubview_(
        widgets.button(NSMakeRect(w - PAD - BTN_W, PAD, BTN_W, BTN_H), "Сохранить", controller, "save:")
    )
    view.addSubview_(
        widgets.button(
            NSMakeRect(w - PAD - BTN_W * 2 - BTN_GAP, PAD, BTN_W, BTN_H), "Отмена", controller, "cancel:"
        )
    )
    return view


def toggle_launch_at_login(controller, sender):
    login.set_launch_at_login(sender.state() == 1)


def toggle_menu_bar_icon(controller, sender):
    controller.on_toggle_icon(sender.state() == 1)


def show_device_id_info(controller, sender):
    widgets.show_info_popup(
        "Device ID",
        [
            ("Влияет на две вещи:\n\n", False),
            ("1. MQTT-топики бриджа:\n", False),
            ("mac/<device_id>/volume/set\n\n", True),
            ("2. Технический ID сущностей в HA:\n", False),
            ("unique_id: <device_id>_volume\n\n", True),
            (
                'Имя устройства в HA ("MacBook") в код зашито отдельной '
                "строкой и от Device ID не зависит — сменишь ID, имя не изменится.",
                False,
            ),
        ],
    )
