"""One open document: its pages, its search panel and its side panel.

Every tab of the window is one of these. Each has its own helper process to
draw the pages, so a document that gives trouble never disturbs the others.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from app.ui.features import Mode
from app.ui.ocr_banner import OcrBanner
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
        # False for a document that is only being looked at (an earlier
        # version): it is not a recent file nor a tab to bring back.
        self.remembered = True
        # How the file was when it was opened or last saved from here, to
        # notice if another program writes it meanwhile.
        self.stamp = None
        # Warnings about saving already answered with "save here anyway".
        self.accepted_warnings: set[str] = set()
        # Saving by itself ("guardar solo"): whether the saving going on was
        # started by the program, whether the last one failed (said once, not
        # at every try) and whether it has been said why it is not done.
        self.saving_by_itself = False
        self.autosave_failed = False
        self.autosave_told = False
        self.slowest_page = 0.0  # seconds, for the drawing figure of test builds
        self.mode = Mode.READ  # the work mode this document is used in
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

        # Offers to recognise the text when the document turns out to be scanned.
        self.ocr_banner = OcrBanner()
        self.text_recognition = None  # reading the text of its scanned pages
        self.recognize_when_known = False  # asked before the pages were looked at

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.ocr_banner)
        layout.addWidget(self.splitter, 1)

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
        if self.text_recognition is not None:
            self.text_recognition.stop()
            self.text_recognition = None
        self.view.shutdown()
