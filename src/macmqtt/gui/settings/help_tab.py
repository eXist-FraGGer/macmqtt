from AppKit import NSColor, NSFont, NSLineBreakByWordWrapping, NSMakeRect, NSView

from ...helpers import hass, sprut
from . import widgets
from .constants import BTN_H, PAD


def build(controller, w, h):
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    inner_w = w - PAD * 2

    y = h - PAD - 18
    view.addSubview_(widgets.label(NSMakeRect(PAD, y, inner_w, 18), "Home Assistant", bold=True))

    y -= 8 + 32
    hint = widgets.label(
        NSMakeRect(PAD, y, inner_w, 32),
        "Готовит YAML под текущий Device ID и копирует его в буфер обмена — вставь в свою структуру конфига HA.",
    )
    hint.setTextColor_(NSColor.secondaryLabelColor())
    hint.setFont_(NSFont.systemFontOfSize_(11))
    hint.cell().setWraps_(True)
    hint.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    view.addSubview_(hint)

    y -= 10 + BTN_H
    view.addSubview_(
        widgets.button(
            NSMakeRect(PAD, y, inner_w, BTN_H),
            "Сгенерировать конфиг (плеер + сенсор)",
            controller,
            "generateHaConfig:",
        )
    )

    y -= 8 + BTN_H
    view.addSubview_(
        widgets.button(
            NSMakeRect(PAD, y, inner_w, BTN_H),
            "Сгенерировать Yandex Smart Home",
            controller,
            "generateYandexConfig:",
        )
    )

    y -= 20 + 18
    view.addSubview_(widgets.label(NSMakeRect(PAD, y, inner_w, 18), "Sprut.hub (Beta)", bold=True))

    y -= 8 + 32
    sprut_hint = widgets.label(
        NSMakeRect(PAD, y, inner_w, 32),
        "Подтверждено частично — мьют по вики хаба, громкость по аналогии с HomeKit. Детали в попапе после генерации.",
    )
    sprut_hint.setTextColor_(NSColor.secondaryLabelColor())
    sprut_hint.setFont_(NSFont.systemFontOfSize_(11))
    sprut_hint.cell().setWraps_(True)
    sprut_hint.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    view.addSubview_(sprut_hint)

    y -= 10 + BTN_H
    view.addSubview_(
        widgets.button(
            NSMakeRect(PAD, y, inner_w, BTN_H),
            "Сгенерировать Sprut.hub (Beta)",
            controller,
            "generateSprutConfig:",
        )
    )

    return view


def _current_device_id(controller):
    return str(controller.inputs["device_id"].stringValue()).strip() or "macbook"


def generate_ha_config(controller, sender):
    widgets.copy_to_clipboard(hass.generate_ha_config(_current_device_id(controller)))
    widgets.show_info_popup("Скопировано", [("YAML (template-сенсор + media_player) в буфере обмена.", False)])


def generate_yandex_config(controller, sender):
    widgets.copy_to_clipboard(hass.generate_yandex_config(_current_device_id(controller), controller.source_slots))
    widgets.show_info_popup("Скопировано", [("YAML для entity_config Yandex Smart Home в буфере обмена.", False)])


def generate_sprut_config(controller, sender):
    widgets.copy_to_clipboard(sprut.generate_sprut_template(_current_device_id(controller)))
    widgets.show_info_popup(
        "Скопировано (Beta)",
        [
            ("JSON-шаблон аксессуара в буфере обмена. Что проверено, а что нет:\n\n", False),
            ("✓ Мьют — Switch/On, подтверждено по wiki.spruthub.ru.\n", False),
            ("? Громкость — Speaker/Volume, по аналогии с HomeKit (Sprut использует его характеристики), сам не проверял.\n", False),
            ("— Запуск приложений и play/pause не включены — не нашёл подходящий тип характеристики.\n\n", False),
            (
                "Файл нужно положить в папку Custom-шаблонов MQTT на самом Sprut.hub — "
                "это не поле в UI, см. wiki.spruthub.ru. Если заработает не как ожидалось — дай знать, поправим.",
                False,
            ),
        ],
    )
