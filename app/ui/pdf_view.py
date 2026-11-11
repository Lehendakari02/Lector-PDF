"""Shows the pages of a PDF one below the other, with continuous scrolling.

Everything is laid out in real screen pixels, not in Qt's scaled units, so on
screens set to 125 % or 150 % every page pixel lands exactly on one screen
pixel and the text stays sharp.

Pages are drawn by ``RenderService`` in another process. This widget only
copies finished images to the screen, which is what keeps scrolling smooth.
"""

import bisect
import math
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPalette
from PySide6.QtWidgets import QAbstractScrollArea, QWidget

from app.core.document import PageSize, PdfDocument
from app.core.render_service import RenderedPage, RenderRequest, RenderService
from app.core.search import SearchHit

PAGE_GAP = 12  # space between pages, in Qt units
SIDE_MARGIN = 16
MIN_ZOOM = 0.2  # screen pixels per point, before the screen scale
MAX_ZOOM = 8.0
ZOOM_STEP = 1.2
PAGES_AHEAD = 3
PAGES_BEHIND = 1
CACHE_BYTES = 400 * 1024 * 1024
# Search results: see-through, so the text stays readable in light and dark pages.
MARK_COLOR = QColor(255, 213, 0, 110)
CURRENT_MARK_COLOR = QColor(255, 120, 0, 150)


def _engine_pixels(points: float, zoom: float) -> int:
    """Pixels the PDF engine uses for a length: it rounds up, with a tiny margin.

    The layout must use exactly the same number. With one pixel of difference
    the image would have to be stretched, and stretched text looks blurry.
    """
    return max(1, math.ceil(points * zoom - 0.001))


def _same_size(image: QImage, target: QRect) -> bool:
    """True if the image fits its place, give or take one pixel of rounding."""
    return abs(image.width() - target.width()) <= 1 and abs(image.height() - target.height()) <= 1


class PdfView(QAbstractScrollArea):
    """Continuous view of one document."""

    # Current page (1-based), page count.
    page_changed = Signal(int, int)
    zoom_changed = Signal(float)
    # Seconds the helper needed for the last page, for the speed read-out.
    page_drawn = Signal(int, float)
    first_page_shown = Signal()
    document_failed = Signal(str)

    # Search results: (search number, list of SearchHit) and (number, too many).
    search_hits = Signal(int, object)
    search_finished = Signal(int, bool)

    # Carry results from the service's background thread to the interface thread.
    _rendered = Signal(object)
    _open_failed = Signal(str)
    _crashed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdfView")
        self.setAccessibleName(self.tr("Documento"))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setBackgroundRole(QPalette.ColorRole.Dark)
        self.viewport().setAutoFillBackground(False)

        self._document: PdfDocument | None = None
        self._sizes: list[PageSize] = []
        self._zoom = 1.0  # Qt units per point
        self._fit_width = True
        self._tops: list[int] = []  # top of every page, in screen pixels
        self._heights: list[int] = []
        self._widths: list[int] = []
        self._total_height = 0
        self._content_width = 0
        self._cache: OrderedDict[int, tuple[float, QImage]] = OrderedDict()
        self._cache_bytes = 0
        self._current_page = -1
        self._shown_first = False
        self._wanted: list[RenderRequest] = []
        self._marks: dict[int, list[SearchHit]] = {}  # search results by page
        self._current_mark: SearchHit | None = None

        self._rendered.connect(self._store_page)
        self._open_failed.connect(self.document_failed)
        self._crashed.connect(self._request_pages)
        self.service = RenderService(
            on_page=self._rendered.emit,
            on_open_failed=self._open_failed.emit,
            on_crashed=self._crashed.emit,
            on_hits=self.search_hits.emit,
            on_search_done=self.search_finished.emit,
        )
        self.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.horizontalScrollBar().valueChanged.connect(self._scrolled)

    # ---- document -------------------------------------------------------

    def set_document(self, document: PdfDocument, password: str | None = None) -> None:
        """Show ``document``. The view takes charge of closing it."""
        self.close_document()
        self._document = document
        self._sizes = document.page_sizes()
        self.service.open(document.path, password)
        self._fit_width = True
        self._layout()
        self.verticalScrollBar().setValue(0)
        self._scrolled()

    def close_document(self) -> None:
        if self._document is not None:
            self._document.close()
            self.service.close_document()
        self._document = None
        self._sizes = []
        self._cache.clear()
        self._cache_bytes = 0
        self._current_page = -1
        self._shown_first = False
        self._marks = {}
        self._current_mark = None
        self._layout()

    def shutdown(self) -> None:
        """Close the document and stop the helper process."""
        self.close_document()
        self.service.shutdown()

    @property
    def document_path(self) -> Path | None:
        return self._document.path if self._document is not None else None

    @property
    def page_count(self) -> int:
        return len(self._sizes)

    @property
    def current_page(self) -> int:
        """Page at the top of the window, counting from 0. -1 without document."""
        return self._current_page

    # ---- search results ---------------------------------------------------

    def set_search_marks(self, hits: list[SearchHit], current: SearchHit | None = None) -> None:
        """Mark these results on the pages; ``current`` stands out from the rest."""
        self._marks = {}
        for hit in hits:
            self._marks.setdefault(hit.page, []).append(hit)
        self._current_mark = current
        self.viewport().update()

    def add_search_marks(self, hits: list[SearchHit]) -> None:
        for hit in hits:
            self._marks.setdefault(hit.page, []).append(hit)
        self.viewport().update()

    def show_search_hit(self, hit: SearchHit) -> None:
        """Make ``hit`` the current result and bring it into view."""
        self._current_mark = hit
        if 0 <= hit.page < self.page_count and hit.rects:
            zoom = self._render_zoom()
            top = self._tops[hit.page] + hit.rects[0][1] * zoom
            bottom = self._tops[hit.page] + hit.rects[-1][3] * zoom
            view_top = self._scroll_y()
            view_height = self._to_pixels(self.viewport().height())
            if top < view_top or bottom > view_top + view_height:
                self.verticalScrollBar().setValue(self._to_units(top - view_height / 3))
        self.viewport().update()

    def search_marks(self) -> dict[int, list[SearchHit]]:
        return self._marks

    # ---- zoom -----------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Zoom as people understand it: 1.0 means 100 %."""
        return self._zoom / (96 / 72)

    def set_zoom(self, zoom: float) -> None:
        self._fit_width = False
        self._apply_zoom(zoom * 96 / 72)

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom / ZOOM_STEP)

    def fit_width(self) -> None:
        self._fit_width = True
        self._apply_zoom(self._zoom_to_fit_width())

    def _zoom_to_fit_width(self) -> float:
        if not self._sizes:
            return self._zoom
        widest = max(size.width for size in self._sizes)
        # Half a unit less, so that rounding up to whole pixels never makes
        # the page one pixel too wide (a sideways scroll bar would appear).
        available = self.viewport().width() - 2 * SIDE_MARGIN - 0.5
        return max(MIN_ZOOM, min(MAX_ZOOM, available / widest))

    def _apply_zoom(self, zoom: float) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if abs(zoom - self._zoom) < 1e-6 and self._tops:
            return
        # Stay on the same spot of the same page while the size changes.
        page = max(self._current_page, 0)
        inside = 0.0
        if self._tops and self._heights[page]:
            inside = (self._scroll_y() - self._tops[page]) / self._heights[page]
        self._zoom = zoom
        self._layout()
        if self._tops:
            self.verticalScrollBar().setValue(
                self._to_units(self._tops[page] + inside * self._heights[page])
            )
        self.zoom_changed.emit(self.zoom)
        self._scrolled()

    # ---- geometry -------------------------------------------------------

    def _scale(self) -> float:
        return self.devicePixelRatioF()

    def _to_pixels(self, units: float) -> int:
        return round(units * self._scale())

    def _to_units(self, pixels: float) -> int:
        return round(pixels / self._scale())

    def _render_zoom(self) -> float:
        """Screen pixels per point: what the helper is asked to draw."""
        return round(self._zoom * self._scale(), 4)

    def _scroll_y(self) -> int:
        return self._to_pixels(self.verticalScrollBar().value())

    def _scroll_x(self) -> int:
        return self._to_pixels(self.horizontalScrollBar().value())

    def _layout(self) -> None:
        if self._fit_width and self._sizes:
            self._zoom = self._zoom_to_fit_width()
        zoom = self._render_zoom()
        gap = self._to_pixels(PAGE_GAP)
        self._tops, self._heights, self._widths = [], [], []
        top = gap
        for size in self._sizes:
            self._tops.append(top)
            self._widths.append(_engine_pixels(size.width, zoom))
            self._heights.append(_engine_pixels(size.height, zoom))
            top += self._heights[-1] + gap
        self._total_height = top if self._sizes else 0
        self._content_width = (
            max(self._widths) + 2 * self._to_pixels(SIDE_MARGIN) if self._sizes else 0
        )
        view = self.viewport().size()
        vertical, horizontal = self.verticalScrollBar(), self.horizontalScrollBar()
        vertical.setRange(0, max(0, self._to_units(self._total_height) - view.height()))
        vertical.setPageStep(view.height())
        vertical.setSingleStep(48)
        horizontal.setRange(0, max(0, self._to_units(self._content_width) - view.width()))
        horizontal.setPageStep(view.width())
        horizontal.setSingleStep(48)
        self.viewport().update()

    def _visible_pages(self) -> range:
        if not self._tops:
            return range(0)
        top = self._scroll_y()
        bottom = top + self._to_pixels(self.viewport().height())
        first = max(0, bisect.bisect_right(self._tops, top) - 1)
        last = bisect.bisect_left(self._tops, bottom)
        return range(first, max(first + 1, last))

    def _page_left(self, page: int) -> int:
        view_width = self._to_pixels(self.viewport().width())
        width = max(view_width, self._content_width)
        return (width - self._widths[page]) // 2 - self._scroll_x()

    # ---- drawing requests ----------------------------------------------

    def _scrolled(self) -> None:
        visible = self._visible_pages()
        current = visible.start if len(visible) else -1
        if len(visible) > 1:
            # The page that fills most of the window counts as the current one.
            middle = self._scroll_y() + self._to_pixels(self.viewport().height()) // 3
            current = max(0, bisect.bisect_right(self._tops, middle) - 1)
        if current != self._current_page:
            self._current_page = current
            self.page_changed.emit(current + 1, self.page_count)
        self._request_pages()
        self.viewport().update()

    def _request_pages(self) -> None:
        if self._document is None:
            return
        visible = self._visible_pages()
        if not len(visible):
            return
        order = list(visible)
        order += range(visible.stop, min(self.page_count, visible.stop + PAGES_AHEAD))
        order += range(max(0, visible.start - PAGES_BEHIND), visible.start)
        zoom = self._render_zoom()
        self._wanted = [
            RenderRequest(page, zoom)
            for page in order
            if page not in self._cache or self._cache[page][0] != zoom
        ]
        self.service.want(self._wanted)

    def _store_page(self, result: RenderedPage) -> None:
        if self._document is None or result.page >= self.page_count:
            return
        image = QImage(
            result.samples,
            result.width,
            result.height,
            result.stride,
            QImage.Format.Format_RGB888,
        ).copy()  # own copy: the bytes object will not outlive this call
        old = self._cache.pop(result.page, None)
        if old is not None:
            self._cache_bytes -= old[1].sizeInBytes()
        self._cache[result.page] = (result.zoom, image)
        self._cache_bytes += image.sizeInBytes()
        self._trim_cache()
        self.page_drawn.emit(result.page, result.seconds)
        if result.page in self._visible_pages():
            self.viewport().update()
            if not self._shown_first:
                self._shown_first = True
                self.first_page_shown.emit()

    def _trim_cache(self) -> None:
        """Forget the pages farthest from the one being read."""
        while self._cache_bytes > CACHE_BYTES and len(self._cache) > 1:
            farthest = max(self._cache, key=lambda page: abs(page - self._current_page))
            self._cache_bytes -= self._cache.pop(farthest)[1].sizeInBytes()

    def cached_pages(self) -> dict[int, float]:
        """Pages that are drawn and ready, with the zoom they were drawn at."""
        return {page: zoom for page, (zoom, _image) in self._cache.items()}

    # ---- Qt events ------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self.viewport())
        palette = self.palette()
        painter.fillRect(self.viewport().rect(), palette.color(QPalette.ColorRole.Dark))
        if not self._tops:
            return
        scale = self._scale()
        painter.scale(1 / scale, 1 / scale)  # from here on, real screen pixels
        scroll_y = self._scroll_y()
        zoom = self._render_zoom()
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() * scale * 1.4)
        painter.setFont(font)
        for page in self._visible_pages():
            target = QRect(
                self._page_left(page),
                self._tops[page] - scroll_y,
                self._widths[page],
                self._heights[page],
            )
            cached = self._cache.get(page)
            if cached is None:
                painter.fillRect(target, QColor("white"))
                painter.setPen(QColor("#767676"))
                painter.drawText(
                    target,
                    Qt.AlignmentFlag.AlignCenter,
                    self.tr("Página {0}").format(page + 1),
                )
            elif cached[0] == zoom and _same_size(cached[1], target):
                painter.drawImage(target.topLeft(), cached[1])  # exact, pixel for pixel
            else:
                # Drawn for another zoom: stretch it until the sharp one arrives.
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.drawImage(target, cached[1])
            for hit in self._marks.get(page, ()):
                color = CURRENT_MARK_COLOR if hit is self._current_mark else MARK_COLOR
                for x0, y0, x1, y1 in hit.rects:
                    mark = QRectF(x0 * zoom, y0 * zoom, (x1 - x0) * zoom, (y1 - y0) * zoom)
                    painter.fillRect(mark.translated(target.left(), target.top()), color)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout()
        self._scrolled()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            # Moved to a screen with another scale: lay out and draw again.
            self._layout()
            self._scrolled()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        bar = self.verticalScrollBar()
        key = event.key()
        if key in (Qt.Key.Key_PageDown, Qt.Key.Key_Space):
            bar.setValue(bar.value() + bar.pageStep() - 40)
        elif key == Qt.Key.Key_PageUp:
            bar.setValue(bar.value() - bar.pageStep() + 40)
        elif key == Qt.Key.Key_Home:
            bar.setValue(0)
        elif key == Qt.Key.Key_End:
            bar.setValue(bar.maximum())
        elif key == Qt.Key.Key_Down:
            bar.setValue(bar.value() + bar.singleStep())
        elif key == Qt.Key.Key_Up:
            bar.setValue(bar.value() - bar.singleStep())
        else:
            super().keyPressEvent(event)

    def scroll_to_page(self, page: int) -> None:
        """Put the top of ``page`` (counting from 0) at the top of the window."""
        if 0 <= page < self.page_count:
            gap = self._to_pixels(PAGE_GAP) // 2
            self.verticalScrollBar().setValue(self._to_units(self._tops[page] - gap))
