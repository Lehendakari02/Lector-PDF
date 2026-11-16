"""Draws PDF pages (and searches them) in a separate process, so the window never freezes.

Why a separate process and not a thread: the PDF engine does not let other
Python code run while it draws a page (it holds Python's global lock). Measured
in task 0.6, a scanned page takes 30 to 150 ms to draw; from a thread, the
window would stall for that long on every page while scrolling. In another
process the window keeps moving and the page appears when it is ready.

A second benefit: if a damaged PDF makes the engine crash, only the helper
process dies. The program stays open and starts a new helper.

How it talks: the window sends the list of pages it wants, most urgent first.
A new list replaces the old one, so pages scrolled past are never drawn.
"""

import contextlib
import multiprocessing
import multiprocessing.connection
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path

from app.core.commands import Color, Command, CommandError, markup_for_selection
from app.core.drawing import PageDrawing, page_drawings
from app.core.notes import PageNote, page_notes
from app.core.ocr import looks_recognised, looks_scanned, page_picture
from app.core.outline import OutlineEntry, read_outline
from app.core.saving import FAILED as SAVE_FAILED
from app.core.saving import SaveError, put_in_place, write_copy
from app.core.search import (
    DEFAULT_OPTIONS,
    PageText,
    SearchHit,
    SearchOptions,
    find_across_pages,
    find_in_page,
    read_page_text,
)
from app.core.selection import selected_text

# Never draw absurdly large images, whatever is asked (protects memory).
MAX_PIXELS_PER_PAGE = 60_000_000
# If the helper dies this many times with the same document, the document is
# the cause: stop restarting it and report the document as unreadable.
MAX_CRASHES_PER_DOCUMENT = 3
GOOD_PAGES_TO_FORGET_CRASHES = 3
TEST_CRASH_PAGES = "LECTOR_PDF_TEST_CRASH_PAGES"
# A search stops after this many results ("a" in a long book has 100 000).
MAX_SEARCH_HITS = 5000
# Pages whose letters are kept ready, so the next search is much faster.
MAX_PAGE_TEXT_BYTES = 96 * 1024 * 1024  # letters of pages kept to search again faster


@dataclass(frozen=True)
class RenderRequest:
    """One page to draw. ``zoom`` is pixels per point (1.0 = 72 dpi)."""

    page: int
    zoom: float
    rotation: int = 0  # extra quarter turns for viewing: 0, 90, 180 or 270
    # False: the page without what was put on it (marks, notes, drawings).
    # A tuple of names: with everything but those (a text being changed).
    annotations: bool | tuple[str, ...] = True


@dataclass(frozen=True)
class RenderedPage:
    """A drawn page: plain RGB pixels, three bytes per pixel, row after row."""

    page: int
    zoom: float
    width: int
    height: int
    stride: int
    samples: bytes
    seconds: float
    rotation: int = 0
    annotations: bool | tuple[str, ...] = True  # as asked in the RenderRequest


def _clean_pixmap(page, matrix):
    """The picture of a page without its annotations.

    What the document itself has stays: its text and pictures and also its
    form fields with what was written in them (and the look of a signature),
    which the PDF keeps next to the annotations.
    """
    import pymupdf
    from pymupdf import mupdf

    inner, still = page.this, mupdf.FzMatrix()
    drawn = mupdf.fz_new_display_list(mupdf.fz_bound_page(inner))
    device = mupdf.fz_new_list_device(drawn)
    mupdf.fz_run_page_contents(inner, device, still, mupdf.FzCookie())
    mupdf.fz_run_page_widgets(inner, device, still, mupdf.FzCookie())
    mupdf.fz_close_device(device)
    return pymupdf.DisplayList(drawn).get_pixmap(matrix=matrix, alpha=False)


@contextlib.contextmanager
def _hidden(doc, page, names: tuple[str, ...]):
    """Some annotations of a page left out of its picture for a moment (the
    text being changed, so that only its editor shows it). Nothing of the
    document changes: each one gets back its own flags."""
    from app.core.commands import find_annotation

    kept = []
    for name in names:
        annotation = find_annotation(page, name)
        if annotation is None:
            continue
        xref = annotation.xref
        flags = doc.xref_get_key(xref, "F")
        number = int(flags[1]) if flags[0] == "int" else 0
        kept.append((xref, flags))
        doc.xref_set_key(xref, "F", str(number | HIDDEN_FLAG))
    try:
        yield
    finally:
        for xref, flags in kept:
            doc.xref_set_key(xref, "F", flags[1] if flags[0] == "int" else "null")


HIDDEN_FLAG = 2  # the "Hidden" flag of an annotation in the PDF standard


def render_page(
    doc,
    page_index: int,
    zoom: float,
    rotation: int = 0,
    annotations: bool | tuple[str, ...] = True,
) -> RenderedPage:
    """Draw one page of an open PyMuPDF document.

    ``rotation`` turns the picture clockwise for viewing; the file is not changed.
    Without ``annotations`` the page is drawn clean: marks, notes and drawings
    are left out (they stay in the document). With a tuple of names, only
    those are left out.
    """
    import pymupdf

    started = time.perf_counter()
    page = doc[page_index]
    pixels = page.rect.width * zoom * page.rect.height * zoom
    if pixels > MAX_PIXELS_PER_PAGE:
        zoom *= (MAX_PIXELS_PER_PAGE / pixels) ** 0.5
    matrix = pymupdf.Matrix(zoom, zoom).prerotate(rotation % 360)
    if isinstance(annotations, tuple):
        with _hidden(doc, page, annotations):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    elif annotations:
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    else:
        pixmap = _clean_pixmap(page, matrix)
    return RenderedPage(
        page=page_index,
        zoom=zoom,
        width=pixmap.width,
        height=pixmap.height,
        stride=pixmap.stride,
        samples=pixmap.samples,
        seconds=time.perf_counter() - started,
        rotation=rotation % 360,
        annotations=annotations,
    )


@dataclass
class _SearchJob:
    search_id: int
    query: str
    options: SearchOptions
    next_page: int = 0
    found: int = 0


def _page_text(doc, number: int, page_texts: dict[int, PageText]) -> PageText:
    """The letters of a page, read once and kept while they fit in memory."""
    text = page_texts.get(number)
    if text is None:
        used = sum(kept.size_in_bytes() for kept in page_texts.values())
        if used > MAX_PAGE_TEXT_BYTES:
            page_texts.clear()
        text = page_texts[number] = read_page_text(doc[number])
    return text


def _text_between(doc, start: tuple[int, int], stop: tuple[int, int], page_texts) -> str:
    """The text from one place of the document to another, each (page, caret)."""
    (first, first_caret), (last, last_caret) = start, stop
    pieces = []
    for number in range(max(first, 0), min(last, doc.page_count - 1) + 1):
        text = _page_text(doc, number, page_texts)
        begin = first_caret if number == first else 0
        end = last_caret if number == last else len(text)
        piece = selected_text(text, begin, end)
        if piece:
            pieces.append(piece)
    return "\n".join(pieces)


def _search_next_page(connection, token, doc, job: _SearchJob, page_texts) -> bool:
    """Search one page and send what was found. False when the search is over."""
    if job.next_page >= doc.page_count or job.found >= MAX_SEARCH_HITS:
        too_many = job.found >= MAX_SEARCH_HITS
        connection.send(("search_done", token, job.search_id, too_many))
        return False
    number = job.next_page
    job.next_page += 1
    try:
        text = _page_text(doc, number, page_texts)
        hits = find_in_page(text, job.query, job.options, number)
        if number + 1 < doc.page_count:
            # A phrase that goes on to the next page.
            following = _page_text(doc, number + 1, page_texts)
            before = _page_text(doc, number - 1, page_texts) if number else None
            hits += find_across_pages(text, following, job.query, job.options, number, before)
    except Exception:
        hits = []  # a page that cannot be read has no results; the search goes on
    if hits:
        hits = hits[: MAX_SEARCH_HITS - job.found]
        job.found += len(hits)
        connection.send(("hits", token, job.search_id, hits))
    return True


class _SaveFailed(Exception):
    """Saving did not work; ``doc`` is the document to go on with."""

    def __init__(self, doc, error: SaveError) -> None:
        super().__init__(str(error))
        self.doc = doc
        self.error = error


def _same_file(first: str, second: str) -> bool:
    try:
        return os.path.samefile(first, second)
    except OSError:  # the target does not exist yet
        return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


def _open_checked(source, password: str | None):
    """Open a PDF from a file name or from its bytes, with its password."""
    import pymupdf

    if isinstance(source, bytes):
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        doc = pymupdf.open(source, filetype="pdf")
    if doc.needs_pass and not (password and doc.authenticate(password)):
        doc.close()
        raise ValueError("password required")
    return doc


def _save_document(doc, path: str, password: str | None, target: str):
    """Save the open ``doc`` (which lives in ``path``) into ``target``.

    Returns the document to go on with, opened from ``target``. Raises
    ``_SaveFailed`` with the document to go on with when it could not be saved:
    in both cases every change is still there.

    The whole document is first written next to ``target`` and checked. To
    save over its own file the document has to let go of it (Windows does not
    replace a file in use). If the file then cannot be replaced, because another
    program holds it for example, the document goes on from the written copy,
    kept in memory, so nothing is lost and the file on disk is the old one.
    """
    try:
        temp = write_copy(doc, target, password)
    except SaveError as error:
        raise _SaveFailed(doc, error) from error
    if not _same_file(path, target):
        # "Save as": the document being read is not touched if this fails.
        try:
            put_in_place(temp, target)
            new = _open_checked(target, password)
        except SaveError as error:
            with contextlib.suppress(OSError):
                temp.unlink()
            raise _SaveFailed(doc, error) from error
        except Exception as error:
            raise _SaveFailed(doc, SaveError(SAVE_FAILED, str(error))) from error
        doc.close()
        return new
    doc.close()
    try:
        put_in_place(temp, target)
    except SaveError as error:
        try:
            kept = _open_checked(temp.read_bytes(), password)
        except Exception:
            # Not even the copy can be read back: go on from the file as it was.
            kept = _open_checked(path, password)
        with contextlib.suppress(OSError):
            temp.unlink()
        raise _SaveFailed(kept, error) from error
    return _open_checked(target, password)


SCAN_CHECK_STEP = 10  # pages looked at between two looks at the messages


def _check_scanned(
    connection, token: int, doc, start: int, scanned: list[int], recognised: list[int]
) -> int | None:
    """Look at a few more pages for scans, and for scans whose text was
    already recognised. Returns where to go on, or None once the whole
    document is seen (and the window has been told)."""
    if doc is None:
        return None
    stop = min(doc.page_count, start + SCAN_CHECK_STEP)
    for number in range(start, stop):
        try:
            page = doc[number]
            if looks_scanned(page):
                scanned.append(number)
            elif looks_recognised(page):
                recognised.append(number)
        except Exception:  # noqa: S112 - a damaged page is not taken for a scan
            continue
    if stop < doc.page_count:
        return stop
    connection.send(("scanned", token, list(scanned), doc.page_count, list(recognised)))
    return None


def _send_reading(connection, token: int, doc, page_index: int) -> None:
    """The grey picture of a page, to read its text (see ``app.core.ocr``)."""
    try:
        picture, dpi = page_picture(doc[page_index])
    except Exception as exc:
        connection.send(("reading_failed", token, page_index, str(exc)))
        return
    connection.send(("reading", token, page_index, picture.width, picture.height, dpi))
    connection.send_bytes(picture.samples)


def _worker_main(connection: Connection) -> None:
    """The helper process: open documents and draw the pages asked for."""
    import pymupdf

    doc = None
    doc_path = doc_password = None  # where the open document lives, to save it
    wanted: list[tuple[int, float, int, bool]] = []
    thumbnails: list[tuple[int, float, int, bool]] = []  # small pictures, drawn when idle
    prints: list[tuple[int, float, int, bool]] = []  # pages for the printer
    token = 0
    search: _SearchJob | None = None
    page_texts: dict[int, PageText] = {}  # letters of pages already read
    # Looking, when there is nothing else to do, for pages that are only a
    # picture (scanned): the next page to look at (None: done) and those found.
    checking: int | None = None
    scanned: list[int] = []
    recognised: list[int] = []
    # Pages whose picture is wanted to read their text (OCR), drawn after the
    # pages being read and the printer, before the small pictures.
    readings: list[int] = []
    # Only for the automatic tests: pages that "kill" the helper when drawn.
    crash_pages = {int(n) for n in os.environ.get(TEST_CRASH_PAGES, "").split(",") if n.strip()}
    while True:
        # Read every waiting message before doing anything, so a newer list of
        # wanted pages (or a newer search) always wins over an older one.
        busy = wanted or prints or readings or thumbnails or search or checking is not None
        if not busy or connection.poll():
            try:
                message = connection.recv()
            except (EOFError, OSError):
                return  # the program has gone
            kind = message[0]
            if kind == "quit":
                return
            if kind == "open":
                _, token, path, password = message
                wanted, prints, thumbnails, search, readings = [], [], [], None, []
                page_texts.clear()
                if doc is not None:
                    doc.close()
                    doc = None
                try:
                    doc = pymupdf.open(path, filetype="pdf")
                    if doc.needs_pass and not (password and doc.authenticate(password)):
                        raise ValueError("password required")
                    if doc.page_count == 0:
                        raise ValueError("the document has no pages")
                    doc_path, doc_password = path, password
                    connection.send(("opened", token, doc.page_count))
                    connection.send(("outline", token, read_outline(doc)))
                    checking, scanned, recognised = 0, [], []
                except Exception as exc:
                    doc = None
                    connection.send(("open_failed", token, str(exc)))
            elif kind == "want":
                _, want_token, items = message
                wanted = list(items) if want_token == token and doc is not None else []
            elif kind == "thumbnails":
                _, want_token, items = message
                thumbnails = list(items) if want_token == token and doc is not None else []
            elif kind == "prints":
                _, want_token, items = message
                prints = list(items) if want_token == token and doc is not None else []
            elif kind == "reading":
                _, reading_token, page_index = message
                if reading_token == token and doc is not None and page_index not in readings:
                    readings.append(page_index)
            elif kind == "search":
                _, search_token, search_id, query, whole_word, exact, approximate = message
                search = None
                if search_token == token and doc is not None:
                    search = _SearchJob(
                        search_id, query, SearchOptions(whole_word, exact, approximate)
                    )
            elif kind == "cancel_search":
                search = None
            elif kind == "text":
                _, text_token, page_index = message
                if text_token == token and doc is not None:
                    try:
                        letters = _page_text(doc, page_index, page_texts).without_caches()
                    except Exception:
                        letters = PageText()  # a page that cannot be read has no text
                    connection.send(("text", token, page_index, letters))
            elif kind == "notes":
                _, notes_token, page_index = message
                if notes_token == token and doc is not None:
                    try:
                        found = page_notes(doc, page_index)
                        drawn = page_drawings(doc, page_index)
                    except Exception:
                        found, drawn = [], []  # a page that cannot be read has none
                    connection.send(("notes", token, page_index, found, drawn))
            elif kind == "copy":
                _, copy_token, copy_id, start, stop = message
                if copy_token == token and doc is not None:
                    try:
                        copied = _text_between(doc, start, stop, page_texts)
                    except Exception:
                        copied = ""
                    connection.send(("copied", token, copy_id, copied))
            elif kind in ("mark", "apply"):
                # A change to the document: a new mark on the text selected, or
                # an order that already exists (to undo it, or to do it again).
                change_token, change_id = message[1], message[2]
                if change_token == token and doc is not None:
                    try:
                        if kind == "mark":
                            _, _, _, mark_kind, start, stop, color, opacity = message
                            order, undo = (
                                markup_for_selection(
                                    mark_kind,
                                    start,
                                    stop,
                                    lambda number, doc=doc: _page_text(doc, number, page_texts),
                                    color,
                                    opacity,
                                ),
                                False,
                            )
                            if order is None:
                                raise CommandError("there is no text there")
                        else:
                            _, _, _, order, undo = message
                        pages = order.undo(doc) if undo else order.apply(doc)
                    except Exception as exc:
                        connection.send(("change_failed", token, change_id, str(exc)))
                    else:
                        connection.send(("changed", token, change_id, order, pages, undo))
                        if getattr(order, "text_change", False):
                            for page_index in pages:  # their letters are different now
                                page_texts.pop(page_index, None)
                            checking, scanned, recognised = 0, [], []  # looked at again
                        if hasattr(order, "page_change"):
                            # Pages were put or taken away: the letters read so
                            # far belong to other places now, and the index
                            # points elsewhere. The window searches again.
                            page_texts.clear()
                            search = None
                            connection.send(("outline", token, read_outline(doc)))
                            checking, scanned, recognised = 0, [], []  # other numbers now
                            readings = []  # the window asks again with the new numbers
            elif kind == "save":
                _, save_token, save_id, target = message
                if save_token == token and doc is not None:
                    try:
                        doc = _save_document(doc, doc_path, doc_password, target)
                    except _SaveFailed as failed:
                        doc = failed.doc  # still open, with every change in it
                        error = failed.error
                        connection.send(("save_failed", token, save_id, error.kind, error.details))
                    else:
                        doc_path = target
                        connection.send(("saved", token, save_id, target))
            elif kind == "close":
                wanted, prints, thumbnails, search, readings = [], [], [], None, []
                checking = None
                page_texts.clear()
                if doc is not None:
                    doc.close()
                    doc = None
            continue

        if readings and not wanted and not prints:
            _send_reading(connection, token, doc, readings.pop(0))
            continue

        if not wanted and not prints and not thumbnails:
            # Nothing to draw: search one more page. Drawing always goes first,
            # so searching a long document never slows the scrolling down.
            if search is not None:
                if not _search_next_page(connection, token, doc, search, page_texts):
                    search = None
            elif checking is not None:
                checking = _check_scanned(connection, token, doc, checking, scanned, recognised)
            continue

        # The pages being read go first, then the printer, then the small
        # pictures of the side panel.
        kind = "page" if wanted else "print" if prints else "thumbnail"
        page_index, zoom, rotation, annotations = (wanted or prints or thumbnails).pop(0)
        # Said first: if drawing this page kills the helper, the program knows which.
        connection.send(("drawing", token, page_index))
        if page_index in crash_pages:
            os._exit(13)
        try:
            result = render_page(doc, page_index, zoom, rotation, annotations)
            connection.send(
                (
                    kind,
                    token,
                    page_index,
                    zoom,
                    result.width,
                    result.height,
                    result.stride,
                    result.seconds,
                    result.rotation,
                    result.annotations,
                )
            )
            connection.send_bytes(result.samples)
        except Exception as exc:
            failed = "print_failed" if kind == "print" else "page_failed"
            connection.send((failed, token, page_index, zoom, str(exc)))


class RenderService:
    """Owns the helper process and delivers drawn pages through callbacks.

    The callbacks are called from a background thread. The interface layer is
    responsible for passing the results to its own thread.
    """

    def __init__(
        self,
        on_page: Callable[[RenderedPage], None],
        on_page_failed: Callable[[int, float, str], None] | None = None,
        on_open_failed: Callable[[str], None] | None = None,
        on_crashed: Callable[[], None] | None = None,
        on_hits: Callable[[int, list[SearchHit]], None] | None = None,
        on_search_done: Callable[[int, bool], None] | None = None,
        on_outline: Callable[[list[OutlineEntry]], None] | None = None,
        on_thumbnail: Callable[[RenderedPage], None] | None = None,
        on_text: Callable[[int, PageText], None] | None = None,
        on_copied: Callable[[int, str], None] | None = None,
        on_print: Callable[[RenderedPage], None] | None = None,
        on_print_failed: Callable[[int], None] | None = None,
        on_print_lost: Callable[[int], None] | None = None,
        on_saved: Callable[[int, Path], None] | None = None,
        on_save_failed: Callable[[int, str, str], None] | None = None,
        on_changed: Callable[[int, Command, list[int], bool], None] | None = None,
        on_change_failed: Callable[[int, str], None] | None = None,
        on_notes: Callable[[int, list[PageNote]], None] | None = None,
        on_drawings: Callable[[int, list[PageDrawing]], None] | None = None,
        on_scanned: Callable[[list[int], int, list[int]], None] | None = None,
        on_reading: Callable[[int, int, int, int, bytes], None] | None = None,
        on_reading_failed: Callable[[int, str], None] | None = None,
    ) -> None:
        self._on_reading = on_reading or (lambda page, width, height, dpi, samples: None)
        self._on_reading_failed = on_reading_failed or (lambda page, details: None)
        self._readings: set[int] = set()  # pictures asked for to read, not yet back
        self._on_scanned = on_scanned or (lambda pages, count, recognised: None)
        self._on_notes = on_notes or (lambda page, notes: None)
        self._on_drawings = on_drawings or (lambda page, drawings: None)
        self._on_changed = on_changed or (lambda number, order, pages, undo: None)
        self._on_change_failed = on_change_failed or (lambda number, details: None)
        self._change_id = 0
        # Changes that are in the helper's document and not yet in the file, in
        # order, each (order, undone). A new helper is given them again.
        self._unsaved: list[tuple[Command, bool]] = []
        self._on_saved = on_saved or (lambda save_id, path: None)
        self._on_save_failed = on_save_failed or (lambda save_id, kind, details: None)
        self._save_id = 0
        self._saving: set[int] = set()  # saves asked for, not yet answered
        self._on_print = on_print or (lambda page: None)
        self._on_print_failed = on_print_failed or (lambda page: None)
        self._on_print_lost = on_print_lost or (lambda page: None)
        self._printing: set[int] = set()  # pages asked for the printer, not yet back
        self._on_text = on_text or (lambda page, text: None)
        self._on_copied = on_copied or (lambda copy_id, text: None)
        self._copy_id = 0
        self._on_outline = on_outline or (lambda entries: None)
        self._on_thumbnail = on_thumbnail or (lambda page: None)
        self._on_hits = on_hits or (lambda search_id, hits: None)
        self._on_search_done = on_search_done or (lambda search_id, too_many: None)
        self._search_id = 0
        self._searching = False
        self._on_page = on_page
        self._on_page_failed = on_page_failed or (lambda page, zoom, message: None)
        self._on_open_failed = on_open_failed or (lambda message: None)
        self._on_crashed = on_crashed or (lambda: None)
        self._lock = threading.RLock()
        self._process = None
        self._connection: Connection | None = None
        self._reader: threading.Thread | None = None
        self._token = 0
        self._path: Path | None = None
        self._password: str | None = None
        self._closing = False
        self._crashes = 0  # with the current document
        self._drawing: int | None = None  # the page the helper is drawing now
        self._bad_pages: set[int] = set()  # pages that killed the helper
        self._drawn_since_crash = 0
        self.restarts = 0

    # ---- public API -----------------------------------------------------

    def open(self, path: str | Path, password: str | None = None) -> None:
        """Tell the helper which document to draw from now on."""
        with self._lock:
            self._path, self._password = Path(path), password
            self._token += 1
            self._crashes = 0
            self._drawing = None
            self._bad_pages = set()
            self._unsaved = []
            self._readings.clear()
            self._ensure_started()
            self._send(("open", self._token, str(self._path), password))

    def warm_up(self) -> None:
        """Start the helper before any document is opened, so the first one is quicker."""
        with self._lock:
            self._ensure_started()

    def want(self, requests: list[RenderRequest]) -> None:
        """Replace the list of pages to draw, most urgent first."""
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                # A new helper knows nothing yet: give it the document again.
                self._reopen()
            self._send(("want", self._token, self._drawable(requests)))

    def want_thumbnails(self, requests: list[RenderRequest]) -> None:
        """Replace the list of small pictures to draw. They wait for the pages."""
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._reopen()
            self._send(("thumbnails", self._token, self._drawable(requests)))

    def want_prints(self, requests: list[RenderRequest]) -> None:
        """Replace the list of pages to draw for the printer (an empty list cancels).

        Each arrives in ``on_print``, or its number in ``on_print_failed`` if it
        cannot be drawn. They do not disturb the pages being read.
        """
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._reopen()
            bad = [r.page for r in requests if r.page in self._bad_pages]
            self._printing = {r.page for r in requests} - set(bad)
            self._send(("prints", self._token, self._drawable(requests)))
        for page in bad:
            self._tell(self._on_print_failed, page)

    def search(self, query: str, options: SearchOptions = DEFAULT_OPTIONS) -> int:
        """Start looking for ``query`` in the whole document.

        Replaces any search still running. Results arrive page by page through
        ``on_hits`` and the end through ``on_search_done``, both with the
        number this method returns.
        """
        with self._lock:
            self._search_id += 1
            if self._path is None:
                return self._search_id
            if self._ensure_started():
                self._reopen()
            self._searching = True
            self._send(
                (
                    "search",
                    self._token,
                    self._search_id,
                    query,
                    options.whole_word,
                    options.exact,
                    options.approximate,
                )
            )
            return self._search_id

    def want_reading(self, page: int) -> None:
        """Ask for the grey picture of a page, to read its text (OCR).

        It arrives in ``on_reading(page, width, height, dpi, samples)``, or
        ``on_reading_failed(page, details)``; also if the helper ends first.
        """
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._reopen()
            self._readings.add(page)
            self._send(("reading", self._token, page))

    def want_text(self, page: int) -> None:
        """Ask for the letters of a page and where they are. Arrives in ``on_text``."""
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._reopen()
            self._send(("text", self._token, page))

    def want_notes(self, page: int) -> None:
        """Ask for the notes and text boxes of a page (counting from 0).

        They arrive through ``on_notes(page, notes)``, each an
        ``app.core.notes.PageNote``, as the document is at that moment. Just
        before, ``on_drawings(page, drawings)`` gives what is drawn or marked
        on it (``app.core.drawing.PageDrawing``).
        """
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._reopen()
            self._send(("notes", self._token, page))

    def copy_text(self, start: tuple[int, int], stop: tuple[int, int]) -> int:
        """Ask for the text between two places, each (page, caret).

        It arrives in ``on_copied`` with the number this method returns.
        """
        with self._lock:
            self._copy_id += 1
            if self._path is None:
                return self._copy_id
            if self._ensure_started():
                self._reopen()
            self._send(("copy", self._token, self._copy_id, start, stop))
            return self._copy_id

    def _reopen(self) -> None:
        """Give a new helper the document again, with the changes not yet saved."""
        self._send(("open", self._token, str(self._path), self._password))
        for order, undo in self._unsaved:
            self._send(("apply", self._token, 0, order, undo))

    def mark_text(
        self,
        kind: str,
        start: tuple[int, int],
        stop: tuple[int, int],
        color: Color | None = None,
        opacity: float = 1.0,
    ) -> int:
        """Highlight, underline or strike out the text between two places.

        ``kind`` is one of ``app.core.commands.MARKUP_KINDS``; each place is
        (page, caret). Returns a number; the answer comes with it through
        ``on_changed`` (with the order that was carried out, which can undo
        it) or ``on_change_failed``. The file is not touched until it is saved.
        """
        return self._change(
            lambda number: ("mark", self._token, number, kind, start, stop, color, opacity)
        )

    def apply(self, order: Command, undo: bool = False) -> int:
        """Carry out an order on the open document, or undo it. Answers like ``mark_text``."""
        return self._change(lambda number: ("apply", self._token, number, order, undo))

    def _change(self, message) -> int:
        with self._lock:
            self._change_id += 1
            number = self._change_id
            ready = self._path is not None
            if ready:
                if self._ensure_started():
                    self._reopen()
                self._send(message(number))
        if not ready:
            self._tell(self._on_change_failed, number, "no document is open")
        return number

    def save(self, target: str | Path | None = None) -> int:
        """Save the open document, in its own file or (``target``) in another one.

        Returns a number; the answer comes with it through ``on_saved`` (with the
        file the document lives in from then on) or ``on_save_failed`` (with
        one of the kinds of ``app.core.saving`` and the details). Saving never
        leaves a file half written, and a failure loses nothing.
        """
        with self._lock:
            self._save_id += 1
            number = self._save_id
            if self._path is None:
                failed = True
            else:
                failed = False
                if self._ensure_started():
                    self._reopen()
                self._saving.add(number)
                where = os.path.abspath(target if target is not None else self._path)
                self._send(("save", self._token, number, where))
        if failed:
            self._tell(self._on_save_failed, number, SAVE_FAILED, "no document is open")
        return number

    def cancel_search(self) -> None:
        with self._lock:
            self._search_id += 1
            self._searching = False
            if self.is_running():
                self._send(("cancel_search",))

    def close_document(self) -> None:
        with self._lock:
            self._path = None
            self._search_id += 1
            self._searching = False
            self._token += 1
            self._unsaved = []
            self._readings.clear()
            if self.is_running():
                self._send(("close",))

    def shutdown(self) -> None:
        """Stop the helper process. Safe to call more than once."""
        with self._lock:
            self._closing = True
            process, connection = self._process, self._connection
            self._process = self._connection = None
        if connection is not None:
            with contextlib.suppress(OSError, ValueError):
                connection.send(("quit",))
        if process is not None:
            process.join(timeout=2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        if connection is not None:
            with contextlib.suppress(OSError):
                connection.close()
        reader = self._reader
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=2)

    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process is not None else None

    # ---- internals ------------------------------------------------------

    def _ensure_started(self) -> bool:
        """Start the helper if needed. Returns True if a new one was started."""
        if self.is_running() or self._closing or self._crashes >= MAX_CRASHES_PER_DOCUMENT:
            return False
        if self._process is not None:
            # The helper has just died and the thread that reads its results has
            # not dealt with it yet. Starting another one here would hide the
            # crash from that thread: which page was to blame, and the notice
            # that makes the window ask for its pages again.
            return False
        # "spawn" everywhere: it is the only way on Windows, and using it on
        # every system means the tests exercise the same path.
        context = multiprocessing.get_context("spawn")
        parent_end, child_end = context.Pipe()
        process = context.Process(
            target=_worker_main, args=(child_end,), name="lector-pdf-render", daemon=True
        )
        process.start()
        child_end.close()
        self._process, self._connection = process, parent_end
        self._reader = threading.Thread(
            target=self._read_results,
            args=(parent_end, process.sentinel),
            name="render-results",
            daemon=True,
        )
        self._reader.start()
        return True

    def _drawable(self, requests: list[RenderRequest]) -> list[tuple[int, float, int, bool]]:
        """The requests as the helper wants them, without the pages that killed it."""
        return [
            (r.page, r.zoom, r.rotation, r.annotations)
            for r in requests
            if r.page not in self._bad_pages
        ]

    @staticmethod
    def _tell(callback: Callable, *values: object) -> None:
        """Call a callback of the program. Its own errors must not stop the results.

        The error is handed to the program's error log like any unexpected one.
        """
        try:
            callback(*values)
        except Exception:
            sys.excepthook(*sys.exc_info())

    def _send(self, message: tuple) -> None:
        if self._connection is None:
            return
        with contextlib.suppress(OSError, ValueError):
            self._connection.send(message)

    def _read_results(self, connection: Connection, process_ended: int) -> None:
        while True:
            try:
                # Wait for a result or for the helper to die. Watching only the
                # connection is not enough: on Windows, if the helper dies while
                # it is still starting, the connection never reports it.
                ready = multiprocessing.connection.wait([connection, process_ended])
                if connection not in ready and not connection.poll():
                    break
                message = connection.recv()
                kind = message[0]
                has_picture = kind in ("page", "thumbnail", "print", "reading")
                samples = connection.recv_bytes() if has_picture else b""
            except (EOFError, OSError, ValueError, TypeError):
                break
            if message[1] != self._token:
                continue  # belongs to a document that is no longer open
            if kind == "drawing":
                self._drawing = message[2]
            elif kind == "print_failed":
                self._drawing = None
                self._printing.discard(message[2])
                self._tell(self._on_print_failed, message[2])
            elif kind == "print":
                _, _, page, zoom, width, height, stride, seconds, rotation, shown = message
                self._drawing = None
                self._printing.discard(page)
                drawn = RenderedPage(
                    page, zoom, width, height, stride, samples, seconds, rotation, shown
                )
                self._tell(self._on_print, drawn)
            elif kind in ("page", "thumbnail"):
                _, _, page, zoom, width, height, stride, seconds, rotation, shown = message
                self._drawing = None
                self._drawn_since_crash += 1
                if self._drawn_since_crash >= GOOD_PAGES_TO_FORGET_CRASHES:
                    self._crashes = 0  # the document is fine: the crash was a one-off
                drawn = RenderedPage(
                    page, zoom, width, height, stride, samples, seconds, rotation, shown
                )
                self._tell(self._on_page if kind == "page" else self._on_thumbnail, drawn)
            elif kind == "outline":
                self._tell(self._on_outline, message[2])
            elif kind == "reading":
                _, _, page, width, height, dpi = message
                self._readings.discard(page)
                self._tell(self._on_reading, page, width, height, dpi, samples)
            elif kind == "reading_failed":
                self._readings.discard(message[2])
                self._tell(self._on_reading_failed, message[2], message[3])
            elif kind == "scanned":
                self._tell(self._on_scanned, message[2], message[3], message[4])
            elif kind == "text":
                self._tell(self._on_text, message[2], message[3])
            elif kind == "copied":
                self._tell(self._on_copied, message[2], message[3])
            elif kind == "notes":
                self._tell(self._on_drawings, message[2], message[4])
                self._tell(self._on_notes, message[2], message[3])
            elif kind == "page_failed":
                self._drawing = None
                self._tell(self._on_page_failed, message[2], message[3], message[4])
            elif kind == "changed":
                _, _, number, order, pages, undo = message
                if number:  # 0: given again to a new helper, already counted
                    with self._lock:
                        self._unsaved.append((order, undo))
                    self._tell(self._on_changed, number, order, pages, undo)
            elif kind == "change_failed":
                if message[2]:
                    self._tell(self._on_change_failed, message[2], message[3])
            elif kind == "saved":
                with self._lock:
                    self._unsaved = []  # everything done before is in the file now
                    self._saving.discard(message[2])
                    self._path = Path(message[3])  # after "Save as", the new file
                self._tell(self._on_saved, message[2], Path(message[3]))
            elif kind == "save_failed":
                self._saving.discard(message[2])
                self._tell(self._on_save_failed, message[2], message[3], message[4])
            elif kind == "open_failed":
                self._tell(self._on_open_failed, message[2])
            elif kind == "hits" and message[2] == self._search_id:
                self._tell(self._on_hits, message[2], message[3])
            elif kind == "search_done" and message[2] == self._search_id:
                self._searching = False
                self._tell(self._on_search_done, message[2], message[3])
        lost_search = bad_page = None
        lost_prints: set[int] = set()
        lost_saves: set[int] = set()
        lost_readings: set[int] = set()
        with self._lock:
            crashed = not self._closing and connection is self._connection
            if crashed:
                with contextlib.suppress(OSError):
                    connection.close()
                self._process = self._connection = None
                self.restarts += 1
                self._drawn_since_crash = 0
                bad_page, self._drawing = self._drawing, None
                if bad_page is not None:
                    # One page is to blame: it is not drawn again, the rest go on.
                    self._bad_pages.add(bad_page)
                else:
                    self._crashes += 1
                gave_up = self._crashes >= MAX_CRASHES_PER_DOCUMENT
                lost_search = self._search_id if self._searching else None
                self._searching = False
                lost_prints, self._printing = self._printing, set()
                lost_saves, self._saving = self._saving, set()
                lost_readings, self._readings = self._readings, set()
        # The printer is told about every page it was waiting for: it asks again
        # for the good ones and leaves out the one that killed the helper.
        for page in sorted(lost_prints):
            self._tell(self._on_print_failed if page == bad_page else self._on_print_lost, page)
        for page in sorted(lost_readings):
            self._tell(self._on_reading_failed, page, "the helper ended before drawing it")
        for number in sorted(lost_saves):
            self._tell(self._on_save_failed, number, SAVE_FAILED, "the helper ended while saving")
        if crashed and bad_page is not None:
            self._tell(self._on_page_failed, bad_page, 0.0, "the helper ended while drawing it")
        if crashed and lost_search is not None:
            self._tell(self._on_search_done, lost_search, False)  # ends early, with what was found
        if crashed and gave_up:
            self._tell(self._on_open_failed, "the helper process keeps crashing with this document")
        elif crashed:
            self._tell(self._on_crashed)
