"""The program's own icons and logo.

Every icon is a small line drawing written here as SVG, drawn for this
program (no icon library is used). They have no colour of their own: they are
painted with the colours of the current appearance, so they always match the
light or dark theme, and they stay sharp at any screen scale.
"""

from PySide6.QtCore import QByteArray, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.ui import theme

_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{colour}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
    "{body}</svg>"
)

_MAGNIFIER = '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'
_SHEET = (
    '<path d="M13 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9.5z"/>'
    '<path d="M13 3.5V8a1.5 1.5 0 0 0 1.5 1.5H19"/>'
)
_MARKER_PEN = '<path d="M14.5 4.5l5 5L11 18H6v-5z"/><path d="M6 18l-2.5 2.5M12 21h8"/>'
_GRID = (
    '<rect x="4" y="4" width="7" height="7" rx="1.5"/>'
    '<rect x="13" y="4" width="7" height="7" rx="1.5"/>'
    '<rect x="4" y="13" width="7" height="7" rx="1.5"/>'
    '<rect x="13" y="13" width="7" height="7" rx="1.5"/>'
)
_SIGNATURE = (
    '<path d="M3 16.5c2-4 3.5-9 5.2-9 2.2 0-.4 8.5 1.8 8.5 1.5 0 2-3.5 3.5-3.5 '
    '1.2 0 1 2.5 2.5 2.5H21"/><path d="M3 20.5h18"/>'
)

# Named after the function they stand for (see app/ui/features.py).
ICONS: dict[str, str] = {
    # Leer
    "open": (
        '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
    ),
    "search": _MAGNIFIER,
    "zoom_in": _MAGNIFIER + '<path d="M11 8.5v5M8.5 11h5"/>',
    "zoom_out": _MAGNIFIER + '<path d="M8.5 11h5"/>',
    "fit_comfortable": (
        '<rect x="5.5" y="3.5" width="13" height="17" rx="1.5"/>'
        '<path d="M9 9.5h6M9 12.5h6M9 15.5h3.5"/>'
    ),
    "fit_width": (
        '<path d="M3.5 5v14M20.5 5v14M7.5 12h9M10 9.5L7.5 12l2.5 2.5M14 9.5l2.5 2.5-2.5 2.5"/>'
    ),
    "fit_page": (
        '<rect x="6.5" y="3.5" width="11" height="17" rx="1.5"/>'
        '<path d="M2.5 7V3.5H5M21.5 7V3.5H19M2.5 17v3.5H5M21.5 17v3.5H19"/>'
    ),
    "rotate_view": ('<path d="M19.5 12a7.5 7.5 0 1 1-2.6-5.7"/><path d="M17.5 2.5v4.3h-4.3"/>'),
    "reading_mode": (
        '<path d="M12 6.5C10 5 7 4.5 3.5 5v13c3.5-.5 6.5 0 8.5 1.5 2-1.5 5-2 8.5-1.5V5'
        'C17 4.5 14 5 12 6.5z"/><path d="M12 6.5v13"/>'
    ),
    "fullscreen": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "go_to_page": (
        '<path d="M6.5 3.5h7l4 4v13h-11z"/><path d="M9.5 14h5M12.5 11.5l2.5 2.5-2.5 2.5"/>'
    ),
    "copy": (
        '<rect x="8.5" y="8.5" width="11" height="12" rx="1.5"/>'
        '<path d="M15.5 8.5v-3a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 5.5v9"/>'
        '<path d="M4.5 14.5A1.5 1.5 0 0 0 6 16h2.5"/>'
    ),
    "minus": '<path d="M6 12h12"/>',
    "plus": '<path d="M12 6v12M6 12h12"/>',
    "outline": (
        '<path d="M4 6h16M9 12h11M9 18h11"/>'
        '<circle cx="5" cy="12" r=".7"/><circle cx="5" cy="18" r=".7"/>'
    ),
    "thumbnails": _GRID,
    "print": (
        '<path d="M7 9V4h10v5"/>'
        '<path d="M7 17H6a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-1"/>'
        '<path d="M7 14h10v6H7z"/>'
    ),
    # Estudiar
    "highlight": _MARKER_PEN,
    "underline": '<path d="M7 4v7a5 5 0 0 0 10 0V4M5 20h14"/>',
    "strikeout": (
        '<path d="M4 12h16"/>'
        '<path d="M16.5 7.8C16 5.8 14.3 4.5 12 4.5c-2.5 0-4.3 1.3-4.3 3.3 0 .7.2 1.3.6 1.8"/>'
        '<path d="M7.3 16.2c.5 2 2.2 3.3 4.7 3.3 2.7 0 4.5-1.3 4.5-3.4 0-.4-.1-.8-.2-1.1"/>'
    ),
    "note": (
        '<path d="M5 4h14a1 1 0 0 1 1 1v9l-6 6H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/>'
        '<path d="M20 14h-5a1 1 0 0 0-1 1v5"/><path d="M8 9h8M8 13h3"/>'
    ),
    "text_box": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M9 9.5h6M12 9.5V15"/>',
    "draw": ('<path d="M4 20l1-4.5L16.5 4a2.1 2.1 0 0 1 3 3L8.5 19z"/><path d="M14.5 6l3.5 3.5"/>'),
    "shapes": (
        '<rect x="3.5" y="10.5" width="10" height="10" rx="1.5"/><circle cx="15.5" cy="8.5" r="5"/>'
    ),
    "eraser": (
        '<path d="M8.5 20L4 15.5a1.5 1.5 0 0 1 0-2.1l9-9a1.5 1.5 0 0 1 2.1 0l5 5a1.5 '
        '1.5 0 0 1 0 2.1L12.5 20z"/><path d="M9 9l6.5 6.5M8.5 20H20"/>'
    ),
    "bookmark": '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z"/>',
    "go_to_article": (
        '<path d="M5 4.5V11a3 3 0 0 0 3 3h11"/><path d="M15 10l4 4-4 4"/><path d="M5 19.5h6"/>'
    ),
    "ocr": (
        '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2'
        'M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M9 9.5h6M12 9.5V15"/>'
    ),
    "annotations": (
        '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M11 9h6M11 15h6"/>'
        '<circle cx="7.5" cy="9" r=".8"/><circle cx="7.5" cy="15" r=".8"/>'
    ),
    "review": (
        '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/>'
        '<circle cx="12" cy="12" r="3"/><path d="M4.5 4l15 16"/>'
    ),
    "margins": (
        '<rect x="4" y="3.5" width="16" height="17" rx="2"/>'
        '<path d="M15 4.5v15" stroke-dasharray="1.5 2.8"/><path d="M7 8h5M7 12h5M7 16h3"/>'
    ),
    "insert_sheet": _SHEET + '<path d="M12 12.5v5M9.5 15h5"/>',
    # Rellenar y firmar
    "fill_form": (
        '<rect x="4" y="3.5" width="16" height="17" rx="2"/>'
        '<rect x="7.5" y="7.5" width="9" height="3.5" rx="1"/><path d="M7.5 15h6"/>'
    ),
    "type_text": ('<path d="M4 6.5V5h10v1.5M9 5v12M7 17h4"/><path d="M17.5 9v11M16 9h3M16 20h3"/>'),
    "my_data": (
        '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10.5" r="2"/>'
        '<path d="M5.5 16c.5-1.7 1.6-2.5 3-2.5s2.5.8 3 2.5M14.5 10h4M14.5 14h3"/>'
    ),
    "stamps": (
        '<path d="M9.5 10.5V7a2.5 2.5 0 0 1 5 0v3.5"/>'
        '<path d="M9.5 10.5l-3 2.5a2 2 0 0 0-.8 1.6V16h12.6v-1.4a2 2 0 0 0-.8-1.6'
        'l-3-2.5"/><path d="M5 20h14"/>'
    ),
    "sign_drawn": _SIGNATURE,
    "sign_certificate": (
        '<circle cx="12" cy="9" r="5.5"/><path d="M8.5 13.5L7 21l5-2.5 5 2.5-1.5-7.5"/>'
        '<path d="M9.8 9l1.6 1.6 2.9-3"/>'
    ),
    "check_signatures": (
        '<path d="M12 3l7.5 3v5.5c0 4.5-3.2 8-7.5 9.5-4.3-1.5-7.5-5-7.5-9.5V6z"/>'
        '<path d="M8.8 12l2.3 2.3 4.2-4.3"/>'
    ),
    # Organizar
    "pages": (
        '<rect x="8" y="3.5" width="12" height="14" rx="2"/>'
        '<path d="M5 7.5a2 2 0 0 0-1 1.7v9.3a2 2 0 0 0 2 2h8.5a2 2 0 0 0 1.7-1"/>'
    ),
    "rotate": '<path d="M20 11.5A8 8 0 1 0 17.7 17.7"/><path d="M20 5v6.5h-6.5"/>',
    "delete_pages": (
        '<path d="M4 7h16M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l.8 11.2a2 2 0 0 0 '
        '2 1.8h5.4a2 2 0 0 0 2-1.8L17.5 7M10 11v5M14 11v5"/>'
    ),
    "merge": (
        '<path d="M5 4v3a5 5 0 0 0 5 5 2 2 0 0 1 2 2v6M19 4v3a5 5 0 0 1-5 5 2 2 0 0 0-2 2"/>'
        '<path d="M9 17.5l3 3 3-3"/>'
    ),
    "split": (
        '<path d="M12 4v4a3 3 0 0 1-3 3 4 4 0 0 0-4 4v5M12 8a3 3 0 0 0 3 3 4 4 0 0 1 4 4v5"/>'
        '<path d="M2.5 17.5L5 20l2.5-2.5M16.5 17.5L19 20l2.5-2.5"/>'
    ),
    "photo_to_pdf": (
        '<path d="M4 8.5a2 2 0 0 1 2-2h1.5l1.5-2h6l1.5 2H18a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2'
        'H6a2 2 0 0 1-2-2z"/><circle cx="12" cy="12.5" r="3.2"/>'
    ),
    "export": (
        '<path d="M12 15V4M8 8l4-4 4 4"/><path d="M5 13v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/>'
    ),
    "redact": (
        '<path d="M5 6h14M5 18.5h9"/>'
        '<rect x="4" y="9.5" width="16" height="5.5" rx="1" fill="{colour}"/>'
    ),
    "compress": '<path d="M12 3v6M9 6.5l3 3 3-3M12 21v-6M9 17.5l3-3 3 3M4 12h16"/>',
    "password": (
        '<rect x="5" y="10.5" width="14" height="9.5" rx="2"/>'
        '<path d="M8 10.5V8a4 4 0 0 1 8 0v2.5M12 14.5v2"/>'
    ),
    "compare": (
        '<rect x="3.5" y="5" width="7" height="14" rx="1.5"/>'
        '<rect x="13.5" y="5" width="7" height="14" rx="1.5"/>'
        '<path d="M6 9.5h2M6 13h2M16 9.5h2M16 13h2"/>'
    ),
    # The modes
    "mode_read": (
        '<path d="M12 6.5C10.5 5 8 4.5 4 4.5V18c4 0 6.5.5 8 2 1.5-1.5 4-2 8-2V4.5'
        'c-4 0-6.5.5-8 2zM12 6.5V20"/>'
    ),
    "mode_study": _MARKER_PEN,
    "mode_fill_sign": _SIGNATURE,
    "mode_organize": _GRID,
    # Small controls
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "previous": '<path d="M6 14.5l6-6 6 6"/>',
    "menu": '<path d="M4.5 7h15M4.5 12h15M4.5 17h15"/>',
    "more": '<path d="M6 7l5 5-5 5M13 7l5 5-5 5"/>',
    "next": '<path d="M6 9.5l6 6 6-6"/>',
}

LOGO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#5a6df0"/><stop offset="1" stop-color="#2f3da8"/>
</linearGradient></defs>
<rect x="3" y="3" width="58" height="58" rx="14" fill="url(#g)"/>
<path fill="#ffffff"
 d="M21 12.5h14.5L46 23v25.5a3 3 0 0 1-3 3H21a3 3 0 0 1-3-3v-33a3 3 0 0 1 3-3z"/>
<path d="M35.5 12.5V20a3 3 0 0 0 3 3H46z" fill="#c5ccf5"/>
<rect x="22" y="28" width="18" height="6.5" rx="1.8" fill="#ffd43b"/>
<rect x="24" y="30.3" width="14" height="2" rx="1" fill="#2f3da8"/>
<rect x="24" y="38.5" width="16" height="2" rx="1" fill="#aab2d8"/>
<rect x="24" y="43.5" width="11" height="2" rx="1" fill="#aab2d8"/>
</svg>"""

# Which colour of the appearance an icon is painted with.
TEXT, MUTED, ACCENT = "text", "muted", "accent"
PENDING = "disabled"  # a function that is not built yet

_renderers: dict[tuple[str, str], QSvgRenderer] = {}
_engines: list[QIconEngine] = []  # Qt does not keep the Python objects alive


def _renderer(name: str, colour: str) -> QSvgRenderer:
    key = (name, colour)
    if key not in _renderers:
        body = ICONS[name].replace("{colour}", colour)
        svg = _TEMPLATE.format(colour=colour, body=body)
        _renderers[key] = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    return _renderers[key]


class _LineIconEngine(QIconEngine):
    """Paints one icon with the colours in use at the moment of painting."""

    def __init__(self, name: str, role: str) -> None:
        super().__init__()
        self.name = name
        self.role = role
        _engines.append(self)

    def _colour(self, mode: QIcon.Mode, state: QIcon.State) -> str:
        c = theme.colours()
        if mode == QIcon.Mode.Disabled:
            return c.disabled
        if state == QIcon.State.On:
            return c.on_accent  # the selected mode tab
        return getattr(c, self.role)

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        _renderer(self.name, self._colour(mode, state)).render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.paint(painter, QRect(QPoint(0, 0), size), mode, state)
        painter.end()
        return pixmap

    def clone(self) -> QIconEngine:
        return _LineIconEngine(self.name, self.role)


def icon(name: str, role: str = TEXT) -> QIcon:
    """The icon called ``name``, painted with the ``role`` colour of the theme."""
    if name not in ICONS:
        raise KeyError(f"there is no icon called {name!r}")
    return QIcon(_LineIconEngine(name, role))


def has_icon(name: str) -> bool:
    return name in ICONS


def logo_pixmap(size: int, scale: float = 1.0) -> QPixmap:
    """The logo, ``size`` points wide, sharp on a screen with ``scale``."""
    pixels = max(1, round(size * scale))
    pixmap = QPixmap(pixels, pixels)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    QSvgRenderer(QByteArray(LOGO.encode("utf-8"))).render(painter, QRectF(0, 0, pixels, pixels))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def logo_icon() -> QIcon:
    """The logo in every size Windows asks for (title bar, task bar, Alt+Tab)."""
    result = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        result.addPixmap(logo_pixmap(size))
    return result
