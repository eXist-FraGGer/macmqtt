import objc
from AppKit import (
    NSApp,
    NSApplicationActivationPolicyAccessory,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSBox,
    NSBoxSeparator,
    NSMakeRect,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskTitled,
    NSView,
)
from Foundation import NSObject

from . import about_tab, general_tab, help_tab, permissions_tab, sources_tab, widgets
from .constants import CONTENT_W, PAD, SECTIONS, SIDEBAR_MARGIN, SIDEBAR_ROW_H, SIDEBAR_W, WIN_H, WIN_W


class SettingsController(NSObject):
    """Thin hub: owns the window/sidebar/section-swap machinery, storage
    shared across tabs (inputs, source_slots, status_dots...), and the
    AppKit action selectors — each just forwards to the owning tab module
    (general_tab.py, sources_tab.py, ...), which also builds that tab's
    view. Keeps this file from re-growing into the 800-line one it used
    to be: layout lives in the tab modules, this only wires them together.
    """

    def initWithConfigAndCallback_(self, args):
        self = objc.super(SettingsController, self).init()
        if self is None:
            return None
        cfg, self.on_save, self.on_toggle_icon = args
        self.cfg = cfg
        self.inputs = {}
        # group index -> status dot view, updated after each permission check
        self.status_dots = {}
        self.sidebar_rows = {}
        self.sections = {}
        self._build(cfg)
        return self

    @objc.python_method
    def _build(self, cfg):
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIN_W, WIN_H), style, NSBackingStoreBuffered, False
        )
        window.setTitle_("Настройки macmqtt")
        window.center()
        # Keep window alive after close() so gui/app.py can reuse it (singleton pattern).
        window.setReleasedWhenClosed_(False)
        # Delegate catches the close (any path: red button, Save, Cancel) so
        # the Dock icon can be dropped again — see windowWillClose_.
        window.setDelegate_(self)
        content = window.contentView()

        self._build_sidebar(content)

        # Vertical divider so the sidebar doesn't visually run straight into
        # the content area with no separation.
        divider = NSBox.alloc().initWithFrame_(NSMakeRect(SIDEBAR_W, 0, 1, WIN_H))
        divider.setBoxType_(NSBoxSeparator)
        content.addSubview_(divider)

        self.content_container = NSView.alloc().initWithFrame_(
            NSMakeRect(SIDEBAR_W, 0, CONTENT_W, WIN_H)
        )
        content.addSubview_(self.content_container)

        self.sections = {
            "general": general_tab.build(self, cfg, CONTENT_W, WIN_H),
            "sources": sources_tab.build(self, cfg, CONTENT_W, WIN_H),
            "permissions": permissions_tab.build(self, CONTENT_W, WIN_H),
            "help": help_tab.build(self, CONTENT_W, WIN_H),
            "about": about_tab.build(self, CONTENT_W, WIN_H),
        }
        self._select_section("general")

        self.window = window

    @objc.python_method
    def _build_sidebar(self, content):
        y = WIN_H - PAD - SIDEBAR_ROW_H
        for identifier, section_label, symbol_name in SECTIONS:
            row = widgets.SidebarRow.alloc().initWithFrame_identifier_label_symbol_controller_(
                NSMakeRect(SIDEBAR_MARGIN, y, SIDEBAR_W - SIDEBAR_MARGIN * 2, SIDEBAR_ROW_H),
                identifier,
                section_label,
                symbol_name,
                self,
            )
            self.sidebar_rows[identifier] = row
            content.addSubview_(row)
            y -= SIDEBAR_ROW_H + 4

    @objc.python_method
    def _select_section(self, identifier):
        for view in self.content_container.subviews():
            view.removeFromSuperview()
        self.content_container.addSubview_(self.sections[identifier])
        for section_id, row in self.sidebar_rows.items():
            row.set_selected(section_id == identifier)

    def selectSidebarRow_(self, row):
        self._select_section(row.row_identifier)

    @objc.python_method
    def show(self):
        # LSUIElement apps have no Dock icon by default — grant one for as
        # long as Settings is open, like every other menu-bar utility does,
        # so Cmd+Tab/the Dock can find this window. Dropped again in
        # windowWillClose_.
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        # Activate the app first, then force the window to front.
        # Order matters: a background (menu bar only) app can lose the
        # "bring to front" race against whatever app was active before.
        NSApp.activateIgnoringOtherApps_(True)
        self.window.makeKeyAndOrderFront_(None)
        self.window.orderFrontRegardless()

    def windowWillClose_(self, notification):
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def save_(self, sender):
        values = {key: str(field.stringValue()) for key, field in self.inputs.items()}
        values["sources"] = self.source_slots
        self.window.close()
        self.on_save(values)

    def cancel_(self, sender):
        self.window.close()

    def toggleLaunchAtLogin_(self, sender):
        general_tab.toggle_launch_at_login(self, sender)

    def toggleMenuBarIcon_(self, sender):
        general_tab.toggle_menu_bar_icon(self, sender)

    def showDeviceIdInfo_(self, sender):
        general_tab.show_device_id_info(self, sender)

    def pickSource_(self, sender):
        sources_tab.pick_source(self, sender)

    def clearSource_(self, sender):
        sources_tab.clear_source(self, sender)

    def checkPermission_(self, sender):
        permissions_tab.check_permission(self, sender)

    def openSettings_(self, sender):
        permissions_tab.open_settings(self, sender)

    def generateHaConfig_(self, sender):
        help_tab.generate_ha_config(self, sender)

    def generateYandexConfig_(self, sender):
        help_tab.generate_yandex_config(self, sender)

    def generateSprutConfig_(self, sender):
        help_tab.generate_sprut_config(self, sender)

    def checkUpdate_(self, sender):
        about_tab.check_update(self, sender)
