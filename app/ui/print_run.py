"""Sends the pages of a document to a printer, one after another.

The pages are drawn by the helper process of the document, a few at a time, so
the window never freezes and a long document does not fill the memory. A page
that cannot be drawn is left out and reported at the end; the rest is printed.
"""

from PySide6.QtCore import QObject, QRectF, Signal
from PySide6.QtGui import QImage, QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrinter

from app.core.printing import Scaling, is_landscape, placement, print_zoom
from app.core.render_service import RenderedPage
from app.ui.pdf_view import PdfView

PAGES_AT_A_TIME = 3  # drawn ahead of the printer
MAX_TRIES = 3  # times a batch is asked again after the helper restarts


class PrintRun(QObject):
    """One print job. Create it, connect the signals and call ``start``."""

    # Pages already sent and pages in total.
    progress = Signal(int, int)
    # The job is over: pages that could not be printed (counting from 0) and
    # whether it was cancelled.
    finished = Signal(list, bool)

    def __init__(
        self,
        view: PdfView,
        printer: QPrinter,
        pages: list[int],
        scaling: Scaling = Scaling.FIT,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._printer = printer
        self._pages = list(pages)
        self._scaling = scaling
        self._sizes = view.page_sizes()
        self._zoom = print_zoom(printer.resolution())
        self._painter = QPainter()
        self._next = 0  # position in self._pages of the next page to send
        self._batch: list[int] = []  # pages asked for and not sent yet, in order
        self._ready: dict[int, QImage | None] = {}  # None: it cannot be drawn
        self._tries = 0
        self._sent_any = False
        self.failed: list[int] = []
        self.running = False
        view.print_page_ready.connect(self._page_ready)
        view.print_page_failed.connect(self._page_failed)
        view.print_page_lost.connect(self._page_lost)
        view.destroyed.connect(self.cancel)

    @property
    def total(self) -> int:
        return len(self._pages)

    def start(self) -> bool:
        """Begin. False if the printer cannot be used (``finished`` is not emitted)."""
        if not self._pages:
            return False
        self._set_orientation(self._pages[0])
        if not self._painter.begin(self._printer):
            return False
        self.running = True
        self.progress.emit(0, self.total)
        self._ask_for_more()
        return True

    def cancel(self) -> None:
        if not self.running:
            return
        self._end(cancelled=True)

    # ---- internals ------------------------------------------------------

    def _set_orientation(self, page: int) -> None:
        size = self._sizes[page]
        landscape = is_landscape(size.width, size.height)
        self._printer.setPageOrientation(
            QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait
        )

    def _ask_for_more(self) -> None:
        self._batch = self._pages[self._next : self._next + PAGES_AT_A_TIME]
        self._tries = 0
        if not self._batch:
            self._end(cancelled=False)
            return
        self._view.want_print_pages(self._batch, self._zoom)

    def _page_ready(self, drawn: RenderedPage) -> None:
        if not self.running or drawn.page not in self._batch:
            return
        self._ready[drawn.page] = QImage(
            drawn.samples, drawn.width, drawn.height, drawn.stride, QImage.Format.Format_RGB888
        ).copy()
        self._send_what_is_ready()

    def _page_failed(self, page: int) -> None:
        if not self.running or page not in self._batch:
            return
        self._ready[page] = None
        self._send_what_is_ready()

    def _page_lost(self, _page: int) -> None:
        """The helper restarted before drawing it: ask again for what is missing."""
        if not self.running:
            return
        missing = [page for page in self._batch if page not in self._ready]
        if not missing:
            return
        self._tries += 1
        if self._tries > MAX_TRIES:
            for page in missing:
                self._ready[page] = None
            self._send_what_is_ready()
            return
        self._view.want_print_pages(missing, self._zoom)

    def _send_what_is_ready(self) -> None:
        """Send to the printer, in order, every page of the batch that has arrived."""
        while self.running and self._batch and self._batch[0] in self._ready:
            page = self._batch.pop(0)
            image = self._ready.pop(page)
            if image is None:
                self.failed.append(page)
            else:
                self._send(page, image)
            self._next += 1
            self.progress.emit(self._next, self.total)
        if self.running and not self._batch:
            self._ask_for_more()

    def _send(self, page: int, image: QImage) -> None:
        if self._sent_any:
            self._set_orientation(page)  # each sheet the way its page is
            self._printer.newPage()
        self._sent_any = True
        resolution = self._printer.resolution()
        area = self._printer.pageLayout().paintRectPixels(resolution)
        size = self._sizes[page]
        left, top, width, height = placement(
            size.width / 72 * resolution,
            size.height / 72 * resolution,
            area.width(),
            area.height(),
            self._scaling,
        )
        self._painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._painter.drawImage(QRectF(left, top, width, height), image)

    def _end(self, cancelled: bool) -> None:
        self.running = False
        self._view.want_print_pages([], self._zoom)
        if cancelled:
            self._printer.abort()
        self._painter.end()
        self._ready.clear()
        self.finished.emit(list(self.failed), cancelled)
