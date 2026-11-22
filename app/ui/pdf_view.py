"""Shows the pages of a PDF one below the other, with continuous scrolling.

Everything is laid out in real screen pixels, not in Qt's scaled units, so on
screens set to 125 % or 150 % every page pixel lands exactly on one screen
pixel and the text stays sharp.

Pages are drawn by ``RenderService`` in another process. This widget only
copies finished images to the screen, which is what keeps scrolling smooth.
"""

import bisect
import math
import time
from collections import OrderedDict
from dataclasses import replace
from enum import Enum
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QEventLoop,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QCursor,
    QFont,
    QGuiApplication,
    QImage,
    QInputDevice,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPointingDevice,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QFrame,
    QMenu,
    QToolTip,
    QWidget,
)

from app.core import arrange, bookmarks, drawing, margins, notes, pen, places, sheets
from app.core.commands import HIGHLIGHT, MARKUP_KINDS, STRIKEOUT, UNDERLINE, new_name
from app.core.document import PageSize, PdfDocument
from app.core.drawing import ARROW, BOX, DRAW, ERASER, INK, OVAL, SHAPE_TOOL, PageDrawing
from app.core.foreign import OTHER
from app.core.notes import NOTE, TEXT_BOX, PageNote
from app.core.outline import OutlineEntry
from app.core.render_service import (
    MAX_PIXELS_PER_PAGE,
    RenderedPage,
    RenderRequest,
    RenderService,
)
from app.core.search import PageText, SearchHit
from app.core.selection import caret_at, is_on_text, selection_rects, word_at
from app.core.text_layer import AddTextLayer, PageLayer
from app.ui import theme
from app.ui.note_panel import NotePanel
from app.ui.picked_bar import PickedBar
from app.ui.text_editor import TextEditor

PAGE_GAP = 12  # space between pages, in Qt units
SIDE_MARGIN = 16
MIN_ZOOM = 0.2  # screen pixels per point, before the screen scale
MAX_ZOOM = 8.0
ZOOM_STEP = 1.2
REVIEW_KINDS = (HIGHLIGHT, UNDERLINE)  # what the review mode covers
COVER_MARGIN = 1.5  # points around a cover that a click still takes
PLACE_MARGIN = 24  # space left above a heading gone to, in Qt units
WRITING_WAIT_S = 3.0  # longest wait for the text being written to become a change
WHEEL_NOTCH = 120  # what one notch of a mouse wheel sends
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
# What can be held in hand: a marker, the notes, the text, the pen, the shapes
# or the eraser.
TOOLS = (*MARKUP_KINDS, NOTE, TEXT_BOX, DRAW, SHAPE_TOOL, ERASER)
ERASER_REACH = 5.0  # screen units around the pointer that the eraser takes
PICK_REACH = 4.0  # screen units around the pointer that count as on a drawing
HANDLE_SIZE = 9.0  # side of the little squares that resize, in screen units
HANDLE_REACH = 8.0  # how near a handle the pointer grabs it
DRAG_START = 3.0  # screen units the pointer travels before a click becomes a drag
NUDGE, BIG_NUDGE = 1.0, 10.0  # points an arrow key moves what is picked (with Shift)
ERASER_CURSOR_SIZE = 20
NOTE_REACH = 3.0  # points around a note that still count as on it
TIP_LETTERS = 400  # of a note, shown when the pointer rests on it
# Fingers on a touch screen.
TOUCH_SLOP = 8.0  # screen units a finger travels before it is moving the page
DOUBLE_TAP_REACH = 14.0  # screen units between two taps that are a double one
HOLD_MS = 500  # a finger resting this long acts like the mouse (select, drag)
FLING_MS = 16  # the page keeps gliding after a quick push, in steps this long
FLING_START = 0.35  # screen units per millisecond: slower than this, no glide
FLING_KEEPS = 0.94  # how much of its speed the glide keeps at each step
FLING_LOOKS_BACK = 0.1  # seconds of the finger's way that tell its speed
_TABLET = (
    QEvent.Type.TabletPress,
    QEvent.Type.TabletMove,
    QEvent.Type.TabletRelease,
)
_TOUCH = (
    QEvent.Type.TouchBegin,
    QEvent.Type.TouchUpdate,
    QEvent.Type.TouchEnd,
    QEvent.Type.TouchCancel,
)
_PEN_BUTTONS = Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton


def _engine_pixels(points: float, zoom: float) -> int:
    """Pixels the PDF engine uses for a length: it rounds up, with a tiny margin.

    The layout must use exactly the same number. With one pixel of difference
    the image would have to be stretched, and stretched text looks blurry.
    """
    return max(1, math.ceil(points * zoom - 0.001))


def _same_size(image: QImage, target: QRect) -> bool:
    """True if the image fits its place, give or take one pixel of rounding."""
    return abs(image.width() - target.width()) <= 1 and abs(image.height() - target.height()) <= 1


# How a change being made is told apart: put back from the journal, not new.
RECOVER, RECOVER_UNDO = "recover", "recover_undo"


def _arrow_head(start: QPointF, end: QPointF, width: float) -> list[QPointF]:
    """The two short lines at the end of an arrow, as the PDF viewers draw them."""
    length = math.hypot(end.x() - start.x(), end.y() - start.y())
    if length == 0:
        return [end]
    size = max(6.0, width * 4.5)
    ux, uy = (end.x() - start.x()) / length, (end.y() - start.y()) / length
    back = QPointF(end.x() - ux * size, end.y() - uy * size)
    side = size * 0.5
    return [
        QPointF(back.x() - uy * side, back.y() + ux * side),
        end,
        QPointF(back.x() + uy * side, back.y() - ux * side),
    ]


def _sketch_of(order) -> tuple | None:
    """What an order draws, to paint it before the engine does: page, kind,
    strokes, colour, thickness, opacity, for a stroke made with a pen that
    feels it the pressures and, for a shape, whether it is filled and dashed.
    None if it is not a drawing."""
    if isinstance(order, drawing.AddInk):
        strokes = [list(stroke) for stroke in order.strokes]
        pressures = order.pressures if order.pressed else ()
        return (
            order.page,
            INK,
            strokes,
            order.color,
            order.width,
            order.opacity,
            pressures,
            (False, False),
        )
    if isinstance(order, drawing.AddShape):
        ends = [[order.start, order.end]]
        return (
            order.page,
            order.kind,
            ends,
            order.color,
            order.width,
            order.opacity,
            (),
            (order.fill, order.dashed),
        )
    return None


_ERASER_CURSOR: QCursor | None = None


def _eraser_cursor() -> QCursor:
    """A small ring: what is inside it is what the eraser takes."""
    global _ERASER_CURSOR
    if _ERASER_CURSOR is None:
        pixmap = QPixmap(ERASER_CURSOR_SIZE, ERASER_CURSOR_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ring = QRectF(2.5, 2.5, ERASER_CURSOR_SIZE - 5, ERASER_CURSOR_SIZE - 5)
        painter.setPen(QPen(QColor("white"), 3))
        painter.drawEllipse(ring)
        painter.setPen(QPen(QColor("#202020"), 1.4))
        painter.drawEllipse(ring)
        painter.end()
        _ERASER_CURSOR = QCursor(pixmap)
    return _ERASER_CURSOR


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
    # A page asked with want_print_pages is ready (RenderedPage), cannot be drawn
    # (its number) or was lost when the helper restarted (its number: ask again).
    print_page_ready = Signal(object)
    print_page_failed = Signal(int)
    print_page_lost = Signal(int)
    _page_failed = Signal(int, float, str)
    # Saving: there are changes not saved yet (or no longer); the document was
    # saved (the number of the save and the file it lives in now); it could not
    # be saved (number, one of the kinds of ``app.core.saving``, details).
    modified_changed = Signal(bool)
    # The document was changed (a mark was made, undone or made again): the
    # pages that look different now. ``edit_failed`` says a change did not work.
    pages_changed = Signal(object)
    # Pages were put in or taken away: every page from there on has another number.
    pages_reshaped = Signal()
    pages_moved = Signal(int, int)  # a page put in at (1) or taken from (-1) a place
    text_changed = Signal(object)  # the letters of these pages are different (OCR)
    # The grey picture of a page, to read its text: page, width, height, dpi, bytes.
    reading_ready = Signal(int, int, int, int, object)
    reading_failed = Signal(int, str)
    # The pages that are only a picture (scanned), once the whole document has
    # been looked at: their numbers (from 0) and how many pages there are.
    scanned_found = Signal(object, int)
    _scanned_ready = Signal(object, int, object)
    edit_failed = Signal(str)
    history_changed = Signal()  # what can be undone or done again is different
    markup_tool_changed = Signal(str)  # the tool in hand ("" for none)
    notes_changed = Signal(int)  # the notes and text boxes of a page are known or different
    _notes_ready = Signal(int, object)
    _drawings_ready = Signal(int, object)
    picked_changed = Signal()  # an annotation is picked, or not any more
    item_copied = Signal()  # the picked annotation was copied, to paste it
    pen_seen_changed = Signal()  # a pen touched a page for the first time
    annotations_listed = Signal(object)  # every annotation of the document (list of Entry)
    _annotations_ready = Signal(int, object)
    # An article or section looked for (``go_to_place``): whether it was found.
    place_answered = Signal(bool)
    _place_ready = Signal(int, object)
    annotations_shown_changed = Signal(bool)  # what was put on the pages is seen, or hidden
    review_changed = Signal(bool)  # the review mode (what is marked, covered) on or off
    # The annotation copied last, for every document: the order that puts it.
    copied = None
    text_style_chosen = Signal(dict)  # the look given to a text while writing it
    _changed = Signal(int, object, object, bool)
    _change_failed = Signal(int, str)
    saved = Signal(int, object)
    save_failed = Signal(int, str, str)
    _saved = Signal(int, object)

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
            on_print=self.print_page_ready.emit,
            on_print_failed=self.print_page_failed.emit,
            on_print_lost=self.print_page_lost.emit,
            on_saved=self._saved.emit,
            on_save_failed=self.save_failed.emit,
            on_changed=self._changed.emit,
            on_change_failed=self._change_failed.emit,
            on_notes=self._notes_ready.emit,
            on_drawings=self._drawings_ready.emit,
            on_scanned=self._scanned_ready.emit,
            on_reading=self.reading_ready.emit,
            on_reading_failed=self.reading_failed.emit,
            on_annotations=self._annotations_ready.emit,
            on_place=self._place_ready.emit,
        )
        self._list_id = 0
        self._pick_when_read: tuple[int, str] | None = None
        self._annotations_ready.connect(self._annotations_came)
        self._place_ready.connect(self._place_came)
        self._place_asked: tuple[int, places.Wanted] | None = None
        # The place found last, (wanted, page, letter): the same text again goes on.
        self._place_shown: tuple[places.Wanted, int, int] | None = None
        self.scanned_pages: list[int] = []  # known once the helper has looked
        self.recognised_pages: list[int] = []  # scans that already have their text
        self.scanned_known = False  # whether it has looked at every page
        self._scanned_ready.connect(self._store_scanned)
        self._notes_ready.connect(self._store_notes)
        self._drawings_ready.connect(self._store_drawings)
        # What is drawn or marked on each page, for the eraser.
        self._drawings: dict[int, list[PageDrawing]] = {}
        self._erased: dict[int, set[str]] = {}  # taken away, until the page is read again
        self._erasing = False
        # The annotation picked to move, resize, copy or remove: (page, name).
        self._picked: tuple[int, str] | None = None
        # While it is dragged: what it was, from where, by which handle, and
        # the order that would leave it where the pointer is now.
        self._grab: dict | None = None
        # Over what is picked: its colour and Borrar, at hand.
        self.picked_bar = PickedBar(self.viewport())
        self.picked_bar.color_chosen.connect(self.recolor_picked)
        self.picked_bar.remove_wanted.connect(self.remove_picked)
        self.picked_changed.connect(self._place_picked_bar)
        # Orders just sent that leave an annotation somewhere else, by its name:
        # where it is now, until its page is read again.
        self._latest: dict[str, object] = {}
        # What is being drawn right now: (page, tool, points), all as the page is shown.
        self._sketch: tuple[int, str, list[tuple[float, float]]] | None = None
        self._sketch_from = QPoint()  # where the stroke being drawn started, in the window
        # Drawn and sent, still to appear in the picture of its page: by change
        # number while the helper puts it, then by page until it is drawn again.
        self._sent_sketches: dict[int, tuple] = {}
        self._settling: dict[int, list[tuple]] = {}
        # False: the pages are seen clean, without marks, notes or drawings.
        self._annotations_shown = True
        # The review mode: what is highlighted or underlined is covered, and a
        # click uncovers one (by its name) until the mode is left.
        self._review = False
        self._uncovered: set[str] = set()
        self._review_click = False  # the press uncovered something: its release does nothing
        # A text being changed in its editor: (page, its name). Its page is
        # drawn without it, so that only the editor shows it.
        self._hiding: tuple[int, str] | None = None
        # The pen and the fingers (the window gives what the user chose).
        self.pen_pressure = True  # a stroke is thicker where the pen presses more
        self.finger_mode = pen.AUTO
        self.pen_seen = False
        # How hard the pen pressed at each point of what is being drawn, if it
        # is the pen that draws it; and how hard it presses right now.
        self._sketch_pressures: list[float] | None = None
        self._pen_pressure: float | None = None
        self._pen_down = False
        self._pen_at = float("-inf")  # when the pen was last on or near the screen
        self._last_tap = (float("-inf"), QPoint())  # when and where it last went down
        # The fingers on the screen: what they are doing ("wait", "pan", "zoom",
        # "tool", "mouse" or "ignored") and where each one is.
        self._touch: dict | None = None
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.setInterval(HOLD_MS)
        self._hold.timeout.connect(self._finger_held)
        self._fling = QTimer(self)
        self._fling.setInterval(FLING_MS)
        self._fling.timeout.connect(self._fling_step)
        self._fling_speed = (0.0, 0.0)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        # How the pen and the shapes draw (the window gives what the user chose).
        self.draw_color = drawing.DRAW_COLOR
        self.draw_width = drawing.DEFAULT_WIDTH
        self.draw_opacity = 1.0
        self.shape_kind = drawing.DEFAULT_SHAPE
        self.shape_color = drawing.SHAPE_COLOR
        self.shape_width = drawing.DEFAULT_WIDTH
        self.shape_opacity = 1.0
        self.shape_fill = False  # a closed shape is filled with a light tone of its colour
        self.shape_dashed = False
        self._notes: dict[int, list[PageNote]] = {}  # notes and text boxes by page
        self._asked_notes: set[int] = set()
        # Where one is being written: a panel, or the page itself for a text.
        self.note_panel: NotePanel | TextEditor | None = None
        self._editor_place: tuple[int, float, float] | None = None  # of that text
        # How new notes and text are made (the window gives what the user chose).
        self.note_color = notes.NOTE_COLOR
        self.text_font = notes.SANS
        self.text_size = notes.TEXT_SIZE
        self.text_bold = False
        self.typed_arrows = True  # "->" turns into an arrow while writing a text
        self.text_color = notes.TEXT_COLOR
        self._changed.connect(self._change_done)
        self._change_failed.connect(self._change_did_not_work)
        self._stale: set[int] = set()  # pages whose picture is from before a change
        self._undo: list = []  # orders carried out, the last one at the end
        self._redo: list = []  # orders undone, that can be carried out again
        self._changing: dict[int, str] = {}  # change number -> "do", "undo" or "redo"
        self._markup_tool = ""  # the marker in hand: every selection gets marked
        self.markup_colors: dict[str, tuple[float, float, float]] = {}
        self.markup_opacity: dict[str, float] = {}
        # Where every change is written down the moment it is made (the window
        # gives it when a document is opened). None: nothing is written down.
        self.journal = None
        self._saved.connect(self._document_saved)
        self.save_failed.connect(self._save_did_not_work)
        self._changes = 0  # changes made to the document since it was opened
        self._saved_changes = 0  # how many of them are in the file
        self._saves: dict[int, int] = {}  # save number -> changes it carries
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

    # ---- changing the document -------------------------------------------

    @property
    def markup_tool(self) -> str:
        """The tool in hand: a marker ("highlight", "underline", "strikeout"),
        the notes ("note"), the text ("text_box"), the pen ("draw"), the shapes
        ("shapes"), the eraser ("eraser") or ""."""
        return self._markup_tool

    def set_markup_tool(self, kind: str) -> None:
        """Take a tool. A marker marks every text selected from now on; with
        the notes or the text, a click on the page starts one there; the pen
        and the shapes draw while the button is held, and the eraser takes
        away what it is passed over."""
        kind = kind if kind in TOOLS else ""
        if kind != self._markup_tool:
            self._sketch = None
            self._erasing = False
            self._grab = None
            if kind:
                self.pick(None)
            self._markup_tool = kind
            self.markup_tool_changed.emit(kind)
            self._update_pointer(self.viewport().mapFromGlobal(QCursor.pos()))

    def mark_selection(self, kind: str) -> bool:
        """Highlight, underline or strike out the selected text. False if there is none."""
        chosen = self.selection()
        if chosen is None or kind not in MARKUP_KINDS or self._document is None:
            return False
        self.set_annotations_shown(True)  # what is put now must be seen
        number = self.service.mark_text(
            kind,
            chosen[0],
            chosen[1],
            self.markup_colors.get(kind),
            self.markup_opacity.get(kind, 1.0),
        )
        self._changing[number] = "do"
        self.clear_selection()
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def annotations_shown(self) -> bool:
        return self._annotations_shown

    def set_annotations_shown(self, shown: bool) -> None:
        """See the pages with what was put on them, or clean.

        Nothing is taken away: hidden, the marks, notes and drawings stay in
        the document, they are just not drawn (and cannot be picked or erased).
        """
        shown = bool(shown)
        if shown == self._annotations_shown:
            return
        self._annotations_shown = shown
        if not shown:
            self.close_note_panel(keep=True)
            self._let_go()
            self.pick(None)
            self.set_review(False)  # nothing to cover on a clean page
        # Every picture is of the other kind: they stay until the new ones come.
        self._stale.update(range(self.page_count))
        self._settling.clear()
        self._request_pages()
        self.viewport().update()
        self.annotations_shown_changed.emit(shown)

    def undo(self) -> bool:
        """Take back the last change. False if there is nothing to take back."""
        if not self._undo:
            return False
        self.set_annotations_shown(True)  # a change that is not seen would be a trap
        order = self._undo.pop()
        self._changing[self.service.apply(order, undo=True)] = "undo"
        self.history_changed.emit()
        return True

    def undo_all(self) -> int:
        """Take back every change made since the document was opened.

        Returns how many. They can be brought back one by one with ``redo``.
        """
        count = 0
        while self.undo():
            count += 1
        return count

    def redo(self) -> bool:
        """Carry out again the last change taken back."""
        if not self._redo:
            return False
        self.set_annotations_shown(True)
        order = self._redo.pop()
        self._changing[self.service.apply(order)] = "redo"
        self.history_changed.emit()
        return True

    def _change_done(self, number: int, order: object, pages: object, _undone: bool) -> None:
        how = self._changing.pop(number, None)
        if how is None or self._document is None:
            return  # belongs to a document that is no longer open
        sketch = self._sent_sketches.pop(number, None)
        if sketch is not None:  # it stays painted until its page is drawn again
            self._settling.setdefault(sketch[0], []).append(sketch)
        undone = how in ("undo", RECOVER_UNDO)
        if undone:
            self._redo.append(order)
        else:
            self._undo.append(order)
            if how == "do":
                self._redo.clear()  # a new change: the undone ones are gone
        if self.journal is not None and how not in (RECOVER, RECOVER_UNDO):
            # Written down at once: a power cut from here on does not lose it.
            self.journal.record(order, undone)
        if hasattr(order, "page_change"):
            self._reshape(*order.page_change(undone), getattr(order, "size", None))
            if how in ("do", "redo"):
                self.scroll_to_page(order.page_change(False)[0])
        grown = margins.size_change(order, undone)
        if grown:
            self._resize(grown)
        # The pictures of those pages are old: they stay on screen until the
        # new ones arrive, so nothing blinks.
        self._stale.update(page for page in pages if 0 <= page < self.page_count)
        for page in pages:
            self._want_notes(page, again=True)  # what is on those pages may be different
        if getattr(order, "text_change", False):
            for page in pages:  # their letters are read again when needed
                self._texts.pop(page, None)
                self._asked_texts.discard(page)
        self.mark_modified()
        self._request_pages()
        self.history_changed.emit()
        self.pages_changed.emit(list(pages))
        if getattr(order, "text_change", False):
            self.text_changed.emit(list(pages))

    def _store_scanned(self, pages: object, count: int, recognised: object = ()) -> None:
        if self._document is None or count != self.page_count:
            return  # about another document, or before pages were put or taken
        self.scanned_pages = sorted(pages)
        self.recognised_pages = sorted(recognised)
        self.scanned_known = True
        self.scanned_found.emit(list(self.scanned_pages), count)

    def _reshape(self, at: int, by: int, size) -> None:
        """Follow a page put in at ``at`` (``by`` 1) or taken from there (-1).

        The pictures already drawn move with their pages, so nothing blinks;
        what was read from the pages (letters, notes, drawings) is read again.
        """
        if by > 0:
            width, height = size if size else (self._sizes[min(at, len(self._sizes) - 1)])
            self._sizes.insert(at, PageSize(float(width), float(height)))
        elif 0 <= at < len(self._sizes) and len(self._sizes) > 1:
            del self._sizes[at]
        else:
            return
        place = self._place()

        def moved(page: int) -> int | None:
            if page < at:
                return page
            if by < 0 and page == at:
                return None  # that page is gone
            return page + by

        cache, self._cache = self._cache, OrderedDict()
        self._cache_bytes = 0
        for page, kept in cache.items():
            new = moved(page)
            if new is not None:
                self._cache[new] = kept
                self._cache_bytes += kept[1].sizeInBytes()
        self._stale = {new for new in map(moved, self._stale) if new is not None}
        self._failed_pages = {new for new in map(moved, self._failed_pages) if new is not None}
        self._marks = {}
        self._current_mark = None
        self._texts.clear()
        self._asked_texts.clear()
        self._notes.clear()
        self._asked_notes.clear()
        self._drawings.clear()
        self._erased.clear()
        self._sent_sketches.clear()
        self._settling.clear()
        self._latest.clear()
        self._place_shown = None  # its page may have moved
        self._grab = None
        self.pick(None)
        self.close_note_panel()
        self.clear_selection()
        page, inside = place
        moved_page = moved(page)
        self._layout()
        self._return_to(
            (min(at, self.page_count - 1) if moved_page is None else moved_page, inside)
        )
        self._current_page = -1  # told again, with the new count
        self._scrolled()
        self.pages_moved.emit(at, by)
        self.pages_reshaped.emit()

    def _resize(self, grown: dict[int, tuple[float, float]]) -> None:
        """Some pages are bigger or smaller now (margins): lay them out again,
        keeping the place being read."""
        place = self._place()
        for page, (wider, taller) in grown.items():
            if 0 <= page < len(self._sizes):
                size = self._sizes[page]
                self._sizes[page] = PageSize(size.width + wider, size.height + taller)
        self._marks = {}
        self._current_mark = None
        self._place_shown = None  # the letters moved
        self.pick(None)
        self.clear_selection()
        for page in grown:
            self._texts.pop(page, None)
            self._asked_texts.discard(page)
        self._layout()
        self._return_to(place)
        self._scrolled()
        self.pages_reshaped.emit()

    def recover(self, entries) -> int:
        """Put back changes read from the journal: (order, undone) pairs.

        They come back as changes not saved. They are not written down again:
        the journal already has them. Returns how many were asked for.
        """
        if self._document is None:
            return 0
        for order, undone in entries:
            number = self.service.apply(order, undo=undone)
            self._changing[number] = RECOVER_UNDO if undone else RECOVER
        return len(entries)

    def _change_did_not_work(self, number: int, details: str) -> None:
        if self._sent_sketches.pop(number, None) is not None:
            self.viewport().update()
        self._latest.clear()
        if self._changing.pop(number, None) is not None:
            self.history_changed.emit()
            self.edit_failed.emit(details)

    # ---- saving ---------------------------------------------------------

    @property
    def modified(self) -> bool:
        """True while the document has changes that are not in its file."""
        return self._changes != self._saved_changes

    @property
    def saving(self) -> bool:
        return bool(self._saves)

    def mark_modified(self) -> None:
        """Called after every change made to the document."""
        was = self.modified
        self._changes += 1
        if not was:
            self.modified_changed.emit(True)

    def save(self, target: str | Path | None = None) -> int:
        """Save the document in its file, or in ``target`` ("Save as").

        The answer comes through ``saved`` or ``save_failed`` with the number
        returned here. After "Save as" the document lives in the new file.
        """
        number = self.service.save(target)
        self._saves[number] = self._changes
        return number

    def _document_saved(self, number: int, path: object) -> None:
        was = self.modified
        if self._saves.pop(number, None) is not None:
            # The helper answers in the order it was asked: every change it has
            # answered so far was asked before this save, so it is in the file,
            # even one still on its way when Guardar was pressed.
            self._saved_changes = self._changes
            if self.journal is not None:
                self.journal.saved(self.journal.count, path)  # it leaves the journal
        if self._document is not None:
            self._document.path = Path(path)
        if was and not self.modified:
            self.modified_changed.emit(False)
        self.saved.emit(number, path)

    def _save_did_not_work(self, number: int, _kind: str, _details: str) -> None:
        self._saves.pop(number, None)

    def close_document(self) -> None:
        if self._document is not None:
            self._document.close()
            self.service.close_document()
        was_modified = self.modified
        if not self._annotations_shown:  # the next document opens with everything in sight
            self._annotations_shown = True
            self.annotations_shown_changed.emit(True)
        self.set_review(False)
        self._changes = self._saved_changes = 0
        self._place_asked = self._place_shown = None
        self._saves.clear()
        self.journal = None
        self._stale.clear()
        self._changing.clear()
        if self._undo or self._redo:
            self._undo.clear()
            self._redo.clear()
            self.history_changed.emit()
        if was_modified:
            self.modified_changed.emit(False)
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
        self._notes.clear()
        self._asked_notes.clear()
        self._drawings.clear()
        self.scanned_pages = []
        self.recognised_pages = []
        self.scanned_known = False
        self._erased.clear()
        self._erasing = False
        self._sketch = None
        self._drop_touch()
        self._fling.stop()
        self._sent_sketches.clear()
        self._settling.clear()
        self._grab = None
        self._latest.clear()
        self.pick(None)
        self.close_note_panel()
        self._selecting = False
        self._autoscroll.stop()
        self.clear_selection()
        self._layout()

    @property
    def outline(self) -> list[OutlineEntry]:
        """Sections of the document. Arrives a moment after opening it."""
        return self._outline

    # ---- the user's bookmarks (app.core.bookmarks) ----------------------

    def _top_shown(self) -> tuple[int, float]:
        """The page at the top of the window and how far down it is seen (points)."""
        page = max(0, self._current_page)
        if self._rotation != 0 or not 0 <= page < self.page_count:
            return page, 0.0
        down = (self._scroll_y() - self._tops[page]) / self._render_zoom()
        return page, max(0.0, min(down, self._sizes[page].height))

    def add_bookmark(self, title: str = "") -> str:
        """Put a bookmark where the window is (the top of what is seen).

        Without ``title`` it is named after the first heading in sight
        ("Artículo 14. Igualdad…") or the page. Returns the title, or "".
        """
        if self._document is None or not self.page_count:
            return ""
        page, top = self._top_shown()
        if not title:
            text = self._texts.get(page)
            seen = self._to_pixels(self.viewport().height()) / self._render_zoom()
            title = places.heading_near(text, top, top + seen) if text is not None else ""
        title = title or self.tr("Página {0}").format(page + 1)
        order = bookmarks.AddBookmark(page, round(top, 1), title, new_name(), self._group_title())
        return title if self._do(order) else ""

    def add_margin(
        self, left: float, right: float, bottom: float, every_page: bool = False
    ) -> bool:
        """Blank room (points) on the sides or below the page being read, or
        every page. Deshacer takes it away again."""
        if self._document is None or not self.page_count:
            return False
        pages = tuple(range(self.page_count)) if every_page else (max(0, self._current_page),)
        largest = margins.LARGEST
        if any(
            self._sizes[page].width + left + right > largest
            or self._sizes[page].height + bottom > largest
            for page in pages
        ):
            return False
        return self._do(margins.AddMargin(pages, left, right, bottom, new_name()))

    def _group_title(self) -> str:
        return self.tr("Mis marcadores")  # the item of the outline that holds them

    def _bookmark_order(self, entry: OutlineEntry) -> bookmarks.AddBookmark:
        return bookmarks.AddBookmark(
            entry.page, entry.top or 0.0, entry.title, entry.bookmark, self._group_title()
        )

    def remove_bookmark(self, entry: OutlineEntry) -> bool:
        if not entry.bookmark or self._document is None:
            return False
        return self._do(notes.Remove(self._bookmark_order(entry)))

    def rename_bookmark(self, entry: OutlineEntry, title: str) -> bool:
        title = " ".join(title.split())
        if not entry.bookmark or not title or title == entry.title or self._document is None:
            return False
        old = self._bookmark_order(entry)
        return self._do(notes.Replace(old, replace(old, title=title)))

    def go_to_outline(self, entry: OutlineEntry) -> None:
        """Go where an entry of the outline leads: its page, or the very place."""
        if not 0 <= entry.page < self.page_count:
            return
        if entry.top is None or self._rotation != 0:
            self.scroll_to_page(entry.page)
            return
        top = self._tops[entry.page] + entry.top * self._render_zoom()
        self.verticalScrollBar().setValue(self._to_units(top - self._to_pixels(PLACE_MARGIN)))

    def _store_outline(self, entries: list[OutlineEntry]) -> None:
        if self._document is None:
            return
        self._outline = entries
        self.outline_changed.emit()

    def page_sizes(self) -> list[PageSize]:
        """Sizes of the pages as the document has them (the view's turn not applied)."""
        return list(self._sizes)

    def want_print_pages(self, pages: list[int], zoom: float, annotations: bool = True) -> None:
        """Ask for ``pages`` drawn for a printer (an empty list cancels).

        They are drawn as the document is: the turn of the view and the tone of
        the paper are only for the screen. Without ``annotations``, clean.
        """
        if self._document is None:
            return
        self.service.want_prints([RenderRequest(page, zoom, 0, annotations) for page in pages])

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
            first = self._shown_rect(hit.page, hit.rects[0])
            last = self._shown_rect(hit.page, hit.rects[-1])
            self._bring_into_view(hit.page, first, last)
        self.viewport().update()

    def want_annotations(self) -> None:
        """Ask for every annotation of the document. They arrive in
        ``annotations_listed``, as the document is when the helper reads them."""
        if self._document is not None:
            self._list_id = self.service.list_annotations()

    def _annotations_came(self, list_id: int, entries: object) -> None:
        if list_id == self._list_id and self._document is not None:
            self.annotations_listed.emit(list(entries))

    def go_to_place(self, typed: str) -> bool:
        """Go to an article, a section, a chapter… written as people write it
        ("art. 14", "3.2", "capítulo II"). False if the text is not one.

        The answer comes through ``place_answered``. The same text again goes
        on to the next place with that number (a second law in the document).
        """
        wanted = places.parse_wanted(typed)
        if wanted is None or self._document is None:
            return False
        after = None
        if self._place_shown is not None and self._place_shown[0] == wanted:
            after = self._place_shown[1:]
        self._place_asked = (self.service.find_place(wanted, after), wanted)
        return True

    def _place_came(self, place_id: int, place: object) -> None:
        asked, self._place_asked = self._place_asked, None
        if asked is None or asked[0] != place_id or self._document is None:
            if asked is not None and asked[0] != place_id:
                self._place_asked = asked  # an older answer: still waiting
            return
        if place is None or not 0 <= place.page < self.page_count:
            self.place_answered.emit(False)
            return
        self._place_shown = (asked[1], place.page, place.letter)
        rect = self._shown_rect(place.page, place.rect)
        zoom = self._render_zoom()
        top = self._tops[place.page] + rect[1] * zoom
        margin = self._to_pixels(PLACE_MARGIN)
        self.verticalScrollBar().setValue(self._to_units(top - margin))
        self._bring_into_view(place.page, rect, rect)  # sideways, with a lot of zoom
        self.place_answered.emit(True)

    def show_annotation(self, page: int, rect, name: str = "") -> None:
        """Bring an annotation into view (``rect`` as the page is shown) and
        pick it, so it can be moved or removed at once."""
        if not 0 <= page < self.page_count:
            return
        shown = self._shown_rect(page, tuple(rect))  # the view may be turned
        self._bring_into_view(page, shown, shown)
        if name and self._annotations_shown:
            item = self._item(page, name)
            if item is not None:
                self.pick(item)
            else:
                self._pick_when_read = (page, name)
                self._want_notes(page)
        self.viewport().update()

    def _bring_into_view(self, page: int, first, last) -> None:
        """Scroll, if needed, so that the part of a page from ``first`` to
        ``last`` (rectangles as the page is drawn) is seen."""
        zoom = self._render_zoom()
        top = self._tops[page] + min(first[1], last[1]) * zoom
        bottom = self._tops[page] + max(first[3], last[3]) * zoom
        view_top = self._scroll_y()
        view_height = self._to_pixels(self.viewport().height())
        if top < view_top or bottom > view_top + view_height:
            self.verticalScrollBar().setValue(self._to_units(top - view_height / 3))
        # With a lot of zoom the result can be off to one side.
        page_left = self._page_left(page) + self._scroll_x()
        left = page_left + min(first[0], last[0]) * zoom
        right = page_left + max(first[2], last[2]) * zoom
        view_left = self._scroll_x()
        view_width = self._to_pixels(self.viewport().width())
        if left < view_left or right > view_left + view_width:
            self.horizontalScrollBar().setValue(self._to_units(left - view_width / 3))

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

    def zoom_around(self, factor: float, position) -> None:
        """Multiply the zoom by ``factor`` keeping still what is under ``position``.

        ``position`` is a point of the visible area (where the pointer is): the
        spot of the page under it stays under it, like in a map.
        """
        x, y = self._to_pixels(position.x()), self._to_pixels(position.y())
        anchor = None
        if self._tops:
            height = self._scroll_y() + y
            page = max(0, bisect.bisect_right(self._tops, height) - 1)
            if self._heights[page] and self._widths[page]:
                down = (height - self._tops[page]) / self._heights[page]
                across = (x - self._page_left(page)) / self._widths[page]
                anchor = (page, down, across)
        self.set_zoom(self.zoom * factor)
        if anchor is None or anchor[0] >= len(self._tops):
            return
        page, down, across = anchor
        top = self._tops[page] + down * self._heights[page] - y
        self.verticalScrollBar().setValue(self._to_units(top))
        width = max(self._to_pixels(self.viewport().width()), self._content_width)
        left = (width - self._widths[page]) // 2 + across * self._widths[page] - x
        self.horizontalScrollBar().setValue(self._to_units(left))

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

    def fit_comfortable(self) -> None:
        """Back to the size a document has when it is opened."""
        self._fit = Fit.COMFORTABLE
        self._apply_zoom(self._zoom_for_fit())

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
        self._place_editor()
        self._place_picked_bar()
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
            if page not in self._cache or self._cache[page][0] != zoom or page in self._stale:
                self._wanted.append(RenderRequest(page, zoom, self._rotation, self._look(page)))
        self.service.want(self._wanted)
        for page in visible:
            self._want_notes(page)

    def _look(self, page: int) -> bool | tuple[str, ...]:
        """What of the annotations a page is drawn with (see ``RenderRequest``)."""
        if self._hiding is not None and self._hiding[0] == page and self._annotations_shown:
            return (self._hiding[1],)
        return self._annotations_shown

    def _helper_restarted(self) -> None:
        """The helper died and a new one takes over: ask again for what was pending."""
        self._asked_texts = set(self._texts)  # letters asked for and never received
        for page in sorted(self._asked_notes):
            self.service.want_notes(page)
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
        if result.annotations != self._look(result.page):
            return  # drawn before the annotations were hidden or shown
        image = QImage(
            result.samples,
            result.width,
            result.height,
            result.stride,
            QImage.Format.Format_RGB888,
        ).copy()  # own copy: the bytes object will not outlive this call
        self._stale.discard(result.page)
        if result.page not in {sketch[0] for sketch in self._sent_sketches.values()}:
            self._settling.pop(result.page, None)  # the picture has it now
        old = self._cache.pop(result.page, None)
        if old is not None:
            self._cache_bytes -= old[1].sizeInBytes()
        self._cache[result.page] = (result.zoom, image)
        self._cache_bytes += image.sizeInBytes()
        self._trim_cache()
        self.page_drawn.emit(result.page, result.seconds)
        if isinstance(result.annotations, tuple) and isinstance(self.note_panel, TextEditor):
            self.note_panel.set_covering(False)  # the page no longer shows the old text
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
            if self._review:
                self._paint_covers(painter, page, target, zoom)
            self._paint_sketches(painter, page, target, zoom)

    # ---- review mode ------------------------------------------------------

    @property
    def review(self) -> bool:
        return self._review

    def set_review(self, on: bool) -> None:
        """Cover what is highlighted or underlined, to try to remember it.

        Nothing changes in the document: the covers are only painted on the
        window. A click on one uncovers it; another click covers it again.
        """
        on = bool(on) and self._document is not None
        if on == self._review:
            return
        self._review = on
        self._uncovered.clear()
        if on:
            self.set_annotations_shown(True)  # the covers go where the marks are
            self.clear_selection()
            self.pick(None)
        self.viewport().update()
        self.review_changed.emit(on)

    def cover_all(self) -> None:
        """Cover again everything uncovered."""
        if self._uncovered:
            self._uncovered.clear()
            self.viewport().update()

    def covers_of(self, page: int) -> list[PageDrawing]:
        """The marks that are covered in the review mode on a page (all of
        them, uncovered or not), in reading order."""
        return [item for item in self._drawings.get(page, ()) if item.kind in REVIEW_KINDS]

    def uncovered(self, name: str) -> bool:
        return name in self._uncovered

    def _cover_under(self, position: QPoint) -> PageDrawing | None:
        point = self._point_on_page(position)
        if point is None:
            return None
        page, x, y = point
        for item in self.covers_of(page):
            for x0, y0, x1, y1 in item.rects:
                if x0 - COVER_MARGIN <= x <= x1 + COVER_MARGIN and (
                    y0 - COVER_MARGIN <= y <= y1 + COVER_MARGIN
                ):
                    return item
        return None

    def toggle_cover(self, name: str) -> None:
        if name in self._uncovered:
            self._uncovered.discard(name)
        else:
            self._uncovered.add(name)
        self.viewport().update()

    def _paint_covers(self, painter: QPainter, page: int, target: QRect, zoom: float) -> None:
        """A block over every covered mark, in its colour, with no text seen."""
        scale = self._scale()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for item in self.covers_of(page):
            if item.name in self._uncovered:
                continue
            color = QColor.fromRgbF(*item.color)
            fill = QColor(color).darker(115) if color.lightnessF() > 0.85 else color
            painter.setPen(QPen(fill.darker(130), max(1.0, scale)))
            painter.setBrush(fill)
            for rect in item.rects:
                x0, y0, x1, y1 = self._shown_rect(page, rect)
                block = QRectF(x0 * zoom, y0 * zoom, (x1 - x0) * zoom, (y1 - y0) * zoom)
                block = block.adjusted(-scale, -scale, scale, scale)
                painter.drawRoundedRect(
                    block.translated(target.left(), target.top()), 2 * scale, 2 * scale
                )
        painter.restore()

    def _paint_sketches(self, painter: QPainter, page: int, target: QRect, zoom: float) -> None:
        """What is being drawn or dragged on a page, and what was just put and
        is not in its picture yet (so that the line never blinks when it is
        let go). Then, the frame of what is picked."""
        waiting = [*self._settling.get(page, ()), *self._sent_sketches.values()]
        if self._sketch is not None:
            kind, color, width, opacity = self._sketch_style(self._sketch[1])
            pressed = (self._sketch_pressures,) if self._sketch_pressures else ()
            look = (self.shape_fill, self.shape_dashed) if kind != INK else (False, False)
            waiting.append(
                (self._sketch[0], kind, [self._sketch[2]], color, width, opacity, pressed, look)
            )
        dragged = self._grab["change"].new if self._grab and self._grab["change"] else None
        if dragged is not None and _sketch_of(dragged) is not None:
            waiting.append(_sketch_of(dragged))
        waiting = [sketch for sketch in waiting if sketch[0] == page]
        painter.save()
        painter.setClipRect(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        try:
            for _page, kind, strokes, color, width, opacity, pressures, look in waiting:
                tone = QColor.fromRgbF(*color)
                tone.setAlphaF(max(0.05, min(1.0, opacity)))
                if len(pressures) == len(strokes) and all(
                    len(pressed) == len(points)
                    for pressed, points in zip(pressures, strokes, strict=True)
                ):
                    for points, pressed in zip(strokes, pressures, strict=True):
                        shown = [self._on_screen(page, point, target, zoom) for point in points]
                        self._paint_pressed(painter, shown, pressed, width * zoom, tone)
                    continue
                pen = QPen(tone, max(1.0, width * zoom))
                round_ends = kind in (
                    INK,
                    ARROW,
                    drawing.DOUBLE_ARROW,
                    drawing.ELBOW,
                    drawing.BRACE,
                )
                pen.setCapStyle(Qt.PenCapStyle.RoundCap if round_ends else Qt.PenCapStyle.FlatCap)
                pen.setJoinStyle(
                    Qt.PenJoinStyle.RoundJoin if round_ends else Qt.PenJoinStyle.MiterJoin
                )
                filled, dashed = look
                if dashed:
                    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                    pen.setDashPattern([3.0, 2.0])  # as the PDF has it, in thicknesses
                painter.setPen(pen)
                for points in strokes:
                    if len(points) < 2:
                        continue
                    self._paint_shape(
                        painter, page, kind, points, target, zoom, width, tone, opacity, filled
                    )
        finally:
            # Whatever happens above, the painter is left as it was found.
            painter.restore()
        self._paint_frame(painter, page, target, zoom)

    def _paint_shape(
        self, painter, page, kind, points, target, zoom, width, tone, opacity, filled
    ) -> None:
        """A shape (or a stroke) on the screen, as the PDF will have it."""
        if kind == INK or kind not in drawing.SHAPES:
            shown = [self._on_screen(page, point, target, zoom) for point in points]
            painter.drawPolyline(QPolygonF(shown))
            return
        start, end = points[0], points[-1]
        corners = drawing.shape_points(kind, start, end)
        shown = [self._on_screen(page, point, target, zoom) for point in corners]
        if filled and kind in drawing.FILLABLE:
            fill = QColor.fromRgbF(*drawing.fill_tone(tone.getRgbF()[:3]))
            fill.setAlphaF(max(0.05, min(1.0, opacity)))
            painter.save()
            # Like a highlighter: what is underneath still shows.
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            self._draw_outline(painter, kind, shown)
            painter.restore()
        self._draw_outline(painter, kind, shown)
        head = width * zoom
        if kind in (ARROW, drawing.DOUBLE_ARROW, drawing.ELBOW):
            painter.drawPolyline(QPolygonF(_arrow_head(shown[-2], shown[-1], head)))
        if kind == drawing.DOUBLE_ARROW:
            painter.drawPolyline(QPolygonF(_arrow_head(shown[1], shown[0], head)))

    @staticmethod
    def _draw_outline(painter: QPainter, kind: str, shown: list[QPointF]) -> None:
        if kind == BOX:
            painter.drawRect(QRectF(shown[0], shown[2]).normalized())
        elif kind == OVAL:
            painter.drawEllipse(QRectF(shown[0], shown[2]).normalized())
        elif kind in (drawing.TRIANGLE, drawing.RHOMBUS):
            painter.drawPolygon(QPolygonF(shown))
        else:
            painter.drawPolyline(QPolygonF(shown))

    @staticmethod
    def _paint_pressed(painter: QPainter, shown, pressures, width: float, tone: QColor) -> None:
        """A stroke that is thicker where the pen pressed more, as it will be saved."""
        if len(shown) < 2:
            return
        spots = [(point.x(), point.y()) for point in shown]
        pieces, discs = drawing.pressed_shape(spots, drawing.half_widths(pressures, width))
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        for piece in pieces:
            path.addPolygon(QPolygonF([QPointF(x, y) for x, y in piece]))
            path.closeSubpath()
        for x, y, radius in discs:
            path.addEllipse(QPointF(x, y), radius, radius)
        painter.fillPath(path, tone)

    def _on_screen(self, page: int, point, target: QRect, zoom: float) -> QPointF:
        x, y = self._shown_point(page, point)
        return QPointF(target.left() + x * zoom, target.top() + y * zoom)

    def _paint_frame(self, painter: QPainter, page: int, target: QRect, zoom: float) -> None:
        """A dashed frame around what is picked, with its handles."""
        if self._picked is None or self._picked[0] != page:
            return
        order = self._picked_order()
        if order is None:
            return
        width = self._sizes[page].width
        x0, y0, x1, y1 = arrange.bounds(order, width)
        frame = QRectF(
            self._on_screen(page, (x0, y0), target, zoom),
            self._on_screen(page, (x1, y1), target, zoom),
        ).normalized()
        scale = self._scale()
        accent = QColor(theme.colours().accent)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        margin = 3 * scale
        for color, style in (
            (QColor("white"), Qt.PenStyle.SolidLine),
            (accent, Qt.PenStyle.DashLine),
        ):
            painter.setPen(QPen(color, max(1.0, scale), style))
            painter.drawRect(frame.adjusted(-margin, -margin, margin, margin))
        half = HANDLE_SIZE * scale / 2
        painter.setPen(QPen(accent, max(1.0, 1.5 * scale)))
        painter.setBrush(QColor("white"))
        for grip in arrange.handles(order, width):
            centre = self._on_screen(page, grip, target, zoom)
            painter.drawRect(QRectF(centre.x() - half, centre.y() - half, 2 * half, 2 * half))
        painter.restore()

    def _sketch_style(self, tool: str):
        """Kind, colour, thickness and opacity of what a tool draws now."""
        if tool == DRAW:
            return INK, self.draw_color, self.draw_width, self.draw_opacity
        return self.shape_kind, self.shape_color, self.shape_width, self.shape_opacity

    def _shown_point(self, page: int, point: tuple[float, float]) -> tuple[float, float]:
        """Where a point of the page is on the turned page (in points)."""
        x, y = point
        size = self._sizes[page]
        if self._rotation == 90:
            return (size.height - y, x)
        if self._rotation == 180:
            return (size.width - x, size.height - y)
        if self._rotation == 270:
            return (y, size.width - x)
        return (x, y)

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

    # ---- notes and text boxes ----------------------------------------------

    def _want_notes(self, page: int, again: bool = False) -> None:
        if not 0 <= page < self.page_count:
            return
        if again or (page not in self._notes and page not in self._asked_notes):
            self._asked_notes.add(page)
            self.service.want_notes(page)

    def _store_notes(self, page: int, found: object) -> None:
        if self._document is None:
            return
        self._asked_notes.discard(page)
        if self._pick_when_read is not None and self._pick_when_read[0] == page:
            name, self._pick_when_read = self._pick_when_read[1], None
            self._notes[page] = list(found)
            item = self._item(page, name)
            if item is not None:
                self.pick(item)
        QTimer.singleShot(0, self._place_picked_bar)  # what is picked may have changed
        self._notes[page] = list(found)
        self.notes_changed.emit(page)
        if not self._changing:
            self._latest.clear()  # what was read is how things are now
        if self._picked is not None and self._picked[0] == page:
            self.picked_changed.emit()  # it may have come, gone or changed
            self.viewport().update()

    def notes_of(self, page: int) -> list[PageNote]:
        """The notes and text boxes known of a page (asked for if not yet)."""
        self._want_notes(page)
        return list(self._notes.get(page, ()))

    def note_under(self, position: QPoint) -> PageNote | None:
        """The note or text box under a place of the window."""
        point = self._point_on_page(position, reach=NOTE_REACH)
        if point is None or not self._annotations_shown:
            return None
        page, x, y = point
        found = self._notes.get(page, ())
        return notes.note_at(found, x, y) or next(
            (
                note
                for note in reversed(found)
                if note.kind == NOTE
                and note.rect[0] - NOTE_REACH <= x <= note.rect[2] + NOTE_REACH
                and note.rect[1] - NOTE_REACH <= y <= note.rect[3] + NOTE_REACH
            ),
            None,
        )

    def _point_on_page(
        self, position: QPoint, reach: float = 0.0
    ) -> tuple[int, float, float] | None:
        """Like ``_page_point``, but only when the place is on a page."""
        point = self._page_point(position)
        if point is None:
            return None
        page, x, y = point
        size = self._sizes[page]
        if -reach <= x <= size.width + reach and -reach <= y <= size.height + reach:
            return point
        return None

    def _do(self, order) -> bool:
        if self._document is None:
            return False
        self.set_annotations_shown(True)  # what is put now must be seen
        number = self.service.apply(order)
        self._changing[number] = "do"
        # A drawing put or moved is painted on top until its page is drawn again.
        new = getattr(order, "new", None)
        if new is not None:
            # A mark on the text is known by the name of each of its pieces.
            names = [mark.name for mark in new.marks] if hasattr(new, "marks") else [new.name]
            for name in names:
                self._latest[name] = new
        sketch = _sketch_of(new or order)
        if sketch is not None:
            self._sent_sketches[number] = sketch
            self.viewport().update()
        return True

    def put_note(self, page: int, x: float, y: float, text: str) -> bool:
        """Stick a note on a page, its icon centred on that point."""
        if not text.strip() or not 0 <= page < self.page_count:
            return False
        size, half = self._sizes[page], notes.NOTE_SIZE / 2
        x = max(0.0, min(size.width - notes.NOTE_SIZE, x - half))
        y = max(0.0, min(size.height - notes.NOTE_SIZE, y - half))
        return self._do(notes.new_note(page, (x, y), text.strip(), self.note_color))

    def want_reading(self, page: int) -> None:
        """Ask for the picture of a page to read its text: ``reading_ready``."""
        if self._document is not None and 0 <= page < self.page_count:
            self.service.want_reading(page)

    def add_text_layer(self, recognised: list, replace: bool = False) -> bool:
        """Write the text read on some pages (``app.core.ocr.OcrPage``) as
        invisible text. One change: Deshacer takes all of it away.

        With ``replace`` the invisible text the pages had is taken away first
        (recognising them again); Deshacer brings it back.
        """
        layers = tuple(
            PageLayer.of(page) for page in recognised if 0 <= page.page < self.page_count
        )
        if not layers:
            return False
        return self._do(AddTextLayer(layers, replace))

    def insert_sheet(self, kind: str = sheets.DEFAULT_SHEET, after: int | None = None) -> bool:
        """Put a sheet to write on after a page (the one being read, if not
        said), the size of that page. Deshacer takes it away again."""
        if self._document is None or not self._sizes:
            return False
        page = self.current_page if after is None else after
        page = max(0, min(page, self.page_count - 1))
        size = self._sizes[page]
        return self._do(sheets.new_sheet(page + 1, kind, (size.width, size.height)))

    def put_text_box(
        self, page: int, x: float, y: float, text: str, width: float = 0.0, **look
    ) -> bool:
        """Write text on a page, starting at that point.

        It is written with the letter, size, colour and weight in use, unless
        ``look`` says otherwise (font, size, color, bold). With ``width`` its
        lines are cut to fit in that many points.
        """
        if not text.strip() or not 0 <= page < self.page_count:
            return False
        font = look.get("font", self.text_font)
        size = look.get("size", self.text_size)
        x, y = self._text_origin(page, x, y, size)
        order = notes.new_text_box(
            page,
            (x, y),
            text.strip(),
            font,
            size,
            look.get("color", self.text_color),
            width,
            look.get("bold", self.text_bold),
        )
        return self._do(order)

    def _text_origin(self, page: int, x: float, y: float, size: float) -> tuple[float, float]:
        """Where a text can start so that it begins inside its page."""
        sheet = self._sizes[page]
        x = max(0.0, min(sheet.width - notes.MIN_BOX_WIDTH, x))
        y = max(0.0, min(sheet.height - size * notes.LINE_HEIGHT, y))
        return x, y

    def change_note(self, note: PageNote, text: str, **look) -> bool:
        """Change what a note or a text box says. Only the ones made here.

        A text box can also change its look: font, size, color, bold, width.
        """
        if not note.ours or not text.strip():
            return False
        old = self._order_of(note)
        new = replace(old, text=text.strip(), **look)
        if new == old:
            return False
        return self._do(notes.Replace(old, new))

    def remove_note(self, note: PageNote) -> bool:
        """Take a note or a text box away (one of another program too)."""
        return note.removable and self._do(notes.Remove(note.order()))

    def close_note_panel(self, keep: bool = False) -> None:
        """Close the panel where a note is being written, keeping the text or not."""
        panel = self.note_panel
        if panel is not None:
            if keep:
                panel.save()
            else:
                panel.cancel()

    def finish_writing(self, seconds: float = WRITING_WAIT_S) -> None:
        """Keep the text or note being written, before saving, closing or printing.

        Until the cursor leaves it, it is not a change yet: this makes it one
        and waits (a moment) for it to come back from the helper, so that
        ``modified`` already counts it.
        """
        if self.note_panel is None:
            return
        self.close_note_panel(keep=True)
        deadline = time.monotonic() + seconds
        while self._changing and time.monotonic() < deadline:
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 20)
            time.sleep(0.002)

    def _panel_closed(self) -> None:
        self.note_panel = None
        self._editor_place = None
        QTimer.singleShot(0, self._place_picked_bar)
        if self._hiding is not None:
            page, self._hiding = self._hiding[0], None
            self._stale.add(page)  # drawn again with the text in its place
            self._request_pages()
        self.setFocus()

    def _hide_while_editing(self, page: int, name: str) -> None:
        self._hiding = (page, name)
        self._stale.add(page)
        self._request_pages()

    def _editor_origin(self, origin: tuple[float, float]) -> tuple[float, float]:
        """Where the text being written starts now: it may have been moved."""
        if self._editor_place is None:
            return origin
        return self._editor_place[1], self._editor_place[2]

    def _editor_moved(self, dx: float, dy: float) -> None:
        """The text being written was dragged by its handle (points of the page)."""
        if self._editor_place is None:
            return
        page, x, y = self._editor_place
        size = self._sizes[page]
        x = max(0.0, min(size.width - notes.MIN_BOX_WIDTH, x + dx))
        y = max(0.0, min(size.height - 4.0, y + dy))
        self._editor_place = (page, x, y)
        self._place_editor()

    def start_note(
        self, kind: str, page: int, x: float, y: float, near: QPoint
    ) -> NotePanel | TextEditor:
        """Start a new note or text at a point of a page.

        A note is written in a small panel. A text is written on the page
        itself, its first line at the height of the click. (With the pages
        turned, the text is written in the panel too.)
        """
        self.close_note_panel(keep=True)
        if kind == TEXT_BOX and self._rotation == 0:
            # The click is where the middle of the first line goes.
            x, y = self._text_origin(page, x, y - 0.55 * self.text_size, self.text_size)
            editor = TextEditor(
                font=self.text_font,
                size=self.text_size,
                color=self.text_color,
                bold=self.text_bold,
                parent=self.viewport(),
                typed_arrows=self.typed_arrows,
            )
            editor.saved.connect(
                lambda text: self.put_text_box(
                    page,
                    *self._editor_origin((x, y)),
                    text,
                    editor.width_chosen,
                    font=editor.font_name,
                    size=editor.size,
                    color=editor.color,
                    bold=editor.bold,
                )
            )
            return self._show_editor(editor, page, x, y)
        panel = NotePanel(kind, parent=self)
        if kind == NOTE:
            panel.saved.connect(lambda text: self.put_note(page, x, y, text))
        else:
            panel.show_text_style(self.text_font, self.text_size, self.text_color)
            panel.saved.connect(lambda text: self.put_text_box(page, x, y, text))
        return self._show_panel(panel, near)

    def open_note(self, note: PageNote, near: QPoint | None = None) -> NotePanel | TextEditor:
        """Open a note or a text box that is on the page: read, change or remove it."""
        self.close_note_panel(keep=True)
        if note.kind == TEXT_BOX and note.ours and self._rotation == 0:
            now = self._order_of(note)  # it may have just been moved or changed
            editor = TextEditor(
                now.text,
                existing=True,
                font=now.font,
                size=now.size,
                color=now.color,
                bold=now.bold,
                width=now.width,
                parent=self.viewport(),
                typed_arrows=self.typed_arrows,
            )
            editor.saved.connect(
                lambda text: self.change_note(
                    note,
                    text,
                    font=editor.font_name,
                    size=editor.size,
                    color=editor.color,
                    bold=editor.bold,
                    width=editor.width_chosen,
                    origin=self._editor_origin(now.origin),
                )
            )
            editor.removed.connect(lambda: self.remove_note(note))
            self.pick(None)
            shown = self._show_editor(editor, now.page, *now.origin)
            self._hide_while_editing(now.page, now.name)
            return shown
        panel = NotePanel(
            note.kind,
            note.text,
            existing=True,
            editable=note.ours,
            parent=self,
            removable=note.removable,
        )
        if note.kind == TEXT_BOX:
            panel.show_text_style(note.font, note.size, note.color)
        panel.saved.connect(lambda text: self.change_note(note, text))
        panel.removed.connect(lambda: self.remove_note(note))
        return self._show_panel(panel, near if near is not None else QPoint(40, 40))

    def _show_panel(self, panel: NotePanel, near: QPoint) -> NotePanel:
        self.note_panel = panel
        panel.closed.connect(self._panel_closed)
        panel.place_near(self.viewport().mapTo(self, near))
        panel.start()
        return panel

    def _show_editor(self, editor: TextEditor, page: int, x: float, y: float) -> TextEditor:
        self.note_panel = editor
        self._editor_place = (page, x, y)
        editor.closed.connect(self._panel_closed)
        editor.style_chosen.connect(self.text_style_chosen)
        editor.moved.connect(self._editor_moved)
        self._place_editor()
        editor.start()
        return editor

    def _place_editor(self) -> None:
        """Keep the text being written on its place of the page (scroll, zoom)."""
        editor = self.note_panel
        if not isinstance(editor, TextEditor) or self._editor_place is None:
            return
        page, x, y = self._editor_place
        zoom = self._render_zoom()
        origin = QPoint(
            self._to_units(self._page_left(page) + x * zoom),
            self._to_units(self._tops[page] - self._scroll_y() + y * zoom),
        )
        editor.put(origin, self._zoom, self._sizes[page].width - x)

    def text_style_given(self, **changed) -> None:
        """The look of the text tool was changed: the text being written takes it."""
        if isinstance(self.note_panel, TextEditor):
            self.note_panel.give_style(**changed)

    # ---- drawing and erasing ------------------------------------------------

    def _store_drawings(self, page: int, found: object) -> None:
        if self._document is None:
            return
        self._drawings[page] = list(found)
        self._erased.pop(page, None)

    def drawings_of(self, page: int) -> list[PageDrawing]:
        """What is known to be drawn or marked on a page (asked for if not yet)."""
        self._want_notes(page)
        return list(self._drawings.get(page, ()))

    def _extend_sketch(self, position: QPoint, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        page, tool, points = self._sketch
        _, x, y = self._page_point(position, page)
        if tool == SHAPE_TOOL and modifiers & Qt.KeyboardModifier.ShiftModifier:
            x, y = drawing.straightened(self.shape_kind, points[0], (x, y))
        size = self._sizes[page]
        point = (max(0.0, min(size.width, x)), max(0.0, min(size.height, y)))
        if tool == DRAW:
            if point != points[-1]:
                points.append(point)
                if self._sketch_pressures is not None:
                    # Lifting the pen tells no pressure: the last one stays.
                    now = self._pen_pressure
                    self._sketch_pressures.append(
                        self._sketch_pressures[-1] if now is None else now
                    )
        else:
            del points[1:]
            points.append(point)
        self.viewport().update()

    def _finish_sketch(self) -> None:
        page, tool, points = self._sketch
        self._sketch = None
        pressures, self._sketch_pressures = self._sketch_pressures, None
        if self._is_tap(page, points):
            # A tap, not a stroke: on something already drawn or written, it
            # picks it (to move it, change it or take it away with Supr).
            item = self.item_under(self._sketch_from, marks=False)
            if item is not None:
                self.pick(item)
                self.viewport().update()
                return
        if tool == DRAW:
            self.draw_ink(page, [points], [pressures] if pressures else ())
        elif len(points) == 2:
            self.draw_shape(self.shape_kind, page, points[0], points[1])
        self.viewport().update()

    def _is_tap(self, page: int, points) -> bool:
        """Whether a stroke never went farther than a click goes."""
        first_x, first_y = points[0]
        reach = DRAG_START / self._zoom
        return all(math.hypot(x - first_x, y - first_y) <= reach for x, y in points)

    def draw_ink(self, page: int, strokes, pressures=()) -> bool:
        """Draw by hand on a page: each stroke, the points it goes through.

        ``pressures``, from a pen that feels it, has for each stroke how hard
        the pen pressed at each point (0 to 1): the stroke is thicker there.
        """
        strokes, pressures = list(strokes), list(pressures)
        with_pressure = (
            len(pressures) == len(strokes)
            and all(len(a) == len(b) for a, b in zip(strokes, pressures, strict=True))
            and all(drawing.felt(pressed) for pressed in pressures)
        )
        if with_pressure:
            both = [drawing.thinned_stroke(*pair) for pair in zip(strokes, pressures, strict=True)]
            both = [(stroke, pressed) for stroke, pressed in both if len(stroke) >= 2]
            strokes, pressures = [a for a, _ in both], [b for _, b in both]
        else:
            strokes = [drawing.thinned(stroke) for stroke in strokes]
            strokes, pressures = [stroke for stroke in strokes if len(stroke) >= 2], []
        if not strokes or not 0 <= page < self.page_count:
            return False
        return self._do(
            drawing.new_ink(
                page, strokes, self.draw_color, self.draw_width, self.draw_opacity, pressures
            )
        )

    def draw_shape(self, kind: str, page: int, start, end) -> bool:
        """Put a line, an arrow, a box or an oval. False if it is too small."""
        if not 0 <= page < self.page_count:
            return False
        order = drawing.new_shape(
            kind,
            page,
            start,
            end,
            self.shape_color,
            self.shape_width,
            self.shape_opacity,
            self.shape_fill,
            self.shape_dashed,
        )
        if order is None or not self._do(order):
            return False
        if self._markup_tool == SHAPE_TOOL:
            # It stays picked: its handles adjust it at once, Supr takes it away.
            self._picked = (page, order.name)
            self.picked_changed.emit()
        return True

    def erase_at(self, position: QPoint) -> bool:
        """Take away what is under a place of the window: a drawing, a shape,
        a mark on the text, a note or a text box, made here or by another
        program (Deshacer puts it back as it was)."""
        point = self._point_on_page(position)
        if point is None or self._document is None or not self._annotations_shown:
            return False  # what is not seen is not erased
        page, x, y = point
        gone = self._erased.setdefault(page, set())
        note = self.note_under(position)
        if note is not None and note.removable and note.name not in gone:
            gone.add(note.name)
            return self._do(notes.Remove(note.order()))
        reach = ERASER_REACH / self._zoom
        for item in reversed(self._drawings.get(page, ())):
            if item.removable and item.name not in gone and item.touches(x, y, reach):
                gone.add(item.name)
                return self._do(notes.Remove(item.order()))
        return False

    # ---- picking, moving, resizing and copying -------------------------------

    def _item(self, page: int, name: str):
        for item in (*self._notes.get(page, ()), *self._drawings.get(page, ())):
            if item.name == name:
                return item
        return None

    def picked_item(self):
        """The annotation that is picked (a ``PageNote`` or a ``PageDrawing``), or None."""
        return self._item(*self._picked) if self._picked is not None else None

    def _picked_order(self):
        """The order of what is picked, where the pointer is taking it."""
        if self._grab is not None and self._grab["change"] is not None:
            return self._grab["change"].new
        item = self.picked_item()
        return self._order_of(item) if item is not None else None

    def _order_of(self, item):
        """The order that puts an annotation where it is now (it may have just
        been moved, and its page not read again yet)."""
        return self._latest.get(item.name) or item.order()

    def pick(self, item) -> None:
        """Pick an annotation (or none), to move, copy or remove it. One made
        by another program can only be removed."""
        chosen = (item.page, item.name) if item is not None and item.removable else None
        if chosen != self._picked:
            self._picked = chosen
            self.picked_changed.emit()
            self.viewport().update()

    def item_under(self, position: QPoint, marks: bool = True):
        """The annotation that is under a place of the window (made here, or
        by another program).

        With ``marks`` false, the marks on the text do not count (a press on
        them starts selecting text).
        """
        note = self.note_under(position)
        if note is not None and note.removable:
            return note
        point = self._point_on_page(position, reach=NOTE_REACH)
        if point is None or not self._annotations_shown:
            return None
        page, x, y = point
        reach = PICK_REACH / self._zoom
        for item in reversed(self._drawings.get(page, ())):
            if not item.removable or (item.kind in MARKUP_KINDS and not marks):
                continue
            if item.touches(x, y, reach):
                return item
        return None

    def _handle_under(self, position: QPoint) -> int | None:
        """The handle of what is picked that is under a place of the window."""
        item = self.picked_item()
        if item is None:
            return None
        _, x, y = self._page_point(position, item.page)
        reach = HANDLE_REACH / self._zoom
        grips = arrange.handles(self._order_of(item), self._sizes[item.page].width)
        near = [
            (math.hypot(x - gx, y - gy), index)
            for index, (gx, gy) in enumerate(grips)
            if abs(x - gx) <= reach and abs(y - gy) <= reach
        ]
        return min(near)[1] if near else None

    def _page_size(self, page: int) -> tuple[float, float]:
        size = self._sizes[page]
        return (size.width, size.height)

    def _start_grab(self, item, handle: int | None, position: QPoint) -> None:
        self.clear_selection()
        self.pick(item)
        _, x, y = self._page_point(position, item.page)
        self._grab = {
            "item": item,
            "order": self._order_of(item),
            "handle": handle,
            "from": (x, y),
            "moved": False,
            "change": None,
        }

    def _drag_grab(self, position: QPoint) -> None:
        grab = self._grab
        item = grab["item"]
        _, x, y = self._page_point(position, item.page)
        from_x, from_y = grab["from"]
        if not grab["moved"]:
            if math.hypot(x - from_x, y - from_y) * self._zoom < DRAG_START:
                return
            grab["moved"] = True
            self.picked_bar.hide()  # back once it is let go
        size = self._page_size(item.page)
        if grab["handle"] is None:
            change = arrange.moved(grab["order"], x - from_x, y - from_y, size)
        else:
            change = arrange.resized(grab["order"], grab["handle"], (x, y), size)
        grab["change"] = change
        self.viewport().update()

    def _end_grab(self, position: QPoint) -> None:
        grab, self._grab = self._grab, None
        if grab["change"] is not None:
            self._do(grab["change"])
        elif not grab["moved"] and (grab["item"].kind == NOTE or grab.get("open")):
            self.open_note(grab["item"], position)  # a plain click on a note opens it
        self._place_picked_bar()
        self.viewport().update()

    def move_picked(self, dx: float, dy: float) -> bool:
        """Move what is picked by so many points. False if it cannot move."""
        item = self.picked_item()
        if item is None:
            return False
        change = arrange.moved(self._order_of(item), dx, dy, self._page_size(item.page))
        return change is not None and self._do(change)

    def resize_picked(self, handle: int, x: float, y: float) -> bool:
        """Take a handle of what is picked to a point of its page."""
        item = self.picked_item()
        if item is None:
            return False
        change = arrange.resized(self._order_of(item), handle, (x, y), self._page_size(item.page))
        return change is not None and self._do(change)

    def recolor_picked(self, color) -> bool:
        """Give what is picked another colour. It stays picked."""
        item = self.picked_item()
        if item is None:
            return False
        change = arrange.recolored(self._order_of(item), color)
        if change is None or not self._do(change):
            return False
        self._place_picked_bar()
        return True

    def _place_picked_bar(self) -> None:
        """Put the bar just over what is picked (under it, when there is no room)."""
        bar = self.picked_bar
        item = self.picked_item()
        order = self._picked_order() if item is not None else None
        busy = self.note_panel is not None or (self._grab is not None and self._grab["moved"])
        if order is None or busy or not self._annotations_shown:
            bar.hide()
            return
        page = item.page
        zoom = self._render_zoom()
        x0, y0, x1, y1 = arrange.bounds(order, self._sizes[page].width)
        corners = [self._shown_point(page, p) for p in ((x0, y0), (x1, y1))]
        left = self._page_left(page) + min(c[0] for c in corners) * zoom
        top = self._tops[page] - self._scroll_y() + min(c[1] for c in corners) * zoom
        bottom = self._tops[page] - self._scroll_y() + max(c[1] for c in corners) * zoom
        bar.show_for(getattr(order, "color", None), arrange.can_recolor(order))
        gap = 8
        x = max(4, min(self._to_units(left), self.viewport().width() - bar.width() - 4))
        y = self._to_units(top) - bar.height() - gap - 4
        if y < 4:
            y = self._to_units(bottom) + gap + 4
        if y > self.viewport().height() - bar.height() - 4 or self._to_units(bottom) < 0:
            bar.hide()  # what is picked is out of sight
            return
        bar.move(x, y)
        bar.show()
        bar.raise_()

    def remove_picked(self) -> bool:
        """Take away what is picked."""
        item = self.picked_item()
        if item is None:
            return False
        self.pick(None)
        return self._do(notes.Remove(self._order_of(item)))

    def copy_picked(self) -> bool:
        """Keep a copy of what is picked, to paste it here or in another document."""
        item = self.picked_item()
        if item is None or not arrange.can_move(item.order()):
            return False
        PdfView.copied = self._order_of(item)
        self.item_copied.emit()
        return True

    def paste(self, at: QPoint | None = None) -> bool:
        """Put the annotation copied last: centred on a place of the window or,
        without one, on the page being read, a little away from the original."""
        if PdfView.copied is None or self._document is None or not self.page_count:
            return False
        point = self._point_on_page(at) if at is not None else None
        if point is not None:
            page, x, y = point
            copy = arrange.copy_of(PdfView.copied, page, self._page_size(page), (x, y))
        else:
            page = max(0, self._current_page)
            copy = arrange.copy_of(PdfView.copied, page, self._page_size(page))
            PdfView.copied = copy  # the next one, a little further still
        return self._put_copy(copy)

    def duplicate_picked(self) -> bool:
        """Put a copy of what is picked next to it."""
        item = self.picked_item()
        if item is None:
            return False
        size = self._page_size(item.page)
        return self._put_copy(arrange.copy_of(self._order_of(item), item.page, size))

    def _put_copy(self, copy) -> bool:
        if copy is None or not self._do(copy):
            return False
        self._picked = (copy.page, copy.name)  # picked as soon as it is on the page
        self.picked_changed.emit()
        return True

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

    def _page_point(
        self, position: QPoint, page: int | None = None
    ) -> tuple[int, float, float] | None:
        """The page under a place of the window and the point of that page, in points.

        Above, below or between pages it gives the nearest page. With ``page``,
        the point is given for that page, wherever the place is.
        """
        if not self._tops:
            return None
        y = self._to_pixels(position.y()) + self._scroll_y()
        if page is None:
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
        self._press(event.position().toPoint(), event.modifiers())

    def _press(self, position: QPoint, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        """The mouse button, the pen or a finger goes down on a place of the window."""
        self.setFocus()
        self._fling.stop()
        self._review_click = False
        if self._review and self.note_panel is None:
            covered = self._cover_under(position)
            if covered is not None:
                self._review_click = True  # uncovered or covered again: nothing else
                self.toggle_cover(covered.name)
                return
        if self.note_panel is not None:
            # A click outside keeps what was written. After a text written on
            # the page, the same click goes on: the next text starts there.
            on_page = isinstance(self.note_panel, TextEditor)
            self.close_note_panel(keep=True)
            if not (on_page and self._markup_tool == TEXT_BOX):
                return
        if self._markup_tool in (DRAW, SHAPE_TOOL) and self._picked is not None:
            # What is picked (the shape just drawn, or one tapped) can be
            # adjusted by its handles or dragged.
            handle = self._handle_under(position)
            item = self.picked_item()
            if item is not None and (handle is not None or self.item_under(position) == item):
                self._start_grab(item, handle, position)
                return
            self.pick(None)
        if self._markup_tool in (DRAW, SHAPE_TOOL):
            point = self._point_on_page(position)
            if point is not None:
                self.clear_selection()
                self._sketch = (point[0], self._markup_tool, [point[1:]])
                self._sketch_from = position
                feels = self._markup_tool == DRAW and self.pen_pressure
                feels = feels and self._pen_pressure is not None
                self._sketch_pressures = [self._pen_pressure] if feels else None
            return
        if self._markup_tool == ERASER:
            self._erasing = True
            self.erase_at(position)
            return
        if not self._markup_tool:
            # With nothing in hand, what is on the page can be picked and dragged.
            handle = self._handle_under(position)
            item = self.picked_item() if handle is not None else None
            item = item or self.item_under(position, marks=False)
            if item is not None:
                self._start_grab(item, handle, position)
                return
            self.pick(None)
        note = self.note_under(position)
        writing = self._markup_tool in (NOTE, TEXT_BOX)
        if writing and note is not None and note.ours and note.kind == TEXT_BOX:
            # Dragged, the text moves; a plain click opens it to write.
            self._start_grab(note, None, position)
            self._grab["open"] = True
            return
        if note is not None and (note.kind == NOTE or writing):
            self.open_note(note, position)
            return
        if writing:
            self.pick(None)
            point = self._point_on_page(position)
            if point is not None:
                self.start_note(self._markup_tool, *point, position)
            return
        if self._markup_tool in MARKUP_KINDS:
            self.pick(None)  # a click on a mark picks it again when the button is let go
        place = self._caret_at(position)
        if place is None:
            self.clear_selection()
            if self._is_picture_page(position):
                self.no_text_to_select.emit()
            return
        if modifiers & Qt.KeyboardModifier.ShiftModifier and self._anchor is not None:
            self.select(self._anchor, place)  # Shift+click: up to here
        else:
            self.clear_selection()
            self._anchor = self._focus = place
        self._selecting = True
        self._drag_position = position

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._move(event.position().toPoint(), event.modifiers())

    def _move(self, position: QPoint, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        """The mouse, the pen or a finger moves, held down or not."""
        if self._sketch is not None:
            self._extend_sketch(position, modifiers)
            return
        if self._erasing:
            self.erase_at(position)
            return
        if self._grab is not None:
            self._drag_grab(position)
            return
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
            self._release(event.position().toPoint(), event.modifiers())
        super().mouseReleaseEvent(event)

    def _release(self, position: QPoint, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        """The mouse button, the pen or a finger is lifted."""
        self._erasing = False
        if self._review_click:
            self._review_click = False
            return
        if self._sketch is not None:
            self._extend_sketch(position, modifiers)
            self._finish_sketch()
        if self._grab is not None:
            self._drag_grab(position)
            self._end_grab(position)
        was_selecting, self._selecting = self._selecting, False
        self._autoscroll.stop()
        if was_selecting and self._markup_tool in MARKUP_KINDS and self.has_selection:
            self.mark_selection(self._markup_tool)  # the marker in hand marks it
        elif (
            was_selecting
            and not self.has_selection
            and (not self._markup_tool or self._markup_tool in MARKUP_KINDS)
        ):
            # A plain click on a mark of the text picks it, with a marker in
            # hand too.
            self.pick(self.item_under(position))

    def _let_go(self) -> None:
        """Drop what the pointer was doing, leaving nothing done."""
        self._sketch = None
        self._sketch_pressures = None
        self._erasing = False
        self._grab = None
        if self._selecting:
            self._selecting = False
            self.clear_selection()
        self._autoscroll.stop()
        self.viewport().update()

    # ---- the pen ------------------------------------------------------------------

    def viewportEvent(self, event) -> bool:  # noqa: N802
        kind = event.type()
        if kind in _TABLET:
            self._pen_event(event)
            event.accept()
            return True
        if kind in _TOUCH and (
            event.pointingDevice().type() == QInputDevice.DeviceType.TouchScreen
        ):
            self._touch_event(event)
            event.accept()
            return True
        return super().viewportEvent(event)

    def _pen_event(self, event) -> None:
        """The pen does what the mouse does, and tells how hard it presses. Its
        other end, or its button held down, erases whatever tool is in hand."""
        kind = event.type()
        position = event.position().toPoint()
        self._pen_at = time.monotonic()
        self._drop_touch()  # what touches the screen now is the hand that holds the pen
        rubber = event.pointerType() == QPointingDevice.PointerType.Eraser or bool(
            event.buttons() & _PEN_BUTTONS or event.button() & _PEN_BUTTONS
        )
        try:
            if kind == QEvent.Type.TabletPress:
                if not self.pen_seen:
                    self.pen_seen = True
                    self.pen_seen_changed.emit()
                self._pen_down = True
                if rubber and self.note_panel is None and self.page_count:
                    self.setFocus()
                    self._erasing = True
                    self.erase_at(position)
                else:
                    self._pen_pressure = event.pressure()
                    if self._second_tap(position):
                        self._double_press(position, event.modifiers())
                    else:
                        self._press(position, event.modifiers())
            elif kind == QEvent.Type.TabletMove:
                if self._pen_down:
                    self._pen_pressure = event.pressure()
                self._move(position)
            else:
                self._pen_down = False
                self._release(position)
        finally:
            self._pen_pressure = None

    # ---- the fingers --------------------------------------------------------------

    def _finger_uses_tool(self) -> bool:
        return bool(self._markup_tool) and pen.finger_uses_tool(self.finger_mode, self.pen_seen)

    def _drop_touch(self) -> None:
        """Stop listening to the fingers on the screen until they are lifted."""
        touch = self._touch
        self._hold.stop()
        if touch is None or touch["mode"] == "ignored":
            return
        if touch["mode"] in ("tool", "mouse"):
            self._let_go()
        touch["mode"] = "ignored"

    def _touch_event(self, event) -> None:
        kind = event.type()
        if kind == QEvent.Type.TouchCancel:
            self._drop_touch()
            self._touch = None
            return
        began = kind == QEvent.Type.TouchBegin
        if began or self._touch is None:
            self._drop_touch()
            self._fling.stop()
            self._touch = {"mode": "wait", "fingers": {}, "moved": False, "trail": []}
            if not began or pen.palm(time.monotonic() - self._pen_at, self._pen_down):
                self._touch["mode"] = "ignored"
        touch = self._touch
        fingers = touch["fingers"]
        lifted = None
        for point in event.points():
            state = point.state()
            if state == point.State.Released:
                fingers.pop(point.id(), None)
                lifted = point.position()
            elif state != point.State.Stationary or point.id() not in fingers:
                fingers[point.id()] = point.position()
        if touch["mode"] != "ignored":
            if kind == QEvent.Type.TouchBegin:
                self._finger_down(touch)
            elif kind == QEvent.Type.TouchEnd:
                self._fingers_up(touch, lifted)
            else:
                self._fingers_moved(touch)
        if kind == QEvent.Type.TouchEnd:
            self._hold.stop()
            self._touch = None

    def _finger_down(self, touch: dict) -> None:
        where = next(iter(touch["fingers"].values()))
        touch["start"] = touch["last"] = where
        if self._finger_uses_tool():
            touch["mode"] = "tool"
            self._press(where.toPoint())
        elif not self._markup_tool:
            self._hold.start()  # resting on a place: like the mouse

    def _finger_held(self) -> None:
        touch = self._touch
        if touch is None or touch["mode"] != "wait" or len(touch["fingers"]) != 1:
            return
        touch["mode"] = "mouse"
        self._press(touch["last"].toPoint())

    def _fingers_moved(self, touch: dict) -> None:
        fingers = list(touch["fingers"].values())
        if not fingers:
            return
        if len(fingers) >= 2:
            first, second = fingers[0], fingers[1]
            centre = (first + second) / 2
            spread = math.hypot(first.x() - second.x(), first.y() - second.y())
            if touch["mode"] != "zoom":
                # A second finger: whatever the first was doing, now they move
                # the page and change its size.
                self._hold.stop()
                if touch["mode"] in ("tool", "mouse"):
                    self._let_go()
                touch["mode"] = "zoom"
            else:
                self._scroll_by(touch["centre"] - centre)
                if touch["spread"] > 1 and spread > 1:
                    self.zoom_around(spread / touch["spread"], centre)
            touch["centre"], touch["spread"], touch["moved"] = centre, spread, True
            return
        where = fingers[0]
        if touch["mode"] == "zoom":
            touch["mode"], touch["last"], touch["trail"] = "pan", where, []
            return
        if touch["mode"] in ("tool", "mouse"):
            if where != touch["last"]:
                touch["moved"] = True
            touch["last"] = where
            self._move(where.toPoint())
            return
        if touch["mode"] == "wait":
            gone = where - touch["start"]
            if math.hypot(gone.x(), gone.y()) < TOUCH_SLOP:
                return
            self._hold.stop()
            touch["mode"], touch["moved"] = "pan", True
        self._scroll_by(touch["last"] - where)
        touch["last"] = where
        now = time.monotonic()
        touch["trail"] = [spot for spot in touch["trail"] if now - spot[0] <= FLING_LOOKS_BACK]
        touch["trail"].append((now, where))

    def _fingers_up(self, touch: dict, where) -> None:
        mode = touch["mode"]
        where = (where or touch.get("last")).toPoint()
        if mode == "tool":
            self._release(where)
        elif mode == "mouse":
            self._release(where)
            if not touch["moved"]:
                # Resting a finger and lifting it is the right button of the mouse.
                self.setFocus()
                QApplication.postEvent(
                    self.viewport(),
                    QContextMenuEvent(
                        QContextMenuEvent.Reason.Other, where, self.viewport().mapToGlobal(where)
                    ),
                )
        elif mode == "wait" and not self._markup_tool:
            if self._second_tap(where):
                self._double_press(where)  # two taps are a double click
            else:
                self._press(where)  # a tap is a click
            self._release(where)
        elif mode == "pan" and len(touch["trail"]) >= 2:
            (then, start), (now, end) = touch["trail"][0], touch["trail"][-1]
            if time.monotonic() - now < FLING_LOOKS_BACK and now > then:
                speed = (start - end) / ((now - then) * 1000)
                if math.hypot(speed.x(), speed.y()) >= FLING_START:
                    self._fling_speed = (speed.x(), speed.y())
                    self._fling.start()

    def _scroll_by(self, way) -> None:
        """Move what is seen by so many screen units."""
        across, down = self.horizontalScrollBar(), self.verticalScrollBar()
        across.setValue(across.value() + round(way.x()))
        down.setValue(down.value() + round(way.y()))

    def _fling_step(self) -> None:
        x, y = self._fling_speed
        across, down = self.horizontalScrollBar(), self.verticalScrollBar()
        before = (across.value(), down.value())
        self._scroll_by(QPointF(x * FLING_MS, y * FLING_MS))
        self._fling_speed = (x * FLING_KEEPS, y * FLING_KEEPS)
        slow = math.hypot(x, y) * FLING_MS < 1
        if slow or before == (across.value(), down.value()):
            self._fling.stop()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._double_press(event.position().toPoint(), event.modifiers())
        elif self._markup_tool in (DRAW, SHAPE_TOOL, ERASER):
            self.mousePressEvent(event)

    def _second_tap(self, position: QPoint) -> bool:
        """Whether the pen or a finger goes down a second time on the same
        place, quickly: what a double click is for the mouse."""
        now = time.monotonic()
        then, where = self._last_tap
        gone = position - where
        again = (
            now - then <= QApplication.doubleClickInterval() / 1000
            and math.hypot(gone.x(), gone.y()) <= DOUBLE_TAP_REACH
        )
        self._last_tap = (float("-inf"), position) if again else (now, position)
        return again

    def _double_press(self, position: QPoint, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        """A double click, or the pen or a finger twice on the same place."""
        if self._markup_tool in (DRAW, SHAPE_TOOL, ERASER):
            self._press(position, modifiers)  # a quick second stroke, not a double click
            return
        note = self.note_under(position)
        if note is not None and note.ours:
            self._grab = None
            self.open_note(note, position)  # a double click on a text opens it
            return
        place = self._caret_at(position)
        if place is None:
            return
        page, caret = place
        start, stop = word_at(self._texts[page], caret)
        self.select((page, start), (page, stop))
        if self._markup_tool in MARKUP_KINDS:
            self.mark_selection(self._markup_tool)  # a double click marks the word

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
        """A hand over a note, a cross to put one, an I-beam over text, an arrow elsewhere."""
        if self._markup_tool in (DRAW, SHAPE_TOOL, ERASER):
            handle = self._handle_under(position) if self._markup_tool == SHAPE_TOOL else None
            if handle is not None:
                self.viewport().setCursor(self._handle_cursor(handle))
            elif self._point_on_page(position) is None:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            elif self._markup_tool == ERASER:
                self.viewport().setCursor(_eraser_cursor())
            else:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            return
        if not self._markup_tool:
            handle = self._handle_under(position)
            item = self.item_under(position, marks=False) if handle is None else None
            if handle is not None:
                self.viewport().setCursor(self._handle_cursor(handle))
                return
            if item is not None and item.kind != NOTE:
                self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
                return
        note = self.note_under(position)
        writing = self._markup_tool in (NOTE, TEXT_BOX)
        if note is not None and (note.kind == NOTE or writing):
            shape = Qt.CursorShape.PointingHandCursor
            tip = note.text[:TIP_LETTERS] + ("…" if len(note.text) > TIP_LETTERS else "")
            if note.kind == NOTE and tip:
                QToolTip.showText(self.viewport().mapToGlobal(position), tip, self.viewport())
        elif writing and self._point_on_page(position) is not None:
            shape = Qt.CursorShape.CrossCursor
        else:
            over_text = False
            point = self._page_point(position)
            if point is not None:
                text = self._texts.get(point[0])
                over_text = text is not None and is_on_text(text, point[1], point[2])
            shape = Qt.CursorShape.IBeamCursor if over_text else Qt.CursorShape.ArrowCursor
        if self.viewport().cursor().shape() != shape:
            self.viewport().setCursor(shape)

    def _handle_cursor(self, handle: int) -> Qt.CursorShape:
        item = self.picked_item()
        if handle in (arrange.RIGHT_SIDE, arrange.LEFT_SIDE):
            sideways = self._rotation in (90, 270)
            return Qt.CursorShape.SizeVerCursor if sideways else Qt.CursorShape.SizeHorCursor
        if len(arrange.handles(self._order_of(item), self._sizes[item.page].width)) == 2:
            return Qt.CursorShape.CrossCursor  # an end of a line goes anywhere
        falling = handle in (arrange.TOP_LEFT, arrange.BOTTOM_RIGHT)
        if self._rotation in (90, 270):
            falling = not falling
        return Qt.CursorShape.SizeFDiagCursor if falling else Qt.CursorShape.SizeBDiagCursor

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self.page_count:
            return
        menu = self.context_menu(event.pos())
        menu.exec(event.globalPos())
        menu.deleteLater()

    def context_menu(self, where: QPoint) -> QMenu:
        """What the right button offers at a place of the window."""
        menu = QMenu(self)
        note = self.note_under(where)
        if note is not None:
            is_note = note.kind == NOTE
            if note.ours:
                name = self.tr("Editar la nota…") if is_note else self.tr("Editar el texto…")
            else:
                name = self.tr("Leer la nota…") if is_note else self.tr("Leer el texto…")
            menu.addAction(name).triggered.connect(
                lambda _checked=False: self.open_note(note, where)
            )
            remove = menu.addAction(
                self.tr("Borrar la nota") if is_note else self.tr("Borrar el texto")
            )
            remove.setEnabled(note.removable)
            remove.triggered.connect(lambda _checked=False: self.remove_note(note))
        item = self.item_under(where)
        if item is not None:
            self.pick(item)
            if arrange.can_move(item.order()):
                menu.addAction(self.tr("Copiar la anotación")).triggered.connect(
                    lambda _checked=False: self.copy_picked()
                )
                menu.addAction(self.tr("Duplicar")).triggered.connect(
                    lambda _checked=False: self.duplicate_picked()
                )
            if note is None:
                name = (
                    self.tr("Borrar la marca")
                    if item.kind in MARKUP_KINDS
                    else self.tr("Borrar el dibujo")
                    if item.kind == INK
                    else self.tr("Borrar la anotación")
                    if item.kind == OTHER
                    else self.tr("Borrar la forma")
                )
                menu.addAction(name).triggered.connect(lambda _checked=False: self.remove_picked())
        if PdfView.copied is not None and self._point_on_page(where) is not None:
            menu.addAction(self.tr("Pegar aquí")).triggered.connect(
                lambda _checked=False: self.paste(where)
            )
        if not menu.isEmpty():
            menu.addSeparator()
        copy = menu.addAction(self.tr("Copiar"))
        copy.setEnabled(self.has_selection)
        copy.triggered.connect(self.copy_selection)
        menu.addAction(self.tr("Seleccionar todo")).triggered.connect(self.select_all)
        menu.addSeparator()
        for kind, name in (
            (HIGHLIGHT, self.tr("Resaltar")),
            (UNDERLINE, self.tr("Subrayar")),
            (STRIKEOUT, self.tr("Tachar")),
        ):
            mark = menu.addAction(name)
            mark.setEnabled(self.has_selection)
            mark.triggered.connect(lambda _checked=False, k=kind: self.mark_selection(k))
        menu.addSeparator()
        undo = menu.addAction(self.tr("Deshacer"))
        undo.setEnabled(self.can_undo)
        undo.triggered.connect(self.undo)
        return menu

    def wheelEvent(self, event) -> None:  # noqa: N802
        self._fling.stop()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # A mouse wheel sends whole notches (120); a touchpad pinch and fine
            # wheels send many small movements. The zoom follows the amount moved,
            # so a notch is one step whether it arrives whole or in pieces.
            moved = event.angleDelta().y()
            if moved:
                self.zoom_around(ZOOM_STEP ** (moved / WHEEL_NOTCH), event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        bar = self.verticalScrollBar()
        key = event.key()
        if self.picked_item() is not None and self._picked_key(event):
            return
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
        elif key == Qt.Key.Key_Escape and self._sketch is not None:
            self._sketch = None  # what was being drawn is dropped
            self._sketch_pressures = None
            self.viewport().update()
        elif key == Qt.Key.Key_Escape and self.has_selection:
            self.clear_selection()
        elif key == Qt.Key.Key_Escape and self._markup_tool:
            self.set_markup_tool("")  # put the marker down
        elif key == Qt.Key.Key_Escape and self._review:
            self.set_review(False)
        else:
            super().keyPressEvent(event)

    def _picked_key(self, event) -> bool:
        """What the keys do while an annotation is picked. False: not one of them."""
        key = event.key()
        step = BIG_NUDGE if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else NUDGE
        # As the page is seen; a turned view turns the arrows with it.
        seen = {
            Qt.Key.Key_Left: (-step, 0.0),
            Qt.Key.Key_Right: (step, 0.0),
            Qt.Key.Key_Up: (0.0, -step),
            Qt.Key.Key_Down: (0.0, step),
        }
        turn = {0: lambda x, y: (x, y), 90: lambda x, y: (y, -x)}
        turn |= {180: lambda x, y: (-x, -y), 270: lambda x, y: (-y, x)}
        moves = {arrow: turn[self._rotation](*way) for arrow, way in seen.items()}
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_picked()
        elif key == Qt.Key.Key_Escape:
            self._grab = None
            self.pick(None)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2) and getattr(
            self.picked_item(), "kind", ""
        ) in (NOTE, TEXT_BOX):
            self.open_note(self.picked_item())  # Intro on a text: write in it
        elif key in moves and arrange.can_move(self.picked_item().order()):
            self.move_picked(*moves[key])
        else:
            return False
        return True

    def scroll_to_page(self, page: int) -> None:
        """Put the top of ``page`` (counting from 0) at the top of the window."""
        if 0 <= page < self.page_count:
            gap = self._to_pixels(PAGE_GAP) // 2
            self.verticalScrollBar().setValue(self._to_units(self._tops[page] - gap))
