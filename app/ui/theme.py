"""Light and dark appearance.

The colours are set by the program itself, not left to Windows, so the window
looks the same on every Windows version and the contrast is known and tested.
"""

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

THEME_SETTING = "tema"


class Theme(Enum):
    """The value is what is stored in the settings file."""

    SYSTEM = "sistema"
    LIGHT = "claro"
    DARK = "oscuro"

    @classmethod
    def from_setting(cls, value: object) -> "Theme":
        return next((theme for theme in cls if theme.value == value), cls.SYSTEM)


Role = QPalette.ColorRole

_LIGHT = {
    Role.Window: "#f3f3f3",
    Role.WindowText: "#1b1b1b",
    Role.Base: "#ffffff",
    Role.AlternateBase: "#f0f0f0",
    Role.Text: "#1b1b1b",
    Role.Button: "#e9e9e9",
    Role.ButtonText: "#1b1b1b",
    Role.ToolTipBase: "#ffffff",
    Role.ToolTipText: "#1b1b1b",
    Role.PlaceholderText: "#5f5f5f",
    Role.Highlight: "#0b5cad",
    Role.HighlightedText: "#ffffff",
    Role.Link: "#0b5cad",
    Role.BrightText: "#b00020",
}
_DARK = {
    Role.Window: "#202124",
    Role.WindowText: "#f1f1f1",
    Role.Base: "#17181a",
    Role.AlternateBase: "#26282b",
    Role.Text: "#f1f1f1",
    Role.Button: "#33363a",
    Role.ButtonText: "#f1f1f1",
    Role.ToolTipBase: "#33363a",
    Role.ToolTipText: "#f1f1f1",
    Role.PlaceholderText: "#a8a8a8",
    Role.Highlight: "#8ab4f8",
    Role.HighlightedText: "#10151c",
    Role.Link: "#8ab4f8",
    Role.BrightText: "#ff8a80",
}
_DISABLED = {False: "#8a8a8a", True: "#7d7f82"}


def build_palette(dark: bool) -> QPalette:
    palette = QPalette()
    for role, colour in (_DARK if dark else _LIGHT).items():
        palette.setColor(role, QColor(colour))
    for role in (Role.WindowText, Role.Text, Role.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(_DISABLED[dark]))
    return palette


def system_prefers_dark() -> bool:
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def is_dark(theme: Theme) -> bool:
    return system_prefers_dark() if theme is Theme.SYSTEM else theme is Theme.DARK


def prepare_application(app: QApplication) -> None:
    """Use the same look on every Windows version."""
    app.setStyle("Fusion")


def apply_theme(theme: Theme) -> None:
    app = QApplication.instance()
    if app is not None:
        app.setPalette(build_palette(is_dark(theme)))
