"""The right half of the window when two documents are seen side by side.

It holds the document put "al lado" with a thin bar above it: its name and a
button to stop seeing it there. The document keeps its tab, and the side
being worked on (the one the tools act on) is shown by a coloured line.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui import icons


class BesideArea(QWidget):
    """The document seen beside the one in front."""

    close_asked = Signal()
    link_here = Signal()  # "Enlazar aquí": the link goes to the place shown
    link_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("besideArea")
        self.page = None  # the DocumentPage put here
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("besideBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 2, 2, 2)
        self.title = QLabel()
        self.title.setObjectName("besideTitle")
        row.addWidget(self.title, 1)
        self.close_button = QToolButton()
        self.close_button.setIcon(icons.icon("close", icons.MUTED))
        tip = self.tr("Dejar de verlo al lado (el documento sigue abierto en su pestaña)")
        self.close_button.setToolTip(tip)
        self.close_button.setAccessibleName(self.tr("Dejar de verlo al lado"))
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.clicked.connect(self.close_asked)
        row.addWidget(self.close_button)
        layout.addWidget(bar)
        # While a link is being made: go to the place and press "Enlazar aquí".
        self.link_bar = QWidget()
        self.link_bar.setObjectName("linkBar")
        link_row = QHBoxLayout(self.link_bar)
        link_row.setContentsMargins(10, 4, 6, 4)
        self.link_label = QLabel()
        self.link_label.setWordWrap(True)
        link_row.addWidget(self.link_label, 1)
        self.link_button = QPushButton(self.tr("Enlazar aquí"))
        self.link_button.setDefault(True)
        self.link_button.clicked.connect(self.link_here)
        link_row.addWidget(self.link_button)
        cancel = QPushButton(self.tr("Cancelar"))
        cancel.clicked.connect(self.link_cancelled)
        link_row.addWidget(cancel)
        self.link_bar.hide()
        layout.addWidget(self.link_bar)
        self.slot = QVBoxLayout()
        self.slot.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.slot, 1)

    def put(self, page) -> None:
        self.page = page
        self.slot.addWidget(page)
        page.show()
        self.set_title(page.title)

    def take(self):
        """Take the document away (to put it back in front); returns it."""
        page, self.page = self.page, None
        if page is not None:
            self.slot.removeWidget(page)
        return page

    def ask_link_place(self, words: str) -> None:
        self.link_label.setText(
            self.tr("Ve al sitio al que quieres enlazar «{0}» y pulsa «Enlazar aquí».").format(
                words
            )
        )
        self.link_bar.show()

    def end_link(self) -> None:
        self.link_bar.hide()

    def set_title(self, title: str) -> None:
        self.title.setText(self.tr("Al lado: {0}").format(title))

    def set_active(self, active: bool) -> None:
        """Whether the tools act on this side now."""
        self.setProperty("active", active)
        self.title.setProperty("active", active)
        for widget in (self, self.title):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
