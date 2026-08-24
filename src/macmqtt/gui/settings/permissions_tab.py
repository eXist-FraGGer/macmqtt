import subprocess

from AppKit import NSColor, NSFont, NSLineBreakByWordWrapping, NSMakeRect, NSTextField, NSView

from . import widgets
from .constants import BTN_H, DOT_FRAME_SIZE, HINT_H, PAD, PERMISSION_GROUP_H, PERMISSION_GROUPS, STATUS_DOT_SIZE


def build(controller, w, h):
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    y = h - PAD
    for index, group in enumerate(PERMISSION_GROUPS):
        y = _build_permission_group(controller, view, y, w, index, group)
    return view


def _build_permission_group(controller, view, top_y, w, index, group):
    # Row 1: title on the left, status dot right-aligned on the same baseline.
    row1_y = top_y - 18
    title_w = w - PAD * 2 - DOT_FRAME_SIZE - 8
    view.addSubview_(widgets.label(NSMakeRect(PAD, row1_y, title_w, 18), group["title"], bold=True))
    dot = _make_status_dot(w - PAD - DOT_FRAME_SIZE, row1_y - 2)
    view.addSubview_(dot)
    controller.status_dots[index] = dot
    _set_dot_granted(dot, group["is_granted"]())

    # Row 2: short explanation of what the permission is for. Two lines
    # tall and word-wrapped — a plain single-line field truncates instead
    # of wrapping, cutting the text off mid-word.
    hint_y = row1_y - 18 - HINT_H
    hint = widgets.label(NSMakeRect(PAD, hint_y, w - PAD * 2, HINT_H), group["hint"])
    hint.setTextColor_(NSColor.secondaryLabelColor())
    hint.setFont_(NSFont.systemFontOfSize_(11))
    hint.cell().setWraps_(True)
    hint.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    view.addSubview_(hint)

    # Row 3: action buttons, 12pt gap between them (HIG spacing for related controls).
    row2_y = hint_y - 10 - BTN_H
    check_btn = widgets.button(NSMakeRect(PAD, row2_y, 170, BTN_H), "Проверить разрешения", controller, "checkPermission:")
    check_btn.setTag_(index)
    view.addSubview_(check_btn)

    open_btn = widgets.button(NSMakeRect(PAD + 170 + 12, row2_y, 140, BTN_H), "Открыть настройки", controller, "openSettings:")
    open_btn.setTag_(index)
    view.addSubview_(open_btn)

    return top_y - PERMISSION_GROUP_H


def _make_status_dot(x, y):
    # Frame is wider than the glyph itself — NSTextField's own cell
    # padding can clip a glyph that exactly matches the frame size.
    dot = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, DOT_FRAME_SIZE, DOT_FRAME_SIZE))
    dot.setStringValue_("●")
    dot.setBezeled_(False)
    dot.setDrawsBackground_(False)
    dot.setEditable_(False)
    dot.setSelectable_(False)
    dot.setFont_(NSFont.systemFontOfSize_(STATUS_DOT_SIZE))
    return dot


def _set_dot_granted(dot, granted):
    dot.setTextColor_(NSColor.systemGreenColor() if granted else NSColor.systemRedColor())


def check_permission(controller, sender):
    group = PERMISSION_GROUPS[sender.tag()]
    # Read-only check, no system prompt — just refresh the dot.
    granted = group["is_granted"]()
    _set_dot_granted(controller.status_dots[sender.tag()], granted)


def open_settings(controller, sender):
    group = PERMISSION_GROUPS[sender.tag()]
    # request() (prompt: true) re-registers the app in the Accessibility
    # list and shows the native dialog if not granted yet — that dialog
    # already has its own "Open System Settings" button, so we only open
    # it ourselves when there's no dialog to do that (already granted).
    was_granted = group["is_granted"]()
    granted = group["request"]()
    if was_granted:
        subprocess.run(["open", group["settings_url"]])
    _set_dot_granted(controller.status_dots[sender.tag()], granted)
