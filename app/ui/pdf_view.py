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
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPalette
from PySide6.QtWidgets import QAbstractScrollArea, QFrame, QMenu, QWidget

from app.core.document import PageSize, PdfDocument
from app.core.outline import OutlineEntry
from app.core.render_service import (
    MAX_PIXELS_PER_PAGE,
    RenderedPage,
    RenderRequest,
    RenderService,
)
from app.core.search import PageText, SearchHit
from app.core.selection import caret_at, is_on_text, selection_rects, word_at
from app.ui import theme

PAGE_GAP = 12  # space between pages, in Qt units
SIDE_MARGIN = 16
MIN_ZOOM = 0.2  # screen pixels per point, before the screen scale
MAX_ZOOM = 8.0
ZOOM_STEP = 1.2
# A document opens fitted to the width, but never bigger than this (1.0 = 100 %):
# on a wide screen the full width makes the letters far too big to read at ease.
COMFORTABLE_ZOOM = 1.25
POINT_TO_PIXEL = 96 / 72  # at 100 %, one point of the page is this many pixels


class Fit(Enum):
    """How the zoom follows the size of the window."""

    NONE = "none"  # a zoom chosen by hand: it stays
    WIDTH = "width"  # the page is as wide as the window
    PAGE = "page"  # the whole page is visible
    COMFORTABLE = "comfortable"  # as wide as the window, but not too big: on opening


PAGES_AHEAD = 3
PAGES_BEHIND = 1
CACHE_BYTES = 400 * 1024 * 1024
# Search results: see-through, so the text stays readable in light and dark pages.
# Colours painted on the pages. They do not follow the light or dark appearance:
# a page is a white sheet in both.
PAPER_COLOR = QColor("white")
WAITING_TEXT_COLOR = QColor("#767676")  # "Página 7" on a sheet not drawn yet
MARK_COLOR = QColor(255, 213, 0, 110)
CURRENT_MARK_COLOR = QColor(255, 120, 0, 150)
SELECTION_COLOR = QColor(61, 79, 208, 80)
PAGE_TEXTS_KEPT = 40  # pages whose letters are kept ready for selecting
END_OF_PAGE = 10**9  # a caret after the last letter, whatever the page has
AUTOSCROLL_MS = 40  # while dragging a selection past the edge of the window


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
    rotation_changed = Signal(int)
    # Seconds the helper needed for the last page, for the speed read-out.
    page_drawn = Signal(int, float)
    first_page_shown = Signal()
    document_failed = Signal(str)

    # Search results: (search number, list of SearchHit) and (number, too many).
    search_hits = Signal(int, object)
    search_finished = Signal(int, bool)

    # Carry results from the service's background thread to the interface thread.
    _rendered = Signal(object)
    # The outline of the document has arrived (or has been emptied).
    outline_changed = Signal()
    # A small picture asked with want_thumbnails is ready: RenderedPage.
    thumbnail_drawn = Signal(object)
    # Text is selected or not any more: bool.
    selection_changed = Signal(bool)
    # "Copy" has finished: number of letters put on the clipboard (0: nothing to copy).
    text_copied = Signal(int)
    # Someone tried to select on a page that is only a picture (a scan).
    no_text_to_select = Signal()
    _open_failed = Signal(str)
    _outline_ready = Signal(object)
    _text_ready = Signal(int, object)
    _copied = Signal(int, str)
    _crashed = Signal()
    _page_failed = Signal(int, float, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdfView")
        self.setAccessibleName(self.tr("Documento"))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setBackgroundRole(QPalette.ColorRole.Dark)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.viewport().setAutoFillBackground(False)

        self._document: PdfDocument | None = None
        self._sizes: list[PageSize] = []
        self._zoom = 1.0  # Qt units per point
        self._rotation = 0
        self._fit = Fit.WIDTH
        self._tops: list[int] = []  # top of every page, in screen pixels
        self._heights: list[int] = []
        self._widths: list[int] = []
        self._total_height = 0
        self._content_width = 0
        self._cache: OrderedDict[int, tuple[float, QImage]] = OrderedDict()
        self._cache_bytes = 0
        self._current_page = -1
        self._shown_first = False
        self._failed_pages: set[int] = set()  # pages that cannot be drawn
        self._wanted: list[RenderRequest] = []
        self._marks: dict[int, list[SearchHit]] = {}  # search results by page
        self._current_mark: SearchHit | None = None
        self._outline: list[OutlineEntry] = []
        self._texts: OrderedDict[int, PageText] = OrderedDict()  # letters, to select
        self._asked_texts: set[int] = set()
        # The selection: where it was started and where it ends, each (page, caret).
        self._anchor: tuple[int, int] | None = None
        self._focus: tuple[int, int] | None = None
        self._selecting = False
        self._drag_position = QPoint()
        self._copy_id = 0
        self._autoscroll = QTimer(self)
        self._autoscroll.setInterval(AUTOSCROLL_MS)
        self._autoscroll.timeout.connect(self._autoscroll_step)
        self.viewport().setMouseTracking(True)  # to change the pointer over text

        self._rendered.connect(self._store_page)
        self._outline_ready.connect(self._store_outline)
        self._text_ready.connect(self._store_text)
        self._copied.connect(self._put_on_clipboard)
        self._open_failed.connect(self.document_failed)
        self._crashed.connect(self._helper_restarted)
        self._page_failed.connect(self._mark_failed)
        self.service = RenderService(
            on_page=self._rendered.emit,
            on_page_failed=self._page_failed.emit,
            on_open_failed=self._open_failed.emit,
            on_crashed=self._crashed.emit,
            on_hits=self.search_hits.emit,
            on_search_done=self.search_finished.emit,
            on_outline=self._outline_ready.emit,
            on_thumbnail=self.thumbnail_drawn.emit,
            on_text=self._text_ready.emit,
            on_copied=self._copied.emit,
        )
        self.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.horizontalScrollBar().valueChanged.connect(self._scrolled)

    # ---- document -------------------------------------------------------

    def set_document(self, document: PdfDocument, password: str | None = None) -> None:
        """Show ``document``. The view takes charge of closing it."""
        self.close_document()
        self._document = document
        self._sizes = document.page_sizes()
        self.service.open(document.path, password or document.password)
        self._fit = Fit.COMFORTABLE
        self._rotation = 0
        self._layout()
        self.zoom_changed.emit(self.zoom)
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
        self._failed_pages = set()
        self._current_page = -1
        self._shown_first = False
        self._marks = {}
        self._current_mark = None
        if self._outline:
            self._outline = []
            self.outline_changed.emit()
        self._texts.clear()
        self._asked_texts.clear()
        self._selecting = False
        self._autoscroll.stop()
        self.clear_selection()
        self._layout()

    @property
    def outline(self) -> list[OutlineEntry]:
        """Sections of the document. Arrives a moment after opening it."""
        return self._outline

    def _store_outline(self, entries: list[OutlineEntry]) -> None:
        if self._document is None:
            return
        self._outline = entries
        self.outline_changed.emit()

    def want_thumbnails(self, pages: list[int], width: int, height: int) -> None:
        """Ask for small pictures of ``pages`` that fit in ``width`` x ``height`` pixels.

        Replaces the previous list. They arrive one by one in ``thumbnail_drawn``.
        """
        if self._document is None:
            return
        sizes = self._shown_sizes()
        requests = []
        for page in pages:
            if 0 <= page < len(sizes):
                size = sizes[page]
                zoom = min(width / size.width, height / size.height)
                requests.append(RenderRequest(page, zoom, self._rotation))
        self.service.want_thumbnails(requests)

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
        self._current_mark = current
        self.add_search_marks(hits)

    def add_search_marks(self, hits: list[SearchHit]) -> None:
        for hit in hits:
            self._marks.setdefault(hit.page, []).append(hit)
            if hit.next_rects:  # a result that goes on to the next page
                self._marks.setdefault(hit.page + 1, []).append(hit)
        self.viewport().update()

    def show_search_hit(self, hit: SearchHit) -> None:
        """Make ``hit`` the current result and bring it into view."""
        self._current_mark = hit
        if 0 <= hit.page < self.page_count and hit.rects:
            zoom = self._render_zoom()
            first = self._shown_rect(hit.page, hit.rects[0])
            last = self._shown_rect(hit.page, hit.rects[-1])
            top = self._tops[hit.page] + min(first[1], last[1]) * zoom
            bottom = self._tops[hit.page] + max(first[3], last[3]) * zoom
            view_top = self._scroll_y()
            view_height = self._to_pixels(self.viewport().height())
            if top < view_top or bottom > view_top + view_height:
                self.verticalScrollBar().setValue(self._to_units(top - view_height / 3))
            # With a lot of zoom the result can be off to one side.
            page_left = self._page_left(hit.page) + self._scroll_x()
            left = page_left + min(first[0], last[0]) * zoom
            right = page_left + max(first[2], last[2]) * zoom
            view_left = self._scroll_x()
            view_width = self._to_pixels(self.viewport().width())
            if left < view_left or right > view_left + view_width:
                self.horizontalScrollBar().setValue(self._to_units(left - view_width / 3))
        self.viewport().update()

    def search_marks(self) -> dict[int, list[SearchHit]]:
        return self._marks

    # ---- zoom -----------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Zoom as people understand it: 1.0 means 100 %."""
        return self._zoom / POINT_TO_PIXEL

    @property
    def fit(self) -> Fit:
        return self._fit

    def set_zoom(self, zoom: float) -> None:
        self._fit = Fit.NONE
        self._apply_zoom(zoom * POINT_TO_PIXEL)

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom / ZOOM_STEP)

    @property
    def rotation(self) -> int:
        """Quarter turns added for viewing, in degrees. The file is not changed."""
        return self._rotation

    def set_rotation(self, degrees: int) -> None:
        degrees %= 360
        if degrees == self._rotation or degrees % 90:
            return
        page = max(self._current_page, 0)
        self._rotation = degrees
        self._cache.clear()  # every picture was drawn the other way round
        self._cache_bytes = 0
        self._layout()
        self.scroll_to_page(page)
        self.rotation_changed.emit(degrees)
        self.zoom_changed.emit(self.zoom)
        self._scrolled()

    def rotate_view(self) -> None:
        """Turn the pages a quarter turn to the right, only on screen."""
        self.set_rotation(self._rotation + 90)

    def _shown_sizes(self) -> list[PageSize]:
        """Page sizes as they are seen, with the viewing rotation applied."""
        if self._rotation in (90, 270):
            return [PageSize(size.height, size.width) for size in self._sizes]
        return self._sizes

    def shown_page_size(self, page: int) -> PageSize:
        """Size of a page in points, as it is seen (viewing rotation applied)."""
        return self._shown_sizes()[page]

    def _shown_rect(self, page: int, rect: tuple[float, float, float, float]):
        """Where a rectangle of the page is on the turned page (in points)."""
        x0, y0, x1, y1 = rect
        size = self._sizes[page]
        if self._rotation == 90:
            return (size.height - y1, x0, size.height - y0, x1)
        if self._rotation == 180:
            return (size.width - x1, size.height - y1, size.width - x0, size.height - y0)
        if self._rotation == 270:
            return (y0, size.width - x1, y1, size.width - x0)
        return rect

    def fit_width(self) -> None:
        """Make the page as wide as the window."""
        self._fit = Fit.WIDTH
        self._apply_zoom(self._zoom_to_fit_width())

    def fit_page(self) -> None:
        """Make a whole page visible at once."""
        self._fit = Fit.PAGE
        self._apply_zoom(self._zoom_to_fit_page())

    def _zoom_to_fit_page(self) -> float:
        if not self._sizes:
            return self._zoom
        tallest = max(size.height for size in self._shown_sizes())
        available = self.viewport().height() - 2 * PAGE_GAP - 0.5
        return max(MIN_ZOOM, min(self._zoom_to_fit_width(), available / tallest))

    def _zoom_for_fit(self) -> float:
        if self._fit is Fit.PAGE:
            return self._zoom_to_fit_page()
        if self._fit is Fit.COMFORTABLE:
            return min(self._zoom_to_fit_width(), COMFORTABLE_ZOOM * POINT_TO_PIXEL)
        return self._zoom_to_fit_width()

    def _zoom_to_fit_width(self) -> float:
        if not self._sizes:
            return self._zoom
        widest = max(size.width for size in self._shown_sizes())
        # Half a unit less, so that rounding up to whole pixels never makes
        # the page one pixel too wide (a sideways scroll bar would appear).
        available = self.viewport().width() - 2 * SIDE_MARGIN - 0.5
        return max(MIN_ZOOM, min(MAX_ZOOM, available / widest))

    def _apply_zoom(self, zoom: float) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if abs(zoom - self._zoom) < 1e-6 and self._tops:
            return
        place = self._place()
        self._zoom = zoom
        self._layout()
        self._return_to(place)
        self.zoom_changed.emit(self.zoom)
        self._scrolled()

    def _place(self) -> tuple[int, float]:
        """The page being read and how far down it the top of the window is."""
        page = max(self._current_page, 0)
        inside = 0.0
        if self._tops and self._heights[page]:
            inside = (self._scroll_y() - self._tops[page]) / self._heights[page]
        return page, inside

    def _return_to(self, place: tuple[int, float]) -> None:
        """Stay on the same spot of the same page after the sizes have changed."""
        page, inside = place
        if page < len(self._tops):
            self.verticalScrollBar().setValue(
                self._to_units(self._tops[page] + inside * self._heights[page])
            )

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
        if self._fit is not Fit.NONE and self._sizes:
            fitted = self._zoom_for_fit()
            if abs(fitted - self._zoom) > 1e-6:
                self._zoom = fitted
                self.zoom_changed.emit(self.zoom)
        zoom = self._render_zoom()
        gap = self._to_pixels(PAGE_GAP)
        self._tops, self._heights, self._widths = [], [], []
        top = gap
        for size in self._shown_sizes():
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
        # With a lot of zoom every page is a huge picture. Pages out of sight are
        # only drawn ahead of time while they fit in memory; otherwise they would
        # push out the ones being read and be asked for again, without end.
        self._wanted = []
        room = CACHE_BYTES
        for page in order:
            room -= min(self._widths[page] * self._heights[page], MAX_PIXELS_PER_PAGE) * 3
            if room < 0 and page not in visible:
                break
            if page in self._failed_pages:
                continue  # it cannot be drawn: asking again would only fail again
            if page not in self._cache or self._cache[page][0] != zoom:
                self._wanted.append(RenderRequest(page, zoom, self._rotation))
        self.service.want(self._wanted)

    def _helper_restarted(self) -> None:
        """The helper died and a new one takes over: ask again for what was pending."""
        self._asked_texts = set(self._texts)  # letters asked for and never received
        self._request_pages()

    def failed_pages(self) -> set[int]:
        """Pages of this document that could not be drawn (damaged)."""
        return set(self._failed_pages)

    def _mark_failed(self, page: int, _zoom: float, _message: str) -> None:
        """A damaged page: say so on its sheet and go on with the others."""
        if self._document is None or not 0 <= page < self.page_count:
            return
        self._failed_pages.add(page)
        self.viewport().update()
        self._request_pages()

    def _store_page(self, result: RenderedPage) -> None:
        if self._document is None or result.page >= self.page_count:
            return
        if result.rotation != self._rotation:
            return  # drawn before the view was turned
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
        self._want_text(result.page)  # a page on screen can be selected at once
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
        painter.fillRect(self.viewport().rect(), QColor(theme.colours().canvas))
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
            # A soft shadow, so the page looks like a sheet lying on the desk.
            edge = max(1, round(scale))
            for step, alpha in ((3, 7), (2, 12), (1, 20)):
                grow = step * edge
                painter.fillRect(
                    target.adjusted(-grow, -grow + edge, grow, grow + edge), QColor(0, 0, 0, alpha)
                )
            cached = self._cache.get(page)
            if cached is None:
                painter.fillRect(target, PAPER_COLOR)
                painter.setPen(WAITING_TEXT_COLOR)
                painter.drawText(
                    target,
                    Qt.AlignmentFlag.AlignCenter,
                    self.tr("La página {0} está dañada y no se puede mostrar").format(page + 1)
                    if page in self._failed_pages
                    else self.tr("Página {0}").format(page + 1),
                )
            elif cached[0] == zoom and _same_size(cached[1], target):
                painter.drawImage(target.topLeft(), cached[1])  # exact, pixel for pixel
            else:
                # Drawn for another zoom: stretch it until the sharp one arrives.
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.drawImage(target, cached[1])
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            self._tint_paper(painter, target)
            for hit in self._marks.get(page, ()):
                color = CURRENT_MARK_COLOR if hit is self._current_mark else MARK_COLOR
                for rect in hit.rects if hit.page == page else hit.next_rects:
                    x0, y0, x1, y1 = self._shown_rect(page, rect)
                    mark = QRectF(x0 * zoom, y0 * zoom, (x1 - x0) * zoom, (y1 - y0) * zoom)
                    painter.fillRect(mark.translated(target.left(), target.top()), color)
            for rect in self._selection_rects(page):
                x0, y0, x1, y1 = self._shown_rect(page, rect)
                mark = QRectF(x0 * zoom, y0 * zoom, (x1 - x0) * zoom, (y1 - y0) * zoom)
                painter.fillRect(mark.translated(target.left(), target.top()), SELECTION_COLOR)

    @staticmethod
    def _tint_paper(painter: QPainter, target: QRect) -> None:
        """Give the page the tone chosen for reading (sepia or night).

        Only what is seen on screen changes: the PDF and the printed pages stay
        as they are.
        """
        tone = theme.paper()
        if tone is theme.Paper.WHITE:
            return
        modes = QPainter.CompositionMode
        if tone is theme.Paper.SEPIA:
            steps = ((modes.CompositionMode_Multiply, theme.SEPIA_TONE),)
        else:
            steps = (
                (modes.CompositionMode_Difference, "#ffffff"),  # dark paper, light ink
                (modes.CompositionMode_Screen, theme.NIGHT_PAPER),
                (modes.CompositionMode_Multiply, theme.NIGHT_INK),
            )
        for mode, colour in steps:
            painter.setCompositionMode(mode)
            painter.fillRect(target, QColor(colour))
        painter.setCompositionMode(modes.CompositionMode_SourceOver)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # With "fit to width" the pages change size with the window (for example
        # when a side panel opens): keep reading where we were.
        place = self._place()
        zoom = self._zoom
        self._layout()
        if abs(zoom - self._zoom) > 1e-6:
            self._return_to(place)
        self._scrolled()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            # Moved to a screen with another scale: lay out and draw again.
            self._layout()
            self._scrolled()

    # ---- selecting and copying text ---------------------------------------

    @property
    def has_selection(self) -> bool:
        return self._anchor is not None and self._anchor != self._focus

    def selection(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Where the selection starts and ends, each (page, caret), in reading order."""
        if not self.has_selection:
            return None
        return min(self._anchor, self._focus), max(self._anchor, self._focus)

    def select(self, start: tuple[int, int], stop: tuple[int, int]) -> None:
        """Select from one place to another, each (page, caret)."""
        had = self.has_selection
        self._anchor, self._focus = start, stop
        if had or self.has_selection:
            self.selection_changed.emit(self.has_selection)
        self.viewport().update()

    def select_all(self) -> None:
        if self.page_count:
            self.select((0, 0), (self.page_count - 1, END_OF_PAGE))

    def clear_selection(self) -> None:
        had = self.has_selection
        self._anchor = self._focus = None
        if had:
            self.selection_changed.emit(False)
            self.viewport().update()

    def copy_selection(self) -> None:
        """Put the selected text on the clipboard. ``text_copied`` tells when it is there."""
        chosen = self.selection()
        if chosen is None:
            self.text_copied.emit(0)
            return
        self._copy_id = self.service.copy_text(*chosen)

    def _put_on_clipboard(self, copy_id: int, text: str) -> None:
        if copy_id != self._copy_id:
            return  # an older request, or one of a document that is no longer open
        if text:
            QGuiApplication.clipboard().setText(text)
        self.text_copied.emit(len(text))

    def _want_text(self, page: int) -> None:
        if page not in self._texts and page not in self._asked_texts:
            self._asked_texts.add(page)
            self.service.want_text(page)

    def _store_text(self, page: int, text: PageText) -> None:
        if self._document is None:
            return
        self._asked_texts.discard(page)
        self._texts[page] = text
        while len(self._texts) > PAGE_TEXTS_KEPT:
            self._texts.popitem(last=False)
        if self.has_selection:
            self.viewport().update()

    def _selection_rects(self, page: int):
        chosen = self.selection()
        if chosen is None or not chosen[0][0] <= page <= chosen[1][0]:
            return ()
        text = self._texts.get(page)
        if text is None:
            self._want_text(page)  # painted as soon as its letters arrive
            return ()
        (first, start), (last, stop) = chosen
        return selection_rects(
            text, start if page == first else 0, stop if page == last else len(text)
        )

    def _page_point(self, position: QPoint) -> tuple[int, float, float] | None:
        """The page under a place of the window and the point of that page, in points.

        Above, below or between pages it gives the nearest page.
        """
        if not self._tops:
            return None
        y = self._to_pixels(position.y()) + self._scroll_y()
        page = max(0, bisect.bisect_right(self._tops, y) - 1)
        zoom = self._render_zoom()
        shown_x = (self._to_pixels(position.x()) - self._page_left(page)) / zoom
        shown_y = (y - self._tops[page]) / zoom
        size = self._sizes[page]
        if self._rotation == 90:
            return page, shown_y, size.height - shown_x
        if self._rotation == 180:
            return page, size.width - shown_x, size.height - shown_y
        if self._rotation == 270:
            return page, size.width - shown_y, shown_x
        return page, shown_x, shown_y

    def _caret_at(self, position: QPoint) -> tuple[int, int] | None:
        """The place of the text nearest to a place of the window: (page, caret)."""
        point = self._page_point(position)
        if point is None:
            return None
        page, x, y = point
        text = self._texts.get(page)
        if text is None:
            self._want_text(page)
            return None
        caret = caret_at(text, x, y)
        return None if caret is None else (page, caret)

    def _is_picture_page(self, position: QPoint) -> bool:
        point = self._page_point(position)
        text = self._texts.get(point[0]) if point else None
        return text is not None and not len(text)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.setFocus()
        position = event.position().toPoint()
        place = self._caret_at(position)
        if place is None:
            self.clear_selection()
            if self._is_picture_page(position):
                self.no_text_to_select.emit()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and self._anchor is not None:
            self.select(self._anchor, place)  # Shift+click: up to here
        else:
            self.clear_selection()
            self._anchor = self._focus = place
        self._selecting = True
        self._drag_position = position

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        position = event.position().toPoint()
        if not self._selecting:
            self._update_pointer(position)
            return
        self._drag_position = position
        self._extend_selection()
        outside = position.y() < 0 or position.y() > self.viewport().height()
        if outside and not self._autoscroll.isActive():
            self._autoscroll.start()
        elif not outside:
            self._autoscroll.stop()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._selecting = False
            self._autoscroll.stop()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        place = self._caret_at(event.position().toPoint())
        if event.button() != Qt.MouseButton.LeftButton or place is None:
            return
        page, caret = place
        start, stop = word_at(self._texts[page], caret)
        self.select((page, start), (page, stop))

    def _extend_selection(self) -> None:
        place = self._caret_at(self._drag_position)
        if place is not None and self._anchor is not None and place != self._focus:
            self.select(self._anchor, place)

    def _autoscroll_step(self) -> None:
        """Dragging past the top or the bottom moves the document along."""
        y, height = self._drag_position.y(), self.viewport().height()
        distance = y if y < 0 else y - height
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() + max(-120, min(120, distance)))
        self._extend_selection()

    def _update_pointer(self, position: QPoint) -> None:
        """An I-beam over text, an arrow elsewhere."""
        over_text = False
        point = self._page_point(position)
        if point is not None:
            text = self._texts.get(point[0])
            over_text = text is not None and is_on_text(text, point[1], point[2])
        shape = Qt.CursorShape.IBeamCursor if over_text else Qt.CursorShape.ArrowCursor
        if self.viewport().cursor().shape() != shape:
            self.viewport().setCursor(shape)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self.page_count:
            return
        menu = QMenu(self)
        copy = menu.addAction(self.tr("Copiar"))
        copy.setEnabled(self.has_selection)
        copy.triggered.connect(self.copy_selection)
        menu.addAction(self.tr("Seleccionar todo")).triggered.connect(self.select_all)
        menu.exec(event.globalPos())

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
        elif key == Qt.Key.Key_Escape and self.has_selection:
            self.clear_selection()
        else:
            super().keyPressEvent(event)

    def scroll_to_page(self, page: int) -> None:
        """Put the top of ``page`` (counting from 0) at the top of the window."""
        if 0 <= page < self.page_count:
            gap = self._to_pixels(PAGE_GAP) // 2
            self.verticalScrollBar().setValue(self._to_units(self._tops[page] - gap))
