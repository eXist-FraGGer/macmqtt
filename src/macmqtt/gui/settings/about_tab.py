from AppKit import NSColor, NSFont, NSImage, NSImageView, NSLineBreakByWordWrapping, NSMakeRect, NSView

from . import widgets
from .constants import APP_ICON_PATH, PAD


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

    # Pinned to the bottom, independent of the centered block above.
    copyright_lbl = widgets.label(NSMakeRect(PAD, PAD, inner_w, 14), "Copyright © eXist-FraGGer, 2026", center=True)
    copyright_lbl.setTextColor_(NSColor.tertiaryLabelColor())
    copyright_lbl.setFont_(NSFont.systemFontOfSize_(10))
    view.addSubview_(copyright_lbl)

    return view
