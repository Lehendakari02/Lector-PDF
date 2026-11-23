"""The reading cursor: the text of the page for screen readers and the keyboard.

A screen reader (NVDA, JAWS, Narrator) cannot read the picture of a page. Like
Adobe Reader, Edge and Chrome, the program hands it the words: an invisible
text over the page with the running text of the page in sight, which the
screen reader reads like any text of Windows (line by line with the arrows,
word by word with Ctrl, "say all"…).

It is also the "caret browsing" of Edge, Chrome and Firefox (F7): with the
arrows one moves through the text, with Shift selects it, and what is selected
is selected on the page too, so it can be highlighted with R or copied.

Moving down past the last line goes on to the next page; up past the first,
to the one before. The page follows: it scrolls to the place being read, and
a thin bar shows where.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAccessible, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QFrame, QPlainTextEdit

from app.core.reading import ReadingText, reading_text

_INVISIBLE = (
    "QPlainTextEdit { background: transparent; color: transparent; border: none;"
    " selection-background-color: transparent; selection-color: transparent; }"
)


class PageReader(QPlainTextEdit):
    """The running text of one page, read-only, on top of the view, unseen."""

    # (page, start letter, end letter): where the reader is; the same two
    # letters when nothing is selected.
    moved = Signal(int, int, int)
    # A page the reader needs the letters of.
    text_wanted = Signal(int)
    # The reader went on to another page (counting from 0).
    page_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(_INVISIBLE)
        self.setCursorWidth(0)  # the view draws where it is, on the page
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.wanted = False  # turned on (F7, or with a screen reader)
        self.page = -1
        self.page_count = 0
        self.reading = ReadingText()
        self._source = None  # the letters of the page the text was made from
        self._filling = False
        self._start_at_end = False  # going up from the next page: start at its end
        self.cursorPositionChanged.connect(self._cursor_moved)
        self.selectionChanged.connect(self._cursor_moved)
        self.hide()

    # ---- the page ------------------------------------------------------------------

    def show_page(self, page: int, page_count: int, text, at_end: bool = False) -> None:
        """Show the text of a page (``text``: its letters, or None while they come)."""
        changed = page != self.page
        self.page, self.page_count = page, page_count
        self._start_at_end = at_end
        title = self.tr("Página {0} de {1}").format(page + 1, page_count)
        self.setAccessibleName(title)
        if text is None:
            self._source = None
            self._fill(ReadingText(self.tr("Leyendo la página {0}…").format(page + 1)), False)
            self.text_wanted.emit(page)
        else:
            self._source = text
            reading = reading_text(text)
            if not reading.text:
                reading = ReadingText(
                    self.tr(
                        "La página {0} no tiene texto: es una imagen (escaneada). "
                        "«Reconocer texto», en el modo Estudiar, lee sus letras."
                    ).format(page + 1)
                )
            self._fill(reading, at_end)
        if changed:
            self.page_changed.emit(page)
            self._announce(title)

    def text_came(self, page: int, text) -> None:
        """The letters of a page arrived: if it is the one being read, show them
        (when they changed, for example after recognising the text, the cursor
        stays on the same letter)."""
        if page != self.page or text is self._source:
            return
        if self._source is None:
            self.show_page(page, self.page_count, text, self._start_at_end)
            return
        letter = self.reading.letter_at(self.textCursor().position())
        self.show_page(page, self.page_count, text)
        self.go_to_letter(letter)

    def _fill(self, reading: ReadingText, at_end: bool) -> None:
        self._filling = True
        self.reading = reading
        self.setPlainText(reading.text)
        cursor = self.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End if at_end else QTextCursor.MoveOperation.Start
        )
        if at_end:  # at the start of the last line, as moving up into it
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        self.setTextCursor(cursor)
        self._filling = False
        self._cursor_moved()

    def _announce(self, said: str) -> None:
        if not QAccessible.isActive():
            return
        try:
            from PySide6.QtGui import QAccessibleAnnouncementEvent

            QAccessible.updateAccessibility(QAccessibleAnnouncementEvent(self, said))
        except (ImportError, TypeError, RuntimeError):  # an older Qt: the name says it
            pass

    # ---- where it is ---------------------------------------------------------------

    def _cursor_moved(self) -> None:
        if self._filling or not self.reading.letters:
            return
        cursor = self.textCursor()
        start = self.reading.letter_at(cursor.selectionStart())
        end = self.reading.letter_at(cursor.selectionEnd())
        self.moved.emit(self.page, start, end)

    def go_to_letter(self, letter: int) -> None:
        """Put the cursor at a letter of the page shown (where a click was)."""
        cursor = self.textCursor()
        cursor.setPosition(self.reading.offset_of(letter))
        self.setTextCursor(cursor)

    # ---- moving past the page ---------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt naming)
        if self.key_first(event):
            return
        key = event.key()
        selecting = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_PageDown:
            self._other_page(1)
            return
        if key == Qt.Key.Key_PageUp:
            self._other_page(-1)
            return
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and not selecting:
            before = self.textCursor().position()
            super().keyPressEvent(event)
            if self.textCursor().position() == before:  # on the last (first) line
                self._other_page(1 if key == Qt.Key.Key_Down else -1)
            return
        super().keyPressEvent(event)

    def _other_page(self, step: int) -> None:
        page = self.page + step
        if not 0 <= page < self.page_count:
            return
        self.reading = ReadingText()  # what comes next is the other page
        self.show_page(page, self.page_count, self.text_of(page), at_end=step < 0)

    def key_first(self, event) -> bool:
        """A key someone else answers first (set by the view). True: answered."""
        return False

    def text_of(self, page: int):
        """The letters of a page, if they are already known (set by the view)."""
        return None
