"""Writing text straight on the page, where it will stay.

A click with the text tool puts the caret on the page itself: what is typed is
seen in its place, with its letter, size and colour, over whatever the page
has there. A small bar next to it changes the size, the weight and the colour,
and the right edge of the frame can be dragged to make the text narrower or
wider (its lines are then cut to fit). Intro starts another line; Ctrl+Intro
or a click outside keeps the text; Esc leaves everything as it was.
"""

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeySequence,
    QRegion,
    QShortcut,
    QTextBlockFormat,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QToolButton,
    QWidget,
)

from app.core import notes
from app.core.marker_styles import QUICK_COLORS, TEXT_SIZES, clamp_size, same_color
from app.core.notes import MONO, SANS, SERIF
from app.ui import theme

Color = tuple[float, float, float]

# The fonts of the text, as the screen has them. The first of each list has
# the same widths as the one of the PDF, so the lines break in the same places.
SCREEN_FAMILIES = {
    SANS: ["Arial", "Liberation Sans", "Helvetica", "sans-serif"],
    SERIF: ["Times New Roman", "Liberation Serif", "Times", "serif"],
    MONO: ["Courier New", "Liberation Mono", "Courier", "monospace"],
}
# The engine writes the first line this far below the top of the box, and the
# next ones this far apart (both, of the size of the letter).
FIRST_BASELINE = 0.8
LINE_STEP = 1.2
INSET = 5  # between the frame and the text, on the screen
GRIP_WIDTH = 10
BAR_GAP = 6
MIN_SHOWN_WIDTH = 60  # of an empty text, so that there is somewhere to see the caret
# The colours to write with that are one click away: black, blue, red, green.
INKS: tuple[Color, ...] = (QUICK_COLORS[9], QUICK_COLORS[7], QUICK_COLORS[6], QUICK_COLORS[8])


def on_paper(color: Color) -> QColor:
    """A colour of the page as the screen shows it with the tone chosen for reading."""
    tone = theme.paper()
    if tone is theme.Paper.WHITE:
        return QColor.fromRgbF(*color)
    if tone is theme.Paper.SEPIA:
        sepia = QColor(theme.SEPIA_TONE).getRgbF()
        return QColor.fromRgbF(*(part * sepia[i] for i, part in enumerate(color)))
    paper = QColor(theme.NIGHT_PAPER).getRgbF()
    ink = QColor(theme.NIGHT_INK).getRgbF()
    return QColor.fromRgbF(*((1 - part * (1 - paper[i])) * ink[i] for i, part in enumerate(color)))


class _Grip(QWidget):
    """The right edge of the frame: dragged, it changes how wide the text is."""

    dragged = Signal(int)  # how far from where it was taken, in screen units
    released = Signal()
    reset = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip(
            self.tr("Arrastra para estrechar o ensanchar el texto. Doble clic: ancho automático.")
        )
        self._from: int | None = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._from = round(event.globalPosition().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._from is not None:
            self.dragged.emit(round(event.globalPosition().x()) - self._from)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._from is not None:
            self._from = None
            self.released.emit()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._from = None
        self.reset.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.colours().accent))
        side = 8
        painter.drawRoundedRect(
            (self.width() - side) // 2, (self.height() - side) // 2, side, side, 2, 2
        )


class _Edit(QTextEdit):
    """Where the text is typed, always with the letter it will have on the page."""

    shown_font: QFont | None = None
    window_under: QWidget | None = None  # who gets the wheel

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        # The style of the program gives every widget its own letter: not this one.
        if event.type() == QEvent.Type.FontChange and self.shown_font is not None:
            self.document().setDefaultFont(self.shown_font)

    def wheelEvent(self, event) -> None:  # noqa: N802
        # The wheel is for the page underneath (the editor lives on its viewport).
        page = self.window_under
        if page is not None:
            QApplication.sendEvent(page, event)
        event.accept()


class TextEditor(QWidget):
    """Write, change or remove one text of the page, in its place.

    ``saved`` carries the text to keep (its look is in ``font``, ``size``,
    ``color``, ``bold`` and ``width``); ``removed`` asks to take it away;
    ``closed`` comes whenever the editor goes, whatever the reason;
    ``style_chosen`` tells what was changed with the bar.
    """

    saved = Signal(str)
    removed = Signal()
    closed = Signal()
    style_chosen = Signal(dict)

    kind = notes.TEXT_BOX
    editable = True

    def __init__(
        self,
        text: str = "",
        existing: bool = False,
        font: str = SANS,
        size: float = notes.TEXT_SIZE,
        color: Color = notes.TEXT_COLOR,
        bold: bool = False,
        width: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.existing = existing
        self.font_name = font
        self.size = float(size)
        self.color = tuple(color)
        self.bold = bool(bold)
        self.width_chosen = notes.clamp_box_width(width)  # in points; 0: as wide as the text
        self._original = (text, font, self.size, self.color, self.bold, self.width_chosen)
        self._done = False
        self._zoom = 1.0  # screen units per point of the page
        self._room = notes.MAX_BOX_WIDTH  # points up to the right edge of the page
        self._origin = QPoint(0, 0)  # where the box starts, in the parent
        self._drag_width = 0.0

        self.box = QFrame(self)
        self.box.setObjectName("textEditorBox")
        self.edit = _Edit(self.box)
        self.edit.setAcceptRichText(False)
        self.edit.window_under = parent
        self.edit.setObjectName("textEditorEdit")
        self.edit.setFrameShape(QFrame.Shape.NoFrame)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.edit.setTabChangesFocus(True)
        self.edit.document().setDocumentMargin(0)
        self.edit.viewport().setAutoFillBackground(False)
        self.edit.setAccessibleName(self.tr("Texto") if existing else self.tr("Texto nuevo"))
        self.edit.setAccessibleDescription(
            self.tr("Intro: otra línea. Ctrl+Intro: dejar el texto. Esc: cancelar.")
        )
        self.edit.setPlainText(text)
        self.edit.textChanged.connect(self._arrange)

        self.grip = _Grip(self)
        self.grip.dragged.connect(self._grip_dragged)
        self.grip.released.connect(self._grip_released)
        self.grip.reset.connect(lambda: self.set_width(0.0))

        self.bar = QFrame(self)
        self.bar.setObjectName("textEditorBar")
        row = QHBoxLayout(self.bar)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)
        self.smaller_button = self._button("A−", self.tr("Letra más pequeña"), self.smaller)
        row.addWidget(self.smaller_button)
        self.size_label = QLabel()
        self.size_label.setObjectName("textEditorSize")
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_label.setMinimumWidth(26)
        row.addWidget(self.size_label)
        self.bigger_button = self._button("A+", self.tr("Letra más grande"), self.bigger)
        row.addWidget(self.bigger_button)
        self.bold_button = self._button("N", self.tr("Negrita (Ctrl+B)"), self.set_bold)
        self.bold_button.setCheckable(True)
        self.bold_button.setObjectName("textEditorBold")
        row.addWidget(self.bold_button)
        row.addSpacing(4)
        self.ink_buttons: list[QToolButton] = []
        names = (self.tr("Negro"), self.tr("Azul"), self.tr("Rojo"), self.tr("Verde"))
        for ink, name in zip(INKS, names, strict=True):
            button = self._button("", name, lambda _checked=False, c=ink: self.set_color(c))
            button.setCheckable(True)
            tone = QColor.fromRgbF(*ink).name()
            button.setStyleSheet(
                f"QToolButton {{ background: {tone}; border: 3px solid {theme.colours().surface};"
                " min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px;"
                " border-radius: 12px; padding: 0; }"
                f"QToolButton:checked {{ border: 3px solid {theme.colours().accent}; }}"
            )
            row.addWidget(button)
            self.ink_buttons.append(button)
        row.addSpacing(4)
        self.remove_button = QPushButton(self.tr("Borrar"))
        self.remove_button.setToolTip(self.tr("Quitar el texto de la página"))
        self.remove_button.setVisible(existing)
        self.remove_button.clicked.connect(self.remove)
        row.addWidget(self.remove_button)
        self.save_button = QPushButton(self.tr("Hecho"))
        self.save_button.setToolTip(self.tr("Dejar el texto en la página (Ctrl+Intro)"))
        self.save_button.clicked.connect(self.save)
        row.addWidget(self.save_button)

        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            self._shortcut(keys, self.save)
        self._shortcut("Esc", self.cancel)
        self._shortcut("Ctrl+B", lambda: self.set_bold(not self.bold))
        self._show_style()

    def _button(self, text: str, tip: str, action) -> QToolButton:
        button = QToolButton(self.bar)
        button.setText(text)
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        button.clicked.connect(action)
        return button

    def _shortcut(self, keys: str, action) -> None:
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(action)

    # ---- the look ------------------------------------------------------------

    def set_size(self, size: float) -> None:
        self._restyle(size=clamp_size(size))

    def smaller(self) -> None:
        below = [step for step in TEXT_SIZES if step < self.size - 0.01]
        self.set_size(below[-1] if below else self.size)

    def bigger(self) -> None:
        above = [step for step in TEXT_SIZES if step > self.size + 0.01]
        self.set_size(above[0] if above else self.size)

    def set_bold(self, bold: bool) -> None:
        self._restyle(bold=bool(bold))

    def set_color(self, color: Color) -> None:
        self._restyle(color=tuple(color))

    def _restyle(self, **changes) -> None:
        """A change made with the bar or the keys: shown, and told."""
        told = self.give_style(**changes)
        self.edit.setFocus()
        if told:
            self.style_chosen.emit(told)

    def give_style(self, font=None, size=None, color=None, bold=None) -> dict:
        """Take another look (only what is given). Returns what really changed."""
        changed: dict = {}
        if font is not None and font in SCREEN_FAMILIES and font != self.font_name:
            self.font_name = changed["font"] = font
        if size is not None and abs(float(size) - self.size) > 0.01:
            self.size = changed["size"] = float(size)
        if color is not None and not same_color(tuple(color), self.color):
            self.color = changed["color"] = tuple(color)
        if bold is not None and bool(bold) != self.bold:
            self.bold = changed["bold"] = bool(bold)
        if changed:
            self._show_style()
        return changed

    def set_width(self, width: float) -> None:
        """How wide the text is, in points of the page; 0: as wide as its lines."""
        self.width_chosen = notes.clamp_box_width(width)
        self._arrange()
        self.edit.setFocus()

    def _show_style(self) -> None:
        number = int(self.size) if float(self.size).is_integer() else round(self.size, 1)
        self.size_label.setText(str(number))
        self.size_label.setToolTip(self.tr("Tamaño de la letra: {0}").format(number))
        self.bold_button.setChecked(self.bold)
        for ink, button in zip(INKS, self.ink_buttons, strict=True):
            button.setChecked(same_color(ink, self.color))
        self.smaller_button.setEnabled(self.size > TEXT_SIZES[0])
        self.bigger_button.setEnabled(self.size < TEXT_SIZES[-1])
        tone = on_paper(self.color)
        accent = theme.colours().accent
        paper = on_paper((1.0, 1.0, 1.0)).name() if self.existing else "transparent"
        self.box.setStyleSheet(
            f"QFrame#textEditorBox {{ background: {paper}; border: 1px dashed {accent}; }}"
            f"QTextEdit#textEditorEdit {{ background: transparent; color: {tone.name()}; }}"
        )
        self._arrange()

    def _screen_font(self) -> QFont:
        font = QFont()
        font.setFamilies(SCREEN_FAMILIES[self.font_name])
        font.setPixelSize(max(1, round(self.size * self._zoom)))
        font.setBold(self.bold)
        font.setKerning(False)  # the PDF does not bring the letters closer either
        return font

    # ---- the place -----------------------------------------------------------

    def put(self, origin: QPoint, zoom: float, room: float) -> None:
        """Where the box starts (in the parent), the zoom, and the points of
        page there are from there to its right edge."""
        self._origin, self._zoom, self._room = QPoint(origin), zoom, room
        self._arrange()

    def _lines_width(self) -> float:
        """How wide the lines are allowed to be, in points (as the page will cut them)."""
        outer = max(notes.MIN_BOX_WIDTH, self._room - notes.PAGE_MARGIN)
        if self.width_chosen > 0:
            outer = min(outer, self.width_chosen)
        return (outer - 2 * notes.PADDING - 2) / notes.WIDTH_SLACK

    def _arrange(self) -> None:
        """Size and place every piece again: after typing, a new look or a move."""
        if self._done:
            return
        font = self._screen_font()
        metrics = QFontMetricsF(font)
        step = max(1.0, LINE_STEP * self.size * self._zoom)
        self.edit.blockSignals(True)
        self.edit.shown_font = font
        self.edit.document().setDefaultFont(font)
        cursor = QTextCursor(self.edit.document())
        cursor.select(QTextCursor.SelectionType.Document)
        spacing = QTextBlockFormat()
        spacing.setLineHeight(step, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        cursor.mergeBlockFormat(spacing)
        self.edit.blockSignals(False)

        wrap = max(20, round(self._lines_width() * self._zoom))
        if self.width_chosen > 0:
            shown = wrap
        else:
            text = self.edit.toPlainText()
            longest = max((metrics.horizontalAdvance(line) for line in text.split("\n")), default=0)
            shown = min(wrap, max(MIN_SHOWN_WIDTH, round(longest + step * 0.6)))
        self.edit.setFixedWidth(shown)
        self.edit.document().setTextWidth(shown)
        lines = max(1, round(self.edit.document().size().height() / step))
        high = round(lines * step + 2)
        self.edit.setFixedHeight(high)

        # The first line of the PDF sits FIRST_BASELINE below the top of the box.
        lift = round(metrics.ascent() - FIRST_BASELINE * self.size * self._zoom)
        box = QRect(
            self._origin.x() - INSET,
            self._origin.y() - INSET - lift,
            shown + 2 * INSET,
            high + 2 * INSET,
        )
        self.bar.adjustSize()
        bar = QRect(QPoint(box.left(), box.top() - BAR_GAP - self.bar.height()), self.bar.size())
        parent = self.parentWidget()
        if parent is not None:
            if bar.top() < 4:  # no room above: below the text
                bar.moveTop(box.bottom() + 1 + BAR_GAP)
            if bar.right() > parent.width() - 4:
                bar.moveLeft(max(4, parent.width() - 4 - bar.width()))
        grip = QRect(box.right() + 1 - GRIP_WIDTH // 2, box.top(), GRIP_WIDTH, box.height())
        whole = box.united(bar).united(grip)
        self.setGeometry(whole)
        self.box.setGeometry(box.translated(-whole.topLeft()))
        self.edit.move(INSET, INSET)
        self.bar.move(bar.topLeft() - whole.topLeft())
        self.grip.setGeometry(grip.translated(-whole.topLeft()))
        self.grip.raise_()
        # Only its pieces take the clicks: between them, the page is still there.
        self.setMask(
            QRegion(self.box.geometry())
            .united(QRegion(self.bar.geometry()))
            .united(QRegion(self.grip.geometry()))
        )

    def _grip_dragged(self, moved: int) -> None:
        if not self._drag_width:
            self._drag_width = self.box.width() - 2 * INSET
        wanted = (self._drag_width + moved) / self._zoom
        # What is seen is the room of the lines; the box is a little wider.
        outer = wanted * notes.WIDTH_SLACK + 2 * notes.PADDING + 2
        self.width_chosen = notes.clamp_box_width(max(notes.MIN_BOX_WIDTH, outer))
        self._arrange()

    def _grip_released(self) -> None:
        self._drag_width = 0.0
        self.edit.setFocus()

    # ---- starting and ending ---------------------------------------------------

    def start(self) -> None:
        self.show()
        self.raise_()
        self.edit.setFocus()
        cursor = self.edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.edit.setTextCursor(cursor)

    @property
    def text(self) -> str:
        return self.edit.toPlainText().strip()

    def _look(self) -> tuple:
        return (self.text, self.font_name, self.size, self.color, self.bold, self.width_chosen)

    def save(self) -> None:
        """Keep what is written. Emptied, an existing one is taken away."""
        if self._done:
            return
        original = (self._original[0].strip(), *self._original[1:])
        if not self.text:
            self._finish(self.removed) if self.existing else self._finish()
        elif self.existing and self._look() == original:
            self._finish()
        else:
            self._finish(self.saved, self.text)

    def remove(self) -> None:
        if not self._done and self.existing:
            self._finish(self.removed)

    def cancel(self) -> None:
        if not self._done:
            self._finish()

    def _finish(self, signal=None, *values) -> None:
        self._done = True
        self.hide()
        if signal is not None:
            signal.emit(*values)
        self.closed.emit()
        self.deleteLater()
