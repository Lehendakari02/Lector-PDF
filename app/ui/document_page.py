"""One open document: its pages, its search panel and its side panel.

Every tab of the window is one of these. Each has its own helper process to
draw the pages, so a document that gives trouble never disturbs the others.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget

from app.ui.pdf_view import PdfView
from app.ui.search_panel import SearchPanel
from app.ui.side_panel import SidePanel

SIDE_PANEL_WIDTH = 222  # one column of thumbnails, the scroll bar and room for the heading
SEARCH_PANEL_WIDTH = 320


class DocumentPage(QWidget):
    """Side panel on the left, the document in the middle, search on the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path: Path | None = None
        self.slowest_page = 0.0  # seconds, for the drawing figure of test builds
        self.view = PdfView()
        self.search_panel = SearchPanel(self.view)
        self.search_panel.setMinimumWidth(SEARCH_PANEL_WIDTH)
        self.side_panel = SidePanel(self.view)
        self.side_panel.setMinimumWidth(SIDE_PANEL_WIDTH)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("documentSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        for widget, stretch in ((self.side_panel, 0), (self.view, 1), (self.search_panel, 0)):
            self.splitter.addWidget(widget)
            self.splitter.setStretchFactor(self.splitter.count() - 1, stretch)
        self.side_panel.hide()
        self.search_panel.hide()
        self._side_panel_sized = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)

    @property
    def title(self) -> str:
        return self.path.name if self.path is not None else ""

    def show_side_panel(self) -> None:
        self.side_panel.show()
        if not self._side_panel_sized:
            # Start narrow: one column of thumbnails. The edge can be dragged.
            self._side_panel_sized = True
            sizes = self.splitter.sizes()
            extra = sizes[0] - SIDE_PANEL_WIDTH
            self.splitter.setSizes([SIDE_PANEL_WIDTH, sizes[1] + extra, sizes[2]])

    def shutdown(self) -> None:
        """Close the document and stop its helper process."""
        self.view.shutdown()
