"""The page number of the status bar: shows where you are and takes you to a page.

It also takes an article, a section or a part written as people write them
("art. 14", "3.2", "capítulo II"): the document goes to its heading.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QWidget

from app.ui.pdf_view import PdfView

MAX_TYPED = 60  # letters: "disposición transitoria decimotercera" fits


class PageBox(QWidget):
    """«Página [ 12 ] de 39». Type a number, or "art. 14", and press Enter to go there."""

    go_to = Signal()  # Enter was pressed: the document gets the keyboard back
    told = Signal(str)  # something to say in the status bar (not found, not understood)

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view: PdfView | None = None
        self.before = QLabel(self.tr("Página"))
        self.edit = QLineEdit()
        self.edit.setObjectName("pageEdit")
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.setFixedWidth(72)
        self.edit.setMaxLength(MAX_TYPED)
        self.edit.setAccessibleName(self.tr("Página, artículo o apartado"))
        self.edit.setToolTip(
            self.tr(
                "Escribe un número de página, o un artículo o apartado "
                "(«art. 14», «3.2», «capítulo II»), y pulsa Intro (Ctrl+G)"
            )
        )
        # Any number can be typed: one past the end goes to the last page.
        self._asked = ""  # the place being looked for, to say it if it is not there
        self.total = QLabel()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(0)
        layout.addWidget(self.before)
        layout.addWidget(self.edit)
        layout.addWidget(self.total)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self.edit.returnPressed.connect(self._go)
        self.edit.editingFinished.connect(self.refresh)  # left without Enter: show the truth
        self.set_view(view)

    def set_view(self, view: PdfView) -> None:
        """Follow another document (the tab that is now in front)."""
        if self.view is not None:
            self.view.page_changed.disconnect(self._page_changed)
            self.view.place_answered.disconnect(self._place_answered)
        self.view = view
        self._asked = ""
        view.page_changed.connect(self._page_changed)
        view.place_answered.connect(self._place_answered)
        self.refresh()

    def _page_changed(self, _page: int, _count: int) -> None:
        self.refresh()

    def start(self, place: bool = False) -> None:
        """Ready to type a page number (or, with ``place``, an article)."""
        if self.view.page_count:
            self.edit.setFocus()
            if place:
                self.edit.clear()
                self.edit.setPlaceholderText(self.tr("art. 14"))
            self.edit.selectAll()

    def _go(self) -> None:
        text = self.edit.text().strip()
        if text.isdigit():
            page = max(1, min(int(text), self.view.page_count))
            self.view.scroll_to_page(page - 1)
        elif text and self.view.go_to_place(text):
            self._asked = text
        elif text:
            self.told.emit(
                self.tr("Escribe un número de página, o un artículo o apartado: «art. 14», «3.2»…")
            )
        self.go_to.emit()
        self.refresh()

    def _place_answered(self, found: bool) -> None:
        asked, self._asked = self._asked, ""
        if not found:
            self.told.emit(self.tr("No encuentro «{0}» en este documento.").format(asked))

    def refresh(self) -> None:
        count = self.view.page_count
        self.setVisible(count > 0)
        if not count:
            return
        if not self.edit.hasFocus():
            self.edit.setPlaceholderText("")
            self.edit.setText(str(self.view.current_page + 1))
        self.total.setText(self.tr("de {0}").format(count))
