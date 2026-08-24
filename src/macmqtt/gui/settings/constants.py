from pathlib import Path

from ...helpers.hass import SOURCE_SLUGS
from ...system import permission

GENERAL_FIELDS = (
    ("mqtt_host", "MQTT host"),
    ("mqtt_port", "MQTT port"),
    ("mqtt_user", "MQTT user"),
    ("mqtt_pass", "MQTT password"),
    ("device_id", "Device ID"),
)

# Add a dict here for each new permission group shown on the "Permissions" section.
PERMISSION_GROUPS = (
    {
        "title": "Звук",
        "hint": "Нужно для анимации громкости/мьюта (эмуляция клавиш клавиатуры).",
        "is_granted": permission.accessibility_trusted,
        "request": permission.request_accessibility,
        # Deep links straight into "Privacy & Security > Accessibility" keep
        # breaking across macOS versions/betas (Apple changes the pane id
        # without notice) — opening System Settings itself is reliable.
        "settings_url": "x-apple.systempreferences:com.apple.preference.security",
    },
)

# Sidebar sections: (identifier, label, SF Symbol name).
SECTIONS = (
    ("general", "Общие", "gearshape"),
    ("sources", "Источник", "square.grid.2x2"),
    ("permissions", "Разрешения", "lock.shield"),
    ("help", "Помощь", "questionmark.circle"),
    ("about", "О программе", "info.circle"),
)

PAD = 20
LABEL_W = 110
ROW_H = 36
FIELD_H = 24
BTN_W = 90
BTN_H = 28
BTN_GAP = 12
# 175 measured against the widest label ("О программе" = 85px at 13pt) plus
# insets/gap — anything narrower clips that text (verified via
# NSString.sizeWithAttributes_, not guessed).
SIDEBAR_W = 175
SIDEBAR_MARGIN = 14
SIDEBAR_ROW_H = 34
# Sidebar row content padding — hand-drawn (see widgets.SidebarRow), so
# these are exact pixel values, not an NSButton content layout guess.
ROW_ICON_SIZE = 16
ROW_INSET = 14
ROW_ICON_TEXT_GAP = 10
CONTENT_W = 370
WIN_W = SIDEBAR_W + CONTENT_W
# General section: fields + launch-at-login row + hide-icon row + Save/Cancel row.
_GENERAL_H = PAD + ROW_H * len(GENERAL_FIELDS) + 10 + ROW_H + BTN_GAP + BTN_H + PAD
# Sources section: one row per slot + Save/Cancel row.
SRC_ROW_H = 30
_SOURCES_H = PAD + SRC_ROW_H * len(SOURCE_SLUGS) + BTN_GAP + BTN_H + PAD
# All sections share one window height — sized to the tallest section, with
# the rest getting extra bottom whitespace.
WIN_H = max(_GENERAL_H, _SOURCES_H)

# Height one permission group (title + hint + buttons) takes on the Permissions section.
HINT_H = 30
PERMISSION_GROUP_H = 116
STATUS_DOT_SIZE = 14
DOT_FRAME_SIZE = 22

# constants.py -> settings/ -> gui/ -> macmqtt/
PACKAGE_DIR = Path(__file__).resolve().parents[2]
APP_ICON_PATH = str(PACKAGE_DIR / "assets" / "icon_app.icns")
