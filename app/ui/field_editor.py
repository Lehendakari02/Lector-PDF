"""Writing in a box of a form, on the page itself.

The editor sits exactly over the field, with letters of the size they will
have. Intro (or leaving the box) keeps what was written, Tab keeps it and goes
on to the next field, Mayús+Tab to the one before, and Esc leaves it as it was.
In a box of several lines Intro starts a new line and Ctrl+Intro keeps it.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCompleter, QFrame, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from app.core.forms import COMBO, FormField

SMALLEST_LETTER_PX = 9


class FieldEditor(QFrame):
    """``finished(text, step)``: kept (step 0, or +1/-1 to go on with Tab);
    ``cancelled``: Esc."""

    finished = Signal(str, int)
    cancelled = Signal()

    def __init__(self, field: FormField, parent: QWidget) -> None:
        super().__init__(parent)
        self.field = field
        self.setObjectName("fieldEditor")
        self._done = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if field.multiline:
            self.box: QLineEdit | QPlainTextEdit = QPlainTextEdit(field.value)
            self.box.setFrameShape(QFrame.Shape.NoFrame)
            self.box.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.box.setTabChangesFocus(True)
        else:
            self.box = QLineEdit(field.value)
            self.box.setFrame(False)
            if field.max_length:
                self.box.setMaxLength(field.max_length)
            if field.password:
                self.box.setEchoMode(QLineEdit.EchoMode.Password)
            if field.kind == COMBO and field.choices:
                completer = QCompleter(list(field.choices), self.box)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                self.box.setCompleter(completer)
        self.box.setAccessibleName(field.title)
        self.box.setToolTip(field.title)
        self.box.installEventFilter(self)
        layout.addWidget(self.box)

    @property
    def text(self) -> str:
        text = self.box.toPlainText() if isinstance(self.box, QPlainTextEdit) else self.box.text()
        if self.field.max_length:
            text = text[: self.field.max_length]
        return text

    def put(self, where: QRect, letter_px: float) -> None:
        """Over the field (``where`` in the window), letters ``letter_px`` high."""
        self.setGeometry(where)
        font = QFont(self.box.font())
        font.setPixelSize(max(SMALLEST_LETTER_PX, round(letter_px)))
        self.box.setFont(font)

    def start(self) -> None:
        self.show()
        self.raise_()
        self.box.setFocus(Qt.FocusReason.OtherFocusReason)
        if isinstance(self.box, QLineEdit):
            self.box.end(False)
        else:
            self.box.moveCursor(self.box.textCursor().MoveOperation.End)

    def finish(self, step: int = 0) -> None:
        """Keep what was written (once)."""
        if self._done:
            return
        self._done = True
        self.finished.emit(self.text, step)

    def cancel(self) -> None:
        if self._done:
            return
        self._done = True
        self.cancelled.emit()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        if watched is self.box:
            if event.type() == QEvent.Type.KeyPress:
                key, modifiers = event.key(), event.modifiers()
                if key == Qt.Key.Key_Escape:
                    popup = self.box.completer() if isinstance(self.box, QLineEdit) else None
                    if popup is not None and popup.popup().isVisible():
                        return False
                    self.cancel()
                    return True
                if key == Qt.Key.Key_Tab:
                    self.finish(+1)
                    return True
                if key == Qt.Key.Key_Backtab:
                    self.finish(-1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    multiline = isinstance(self.box, QPlainTextEdit)
                    if not multiline or modifiers & Qt.KeyboardModifier.ControlModifier:
                        self.finish(0)
                        return True
            elif event.type() == QEvent.Type.FocusOut:
                reason = event.reason()
                if reason != Qt.FocusReason.PopupFocusReason:  # the list of choices
                    self.finish(0)  # a click elsewhere keeps it
        return super().eventFilter(watched, event)
