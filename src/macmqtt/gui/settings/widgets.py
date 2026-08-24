import importlib.metadata

import objc
from AppKit import (
    NSAlert,
    NSBackgroundColorAttributeName,
    NSBezierPath,
    NSButton,
    NSColor,
    NSCompositingOperationSourceAtop,
    NSCompositingOperationSourceOver,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSImage,
    NSMakeRect,
    NSPasteboard,
    NSPasteboardTypeString,
    NSRectFillUsingOperation,
    NSStringDrawingUsesFontLeading,
    NSStringDrawingUsesLineFragmentOrigin,
    NSTextAlignmentCenter,
    NSTextField,
    NSTextView,
    NSView,
)
from Foundation import NSAttributedString, NSMutableAttributedString, NSString

import macmqtt

from .constants import ROW_ICON_SIZE, ROW_ICON_TEXT_GAP, ROW_INSET


def tinted_image(image, color):
    # SF Symbol images draw plain black via drawInRect_ unless recolored —
    # this is the standard NSImage tint recipe: draw the image, then fill
    # the color with sourceAtop so it only recolors already-opaque pixels.
    size = image.size()
    tinted = NSImage.alloc().initWithSize_(size)
    tinted.lockFocus()
    image.drawAtPoint_fromRect_operation_fraction_(
        (0, 0), NSMakeRect(0, 0, size.width, size.height), NSCompositingOperationSourceOver, 1.0
    )
    color.set()
    NSRectFillUsingOperation(NSMakeRect(0, 0, size.width, size.height), NSCompositingOperationSourceAtop)
    tinted.unlockFocus()
    return tinted


def label(frame, text, bold=False, center=False):
    lbl = NSTextField.alloc().initWithFrame_(frame)
    lbl.setStringValue_(text)
    lbl.setBezeled_(False)
    lbl.setDrawsBackground_(False)
    lbl.setEditable_(False)
    lbl.setSelectable_(False)
    if bold:
        lbl.setFont_(NSFont.boldSystemFontOfSize_(15))
    if center:
        lbl.setAlignment_(NSTextAlignmentCenter)
    return lbl


def button(frame, title, target, action):
    btn = NSButton.alloc().initWithFrame_(frame)
    btn.setTitle_(title)
    btn.setBezelStyle_(1)
    btn.setTarget_(target)
    btn.setAction_(action)
    return btn


def info_button(frame, target, action):
    # A round (i) button — the standard macOS "more info" affordance.
    btn = NSButton.alloc().initWithFrame_(frame)
    btn.setImage_(NSImage.imageWithSystemSymbolName_accessibilityDescription_("info.circle", None))
    btn.setBezelStyle_(1)
    btn.setBordered_(False)
    btn.setTarget_(target)
    btn.setAction_(action)
    return btn


def rich_text(segments):
    # segments: list of (text, is_code). Code runs get a monospace font
    # and a faint background so they read as a formatted code block.
    result = NSMutableAttributedString.alloc().init()
    regular_font = NSFont.systemFontOfSize_(12)
    mono_font = NSFont.userFixedPitchFontOfSize_(11)
    for text, is_code in segments:
        attrs = {
            NSFontAttributeName: mono_font if is_code else regular_font,
            NSForegroundColorAttributeName: NSColor.labelColor(),
        }
        if is_code:
            attrs[NSBackgroundColorAttributeName] = NSColor.controlColor()
        run = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
        result.appendAttributedString_(run)
    return result


def show_info_popup(title, segments, width=360):
    attributed = rich_text(segments)
    options = NSStringDrawingUsesLineFragmentOrigin | NSStringDrawingUsesFontLeading
    bounds = attributed.boundingRectWithSize_options_((width, 10000), options)
    text_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, width, bounds.size.height + 8))
    text_view.setEditable_(False)
    text_view.setDrawsBackground_(False)
    text_view.textStorage().setAttributedString_(attributed)

    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setAccessoryView_(text_view)
    alert.addButtonWithTitle_("Понятно")
    alert.runModal()


def copy_to_clipboard(text):
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, NSPasteboardTypeString)


def version():
    # importlib.metadata can't find package metadata inside the bundled
    # .app (no egg-info/dist-info there) — fall back to the hardcoded one.
    try:
        return importlib.metadata.version("macmqtt")
    except importlib.metadata.PackageNotFoundError:
        return macmqtt.__version__


class SidebarRow(NSView):
    """Hand-drawn sidebar row: exact pixel control over icon/text padding,
    since NSButton's automatic content layout does not give reliable insets.
    """

    def initWithFrame_identifier_label_symbol_controller_(self, frame, identifier, label_text, symbol_name, controller):
        self = objc.super(SidebarRow, self).initWithFrame_(frame)
        if self is None:
            return None
        self.row_identifier = identifier
        self.row_label = NSString.stringWithString_(label_text)
        raw_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol_name, None)
        # SF Symbol images draw plain black via drawInRect_ otherwise —
        # tint once here (not per-frame) to match the label's text color.
        self.row_image = tinted_image(raw_image, NSColor.labelColor()) if raw_image is not None else None
        self.row_controller = controller
        self.row_selected = False
        return self

    def drawRect_(self, rect):
        bounds = self.bounds()

        if self.row_selected:
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bounds, 6, 6)
            NSColor.controlColor().setFill()
            path.fill()

        icon_y = (bounds.size.height - ROW_ICON_SIZE) / 2
        if self.row_image is not None:
            self.row_image.drawInRect_(NSMakeRect(ROW_INSET, icon_y, ROW_ICON_SIZE, ROW_ICON_SIZE))

        text_x = ROW_INSET + ROW_ICON_SIZE + ROW_ICON_TEXT_GAP
        font = NSFont.boldSystemFontOfSize_(13) if self.row_selected else NSFont.systemFontOfSize_(13)
        attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: NSColor.labelColor()}
        # font.pointSize() is not the real rendered glyph height (ascender +
        # descender + leading) — that mismatch is what threw off centering
        # before. Measure the actual size instead of assuming it.
        text_size = self.row_label.sizeWithAttributes_(attrs)
        text_y = (bounds.size.height - text_size.height) / 2
        self.row_label.drawAtPoint_withAttributes_((text_x, text_y), attrs)

    def mouseDown_(self, event):
        self.row_controller.selectSidebarRow_(self)

    @objc.python_method
    def set_selected(self, selected):
        self.row_selected = selected
        self.setNeedsDisplay_(True)
