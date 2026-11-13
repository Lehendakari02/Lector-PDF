"""Light and dark appearance: the colours and the look of every control.

The colours are set by the program itself, not left to Windows, so the window
looks the same on every Windows version and the contrast is known and tested.

``Colours`` holds the few named colours of the design. The Qt palette and the
style sheet are both built from them, and the widgets that paint themselves
(the page view, the icons, the result lists) read them through ``colours()``.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

THEME_SETTING = "tema"
PAPER_SETTING = "papel"
# Small pictures the style sheet needs as files (drawn by packaging/make_images.py).
_IMAGES = Path(__file__).resolve().parents[1] / "recursos" / "interfaz"


class Theme(Enum):
    """The value is what is stored in the settings file."""

    SYSTEM = "sistema"
    LIGHT = "claro"
    DARK = "oscuro"

    @classmethod
    def from_setting(cls, value: object) -> "Theme":
        return next((theme for theme in cls if theme.value == value), cls.SYSTEM)


class Paper(Enum):
    """The tone of the pages on screen. It never changes the PDF nor what is printed.

    The value is what is stored in the settings file.
    """

    WHITE = "blanco"  # as the document is
    SEPIA = "sepia"  # warm paper, easier on the eyes for long hours
    NIGHT = "noche"  # dark paper with light letters

    @classmethod
    def from_setting(cls, value: object) -> "Paper":
        return next((paper for paper in cls if paper.value == value), cls.WHITE)


# Sepia: every colour of the page is multiplied by this warm tone.
SEPIA_TONE = "#f6ecd4"
# Night: the page is inverted, then black is lifted to this dark grey and white
# is lowered to this soft grey, so the contrast does not tire the eyes.
NIGHT_PAPER = "#1e2025"
NIGHT_INK = "#d9dbe0"


@dataclass(frozen=True)
class Colours:
    """The named colours of one appearance (light or dark)."""

    dark: bool
    window: str  # behind the bars and panels
    surface: str  # tool bar, panels, text boxes, cards
    hover: str  # a control under the mouse
    border: str
    text: str
    muted: str  # secondary text
    disabled: str
    accent: str  # the colour of the program: selected mode, main buttons
    accent_hover: str
    on_accent: str  # text on top of the accent colour
    accent_soft: str  # selected row, pressed button
    canvas: str  # behind the pages of the document
    scroll: str  # scroll bar handle
    danger: str
    tooltip: str
    on_tooltip: str


LIGHT = Colours(
    dark=False,
    window="#f5f6f8",
    surface="#ffffff",
    hover="#eaecf1",
    border="#dde0e7",
    text="#1b1d23",
    muted="#5b6272",
    disabled="#9a9fab",
    accent="#3d4fd0",
    accent_hover="#3040b4",
    on_accent="#ffffff",
    accent_soft="#e5e8fb",
    canvas="#e3e6ec",
    scroll="#c3c7d1",
    danger="#b00020",
    tooltip="#262a33",
    on_tooltip="#ffffff",
)
DARK = Colours(
    dark=True,
    window="#1c1e23",
    surface="#25282f",
    hover="#31353e",
    border="#383c47",
    text="#eceef2",
    muted="#a6adbb",
    disabled="#6f7582",
    accent="#9aa9ff",
    accent_hover="#b3beff",
    on_accent="#10143a",
    accent_soft="#2e3459",
    canvas="#121317",
    scroll="#4a4f5c",
    danger="#ff8a80",
    tooltip="#3a3f4b",
    on_tooltip="#ffffff",
)

# The yellow of a highlighter pen: the second colour of the logo.
MARKER = "#ffd43b"

_current = LIGHT
_paper = Paper.WHITE


def colours() -> Colours:
    """The colours in use right now."""
    return _current


def paper() -> Paper:
    """The tone of the pages in use right now."""
    return _paper


def set_paper(tone: Paper) -> None:
    global _paper
    _paper = tone


Role = QPalette.ColorRole


def build_palette(dark: bool) -> QPalette:
    c = DARK if dark else LIGHT
    roles = {
        Role.Window: c.window,
        Role.WindowText: c.text,
        Role.Base: c.surface,
        Role.AlternateBase: c.window,
        Role.Text: c.text,
        Role.Button: c.surface,
        Role.ButtonText: c.text,
        Role.ToolTipBase: c.tooltip,
        Role.ToolTipText: c.on_tooltip,
        Role.PlaceholderText: c.muted,
        Role.Highlight: c.accent,
        Role.HighlightedText: c.on_accent,
        Role.Link: c.accent,
        Role.BrightText: c.danger,
    }
    palette = QPalette()
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    for role in (Role.WindowText, Role.Text, Role.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c.disabled))
    return palette


def build_style_sheet(c: Colours) -> str:
    """The look of every control, written once for the whole program."""
    tick = (_IMAGES / ("marca-oscura.png" if c.dark else "marca-clara.png")).as_posix()
    arrow = (_IMAGES / ("flecha-oscura.png" if c.dark else "flecha-clara.png")).as_posix()
    return f"""
QWidget {{ font-size: 10pt; }}
QMainWindow, QDialog {{ background: {c.window}; }}
QToolTip {{
    background: {c.tooltip}; color: {c.on_tooltip};
    border: 1px solid {c.tooltip}; padding: 5px 8px;
}}

/* ---- menus ---- */
QMenuBar {{ background: {c.window}; padding: 3px 6px 0 6px; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: 6px; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ background: {c.hover}; }}
QMenu {{ background: {c.surface}; border: 1px solid {c.border}; padding: 5px; }}
QMenu::item {{ padding: 7px 26px 7px 26px; border-radius: 5px; }}
QMenu::item:selected {{ background: {c.accent_soft}; color: {c.text}; }}
QMenu::item:disabled {{ color: {c.disabled}; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: 5px 8px; }}

/* ---- the bar with the modes ---- */
QToolBar {{ border: none; }}
QToolBar#modeBar {{ background: {c.window}; padding: 3px 6px 4px 6px; }}
QTabBar#modeTabs {{ background: transparent; }}
QTabBar#modeTabs::tab {{
    background: transparent; color: {c.muted}; font-weight: 600;
    border: none; border-radius: 9px;
    padding: 5px 14px 5px 10px; margin: 0 3px 0 0; min-height: 20px;
}}
QTabBar#modeTabs::tab:hover {{ background: {c.hover}; color: {c.text}; }}
QTabBar#modeTabs::tab:selected {{ background: {c.accent}; color: {c.on_accent}; }}
QPushButton#finderButton {{
    background: {c.surface}; color: {c.muted};
    border: 1px solid {c.border}; border-radius: 9px;
    padding: 0 12px 0 10px; text-align: left;
}}
QToolButton#menuButton {{
    background: transparent; color: {c.text}; font-weight: 600;
    border: 1px solid transparent; border-radius: 9px; padding: 0 10px 0 8px;
}}
QToolButton#menuButton:hover {{ background: {c.hover}; }}
QToolButton#menuButton:focus {{ border-color: {c.accent}; }}
QToolButton#menuButton::menu-indicator {{ image: none; }}
QLineEdit#topSearch {{ border-radius: 9px; padding: 0 8px; min-height: 30px; }}
QPushButton#finderButton:hover {{ border-color: {c.accent}; color: {c.text}; }}

/* ---- the tools of each mode ---- */
QToolBar[tools="true"] {{
    background: {c.surface};
    border-top: 1px solid {c.border}; border-bottom: 1px solid {c.border};
    padding: 1px 8px; spacing: 1px;
}}
QToolBar[tools="true"] QToolButton {{
    background: transparent; color: {c.text}; font-size: 9pt;
    border: 2px solid transparent; border-radius: 8px; padding: 2px 3px 1px 3px;
}}
QToolBar[tools="true"] QToolButton[pending="true"] {{ color: {c.muted}; }}
QToolBar[tools="true"] QToolButton:hover {{ background: {c.hover}; }}
QToolBar[tools="true"] QToolButton:pressed {{ background: {c.accent_soft}; }}
QToolBar[tools="true"] QToolButton:focus {{ border-color: {c.accent}; }}
QToolBar[tools="true"]::separator {{ background: {c.border}; width: 1px; margin: 8px 5px; }}

/* ---- buttons ---- */
QPushButton {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: 8px; padding: 7px 16px;
}}
QPushButton:hover {{ background: {c.hover}; }}
QPushButton:pressed {{ background: {c.accent_soft}; }}
QPushButton:focus {{ border-color: {c.accent}; }}
QPushButton:disabled {{ color: {c.disabled}; }}
QPushButton:default, QPushButton#primaryButton {{
    background: {c.accent}; color: {c.on_accent}; border-color: {c.accent}; font-weight: 600;
}}
QPushButton:default:hover, QPushButton#primaryButton:hover {{
    background: {c.accent_hover}; border-color: {c.accent_hover};
}}
QPushButton:default:focus, QPushButton#primaryButton:focus {{ border: 2px solid {c.text}; }}
QPushButton:default:disabled {{
    background: {c.hover}; color: {c.disabled}; border-color: {c.border};
}}
QPushButton#primaryButton {{ font-size: 11pt; padding: 11px 26px; border-radius: 10px; }}
QToolButton#iconButton {{
    background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 6px;
}}
QToolButton#iconButton:hover {{ background: {c.hover}; }}
QToolButton#iconButton:pressed {{ background: {c.accent_soft}; }}
QToolButton#iconButton:focus {{ border-color: {c.accent}; }}

/* ---- text boxes and lists ---- */
QLineEdit, QPlainTextEdit {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: 8px; padding: 6px 8px;
    selection-background-color: {c.accent}; selection-color: {c.on_accent};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {c.accent}; }}
QListWidget {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: 8px; padding: 4px; outline: none;
}}
QListWidget::item {{ border-radius: 6px; padding: 7px 8px; }}
QListWidget::item:hover {{ background: {c.hover}; }}
QListWidget::item:selected {{ background: {c.accent_soft}; color: {c.text}; }}
QListWidget::item:disabled {{ color: {c.disabled}; }}
QCheckBox {{ spacing: 8px; padding: 3px 0; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; background: {c.surface};
    border: 1px solid {c.muted}; border-radius: 5px;
}}
QCheckBox::indicator:hover, QCheckBox::indicator:focus {{ border-color: {c.accent}; }}
QCheckBox::indicator:checked {{
    background: {c.accent}; border-color: {c.accent}; image: url("{tick}");
}}

QSpinBox {{ min-height: 30px; padding: 0 6px; }}
QRadioButton {{ spacing: 8px; padding: 3px 0; }}
QProgressBar {{
    background: {c.hover}; border: none; border-radius: 5px; height: 10px; text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {c.accent}; border-radius: 5px; }}
QComboBox {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: 8px; padding: 6px 10px; min-height: 22px;
}}
QComboBox:hover {{ background: {c.hover}; }}
QComboBox:focus {{ border-color: {c.accent}; }}
QComboBox::drop-down {{ border: none; width: 30px; }}
QComboBox::down-arrow {{ image: url("{arrow}"); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
    selection-background-color: {c.accent_soft}; selection-color: {c.text}; outline: none;
}}
QLabel#settingsHeading {{ font-size: 11pt; font-weight: 700; padding-top: 6px; }}

/* ---- scroll bars ---- */
QScrollBar:vertical {{ background: transparent; width: 14px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 14px; margin: 0; }}
QScrollBar::handle {{ background: {c.scroll}; border-radius: 4px; margin: 3px; }}
QScrollBar::handle:vertical {{ min-height: 40px; }}
QScrollBar::handle:horizontal {{ min-width: 40px; }}
QScrollBar::handle:hover, QScrollBar::handle:pressed {{ background: {c.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- zoom control ---- */
QSlider#zoomSlider::groove:horizontal {{
    height: 4px; background: {c.border}; border-radius: 2px;
}}
QSlider#zoomSlider::sub-page:horizontal {{ background: {c.accent}; border-radius: 2px; }}
QSlider#zoomSlider::handle:horizontal {{
    background: {c.surface}; border: 2px solid {c.accent};
    width: 12px; height: 12px; margin: -6px 0; border-radius: 8px;
}}
QSlider#zoomSlider::handle:horizontal:hover {{ background: {c.accent_soft}; }}
QSlider#zoomSlider::groove:horizontal:disabled {{ background: {c.hover}; }}
QSlider#zoomSlider::sub-page:horizontal:disabled {{ background: {c.border}; }}
QSlider#zoomSlider::handle:horizontal:disabled {{ border-color: {c.border}; }}
QToolButton#zoomFigure {{
    background: transparent; color: {c.text}; font-size: 9pt; font-weight: 600;
    border: 1px solid transparent; border-radius: 7px; padding: 3px 8px;
}}
QToolButton#zoomFigure:hover {{ background: {c.hover}; }}
QToolButton#zoomFigure::menu-indicator {{ image: none; }}

/* ---- status bar ---- */
QStatusBar {{ background: {c.window}; color: {c.muted}; border-top: 1px solid {c.border}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {c.muted}; padding: 0 8px; }}
QStatusBar QToolButton#iconButton {{ padding: 2px; }}

/* ---- welcome page ---- */
QWidget#welcome {{ background: {c.canvas}; }}
QFrame#welcomeCard {{
    background: {c.surface}; border: 1px solid {c.border}; border-radius: 18px;
}}
QFrame#welcomeCard[dropping="true"] {{ border: 2px solid {c.accent}; }}
QLabel#welcomeTitle {{ font-size: 24pt; font-weight: 700; }}
QLabel#welcomeTagline {{ font-size: 11pt; color: {c.muted}; }}
QLabel#welcomeDrop {{ color: {c.muted}; }}
QLabel#keyCap {{
    background: {c.window}; color: {c.text}; font-size: 9pt; font-weight: 600;
    border: 1px solid {c.border}; border-radius: 6px; padding: 3px 8px;
}}
QLabel#keyHint {{ color: {c.muted}; font-size: 9pt; }}
QLabel#welcomeBuild {{
    background: {c.accent_soft}; color: {c.text}; font-size: 9pt;
    border-radius: 9px; padding: 3px 10px;
}}
QLabel#welcomeDetails {{ color: {c.muted}; font-size: 8pt; }}

/* ---- search panel ---- */
QWidget#searchPanel {{ background: {c.surface}; border-left: 1px solid {c.border}; }}
QWidget#sidePanel {{ background: {c.surface}; border-right: 1px solid {c.border}; }}
QWidget#sidePanel QListWidget, QWidget#sidePanel QTreeWidget {{
    border: none; padding: 0; background: {c.surface}; color: {c.text}; outline: none;
}}
QListWidget#thumbnailList::item {{ padding: 6px 2px 4px 2px; color: {c.muted}; }}
QListWidget#thumbnailList::item:selected {{ color: {c.text}; font-weight: 700; }}
QTreeWidget#outlineTree::item {{ padding: 7px 4px; border-radius: 6px; }}
QTreeWidget#outlineTree::item:hover {{ background: {c.hover}; }}
QTreeWidget#outlineTree::item:selected {{ background: {c.accent_soft}; color: {c.text}; }}
QToolButton#panelTab {{
    border: none; border-radius: 8px; padding: 4px 10px;
    color: {c.muted}; font-weight: 600; background: transparent;
}}
QToolButton#panelTab:hover {{ background: {c.hover}; color: {c.text}; }}
QToolButton#panelTab:checked {{ background: {c.accent_soft}; color: {c.accent}; }}
QLabel#panelEmpty {{ color: {c.muted}; padding: 8px; }}
QLabel#welcomeRecentTitle {{
    color: {c.muted}; font-size: 9pt; font-weight: 600; padding: 0 0 4px 8px;
}}
QPushButton#recentButton {{
    text-align: left; border: none; border-radius: 8px; padding: 6px 10px;
    background: transparent; color: {c.text};
}}
QPushButton#recentButton:hover {{ background: {c.hover}; }}
QPushButton#recentButton:focus {{ background: {c.accent_soft}; }}
QTabBar#documentTabs {{ background: {c.window}; border-bottom: 1px solid {c.border}; }}
QTabBar#documentTabs::tab {{
    background: transparent; color: {c.muted};
    border: 1px solid transparent; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
    padding: 5px 10px 5px 14px; margin: 3px 2px 0 2px; min-width: 90px; max-width: 260px;
}}
QTabBar#documentTabs::tab:hover {{ background: {c.hover}; color: {c.text}; }}
QTabBar#documentTabs::tab:selected {{
    background: {c.surface}; color: {c.text}; border-color: {c.border}; font-weight: 600;
}}
QToolButton#tabCloseButton {{
    border: none; border-radius: 6px; padding: 3px; margin-left: 6px; background: transparent;
}}
QToolButton#tabCloseButton:hover {{ background: {c.hover}; }}
QToolButton#tabCloseButton:pressed {{ background: {c.accent_soft}; }}
QSplitter#documentSplitter::handle {{ background: {c.border}; }}
QLabel#panelTitle {{ font-size: 12pt; font-weight: 700; }}
QLabel#searchStatus {{ color: {c.muted}; font-size: 9pt; }}
QWidget#searchPanel QListWidget {{ border: none; padding: 0; }}

/* ---- function finder ---- */
QDialog#commandPalette {{
    background: {c.surface}; border: 1px solid {c.border}; border-radius: 0;
}}
QLineEdit#pageEdit {{ padding: 1px 4px; margin: 0 6px; border-radius: 6px; min-height: 18px; }}
QLineEdit#paletteQuery {{
    border: none; border-bottom: 1px solid {c.border}; border-radius: 0;
    font-size: 12pt; padding: 12px 8px;
}}
QListWidget#paletteResults {{ border: none; }}
QLabel#paletteHint, QLabel#paletteEmpty {{ color: {c.muted}; font-size: 9pt; }}
QFrame#updateBanner {{
    background: {c.accent_soft}; border-bottom: 1px solid {c.border};
}}
QLabel#updateMessage {{ color: {c.text}; font-weight: 600; }}
QFrame#updateBanner QPushButton {{ padding: 4px 12px; }}
QPushButton#bannerMainButton {{
    background: {c.accent}; color: {c.on_accent}; border-color: {c.accent}; font-weight: 600;
}}
QPushButton#bannerMainButton:hover {{ background: {c.accent_hover}; }}
QLabel#dialogNote {{ color: {c.muted}; }}
QLabel#dialogError {{ color: {c.danger}; font-weight: 600; }}
"""


def system_prefers_dark() -> bool:
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def is_dark(theme: Theme) -> bool:
    return system_prefers_dark() if theme is Theme.SYSTEM else theme is Theme.DARK


def prepare_application(app: QApplication) -> None:
    """Use the same look on every Windows version."""
    app.setStyle("Fusion")


def apply_theme(theme: Theme) -> None:
    global _current
    _current = DARK if is_dark(theme) else LIGHT
    app = QApplication.instance()
    if app is not None:
        app.setPalette(build_palette(_current.dark))
        app.setStyleSheet(build_style_sheet(_current))
