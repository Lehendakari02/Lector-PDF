"""The page number of the status bar: shows where you are and takes you to a page."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QWidget

from app.ui.pdf_view import PdfView


class PageBox(QWidget):
    """«Página [ 12 ] de 39». Type a number and press Enter to go there."""

    def __init__(self, view: PdfView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.before = QLabel(self.tr("Página"))
        self.edit = QLineEdit()
        self.edit.setObjectName("pageEdit")
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.setFixedWidth(56)
        self.edit.setAccessibleName(self.tr("Número de página"))
        self.edit.setToolTip(self.tr("Escribe un número de página y pulsa Intro (Ctrl+G)"))
        self.validator = QIntValidator(1, 1, self.edit)
        self.edit.setValidator(self.validator)
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
        view.page_changed.connect(lambda _page, _count: self.refresh())
        self.refresh()

    def start(self) -> None:
        """Ready to type a page number."""
        if self.view.page_count:
            self.edit.setFocus()
            self.edit.selectAll()

    def _go(self) -> None:
        text = self.edit.text().strip()
        if text.isdigit():
            page = max(1, min(int(text), self.view.page_count))
            self.view.scroll_to_page(page - 1)
        self.view.setFocus()
        self.refresh()

    def refresh(self) -> None:
        count = self.view.page_count
        self.setVisible(count > 0)
        if not count:
            return
        self.validator.setTop(count)
        if not self.edit.hasFocus():
            self.edit.setText(str(self.view.current_page + 1))
        self.total.setText(self.tr("de {0}").format(count))
