"""The small panel where a note or the text of a text box is written.

It floats over the document, next to the place it belongs to. "Guardar" (or
Ctrl+Intro, or a click outside) keeps what was written; Esc leaves everything
as it was. A note made by another program can be read here, not changed.
"""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.notes import MONO, NOTE, SERIF

PANEL_WIDTH = 320
EDIT_HEIGHT = 130
# The fonts of the text boxes, as the screen has them (the PDF uses its own).
SCREEN_FAMILIES = {
    SERIF: ["Times New Roman", "Liberation Serif", "serif"],
    MONO: ["Courier New", "Liberation Mono", "monospace"],
}
SANS_FAMILIES = ["Arial", "Helvetica", "Liberation Sans", "sans-serif"]


class NotePanel(QFrame):
    """Write, change, read or remove one note or text box.

    ``saved`` carries the text to keep; ``removed`` asks to take it away;
    ``closed`` comes whenever the panel goes, whatever the reason.
    """

    saved = Signal(str)
    removed = Signal()
    closed = Signal()

    def __init__(
        self,
        kind: str,
        text: str = "",
        existing: bool = False,
        editable: bool = True,
        parent: QWidget | None = None,
        removable: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("notePanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setFixedWidth(PANEL_WIDTH)
        self.kind = kind
        self.existing = existing
        self.editable = editable
        # One of another program cannot be changed, but it can be taken away.
        self.removable = editable if removable is None else removable
        self._original = text
        self._done = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        if not editable:
            title = (
                self.tr("Nota de otro programa (se puede leer y borrar)")
                if self.removable
                else self.tr("Nota de otro programa (solo se puede leer)")
            )
        elif kind == NOTE:
            title = self.tr("Nota") if existing else self.tr("Nota nueva")
        else:
            title = self.tr("Texto") if existing else self.tr("Texto nuevo")
        self.title = QLabel(title)
        self.title.setObjectName("notePanelTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.edit = QPlainTextEdit()
        self.edit.setAccessibleName(title)
        self.edit.setPlainText(text)
        self.edit.setReadOnly(not editable)
        self.edit.setTabChangesFocus(True)
        self.edit.setFixedHeight(EDIT_HEIGHT)
        if editable:
            self.edit.setPlaceholderText(
                self.tr("Escribe la nota…")
                if kind == NOTE
                else self.tr("Escribe el texto que irá sobre la página…")
            )
        layout.addWidget(self.edit)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.remove_button = QPushButton(self.tr("Borrar"))
        self.remove_button.setToolTip(
            self.tr("Quitar la nota de la página")
            if kind == NOTE
            else self.tr("Quitar el texto de la página")
        )
        self.remove_button.setVisible(existing and self.removable)
        self.remove_button.clicked.connect(self.remove)
        row.addWidget(self.remove_button)
        row.addStretch(1)
        self.cancel_button = QPushButton(self.tr("Cancelar") if editable else self.tr("Cerrar"))
        self.cancel_button.clicked.connect(self.cancel)
        row.addWidget(self.cancel_button)
        self.save_button = QPushButton(self.tr("Guardar"))
        self.save_button.setDefault(True)
        self.save_button.setToolTip(self.tr("Guardar (Ctrl+Intro)"))
        self.save_button.setVisible(editable)
        self.save_button.clicked.connect(self.save)
        row.addWidget(self.save_button)
        layout.addLayout(row)

        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self.save)
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(self.cancel)

    def show_text_style(self, font: str, size: float, color: tuple[float, float, float]) -> None:
        """Write in the panel with the look the text will have on the page."""
        shown = QFont()
        shown.setFamilies(SCREEN_FAMILIES.get(font, SANS_FAMILIES))
        shown.setPointSizeF(max(9.0, min(20.0, size)))
        self.edit.setFont(shown)
        tone = QColor.fromRgbF(*color)
        if tone.lightnessF() < 0.75:  # a very light colour could not be read here
            self.edit.setStyleSheet(f"QPlainTextEdit {{ color: {tone.name()}; }}")

    def place_near(self, point: QPoint) -> None:
        """Next to a place of the parent, without leaving it."""
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            self.move(point)
            return
        x = min(point.x() + 14, parent.width() - self.width() - 8)
        y = min(point.y() + 14, parent.height() - self.height() - 8)
        self.move(max(8, x), max(8, y))

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

    def save(self) -> None:
        """Keep what is written. Emptied, an existing one is taken away."""
        if self._done:
            return
        if not self.editable or self.text == self._original.strip():
            self._finish()
        elif self.text:
            self._finish(self.saved, self.text)
        elif self.existing:
            self._finish(self.removed)
        else:
            self._finish()

    def remove(self) -> None:
        if not self._done and self.existing and self.removable:
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
