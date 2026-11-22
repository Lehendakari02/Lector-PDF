"""The right half of the window when two documents are seen side by side.

It holds the document put "al lado" with a thin bar above it: its name and a
button to stop seeing it there. The document keeps its tab, and the side
being worked on (the one the tools act on) is shown by a coloured line.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from app.ui import icons


class BesideArea(QWidget):
    """The document seen beside the one in front."""

    close_asked = Signal()

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

    def set_title(self, title: str) -> None:
        self.title.setText(self.tr("Al lado: {0}").format(title))

    def set_active(self, active: bool) -> None:
        """Whether the tools act on this side now."""
        self.setProperty("active", active)
        self.title.setProperty("active", active)
        for widget in (self, self.title):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
