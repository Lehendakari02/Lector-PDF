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

from app.core.outline import OutlineEntry, read_outline
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


def render_page(doc, page_index: int, zoom: float, rotation: int = 0) -> RenderedPage:
    """Draw one page of an open PyMuPDF document.

    ``rotation`` turns the picture clockwise for viewing; the file is not changed.
    """
    import pymupdf

    started = time.perf_counter()
    page = doc[page_index]
    pixels = page.rect.width * zoom * page.rect.height * zoom
    if pixels > MAX_PIXELS_PER_PAGE:
        zoom *= (MAX_PIXELS_PER_PAGE / pixels) ** 0.5
    matrix = pymupdf.Matrix(zoom, zoom).prerotate(rotation % 360)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return RenderedPage(
        page=page_index,
        zoom=zoom,
        width=pixmap.width,
        height=pixmap.height,
        stride=pixmap.stride,
        samples=pixmap.samples,
        seconds=time.perf_counter() - started,
        rotation=rotation % 360,
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
            hits += find_across_pages(text, following, job.query, job.options, number)
    except Exception:
        hits = []  # a page that cannot be read has no results; the search goes on
    if hits:
        hits = hits[: MAX_SEARCH_HITS - job.found]
        job.found += len(hits)
        connection.send(("hits", token, job.search_id, hits))
    return True


def _worker_main(connection: Connection) -> None:
    """The helper process: open documents and draw the pages asked for."""
    import pymupdf

    doc = None
    wanted: list[tuple[int, float, int]] = []
    thumbnails: list[tuple[int, float, int]] = []  # small pictures, drawn when idle
    token = 0
    search: _SearchJob | None = None
    page_texts: dict[int, PageText] = {}  # letters of pages already read
    # Only for the automatic tests: pages that "kill" the helper when drawn.
    crash_pages = {int(n) for n in os.environ.get(TEST_CRASH_PAGES, "").split(",") if n.strip()}
    while True:
        # Read every waiting message before doing anything, so a newer list of
        # wanted pages (or a newer search) always wins over an older one.
        if not (wanted or thumbnails or search) or connection.poll():
            try:
                message = connection.recv()
            except (EOFError, OSError):
                return  # the program has gone
            kind = message[0]
            if kind == "quit":
                return
            if kind == "open":
                _, token, path, password = message
                wanted, thumbnails, search = [], [], None
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
                    connection.send(("opened", token, doc.page_count))
                    connection.send(("outline", token, read_outline(doc)))
                except Exception as exc:
                    doc = None
                    connection.send(("open_failed", token, str(exc)))
            elif kind == "want":
                _, want_token, items = message
                wanted = list(items) if want_token == token and doc is not None else []
            elif kind == "thumbnails":
                _, want_token, items = message
                thumbnails = list(items) if want_token == token and doc is not None else []
            elif kind == "search":
                _, search_token, search_id, query, whole_word, exact = message
                search = None
                if search_token == token and doc is not None:
                    search = _SearchJob(search_id, query, SearchOptions(whole_word, exact))
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
            elif kind == "copy":
                _, copy_token, copy_id, start, stop = message
                if copy_token == token and doc is not None:
                    try:
                        copied = _text_between(doc, start, stop, page_texts)
                    except Exception:
                        copied = ""
                    connection.send(("copied", token, copy_id, copied))
            elif kind == "close":
                wanted, thumbnails, search = [], [], None
                page_texts.clear()
                if doc is not None:
                    doc.close()
                    doc = None
            continue

        if not wanted and not thumbnails:
            # Nothing to draw: search one more page. Drawing always goes first,
            # so searching a long document never slows the scrolling down.
            if not _search_next_page(connection, token, doc, search, page_texts):
                search = None
            continue

        # The pages being read go before the small pictures of the side panel.
        kind = "page" if wanted else "thumbnail"
        page_index, zoom, rotation = (wanted or thumbnails).pop(0)
        # Said first: if drawing this page kills the helper, the program knows which.
        connection.send(("drawing", token, page_index))
        if page_index in crash_pages:
            os._exit(13)
        try:
            result = render_page(doc, page_index, zoom, rotation)
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
                )
            )
            connection.send_bytes(result.samples)
        except Exception as exc:
            connection.send(("page_failed", token, page_index, zoom, str(exc)))


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
    ) -> None:
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
                self._send(("open", self._token, str(self._path), self._password))
            self._send(("want", self._token, self._drawable(requests)))

    def want_thumbnails(self, requests: list[RenderRequest]) -> None:
        """Replace the list of small pictures to draw. They wait for the pages."""
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._send(("open", self._token, str(self._path), self._password))
            self._send(("thumbnails", self._token, self._drawable(requests)))

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
                self._send(("open", self._token, str(self._path), self._password))
            self._searching = True
            self._send(
                (
                    "search",
                    self._token,
                    self._search_id,
                    query,
                    options.whole_word,
                    options.exact,
                )
            )
            return self._search_id

    def want_text(self, page: int) -> None:
        """Ask for the letters of a page and where they are. Arrives in ``on_text``."""
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                self._send(("open", self._token, str(self._path), self._password))
            self._send(("text", self._token, page))

    def copy_text(self, start: tuple[int, int], stop: tuple[int, int]) -> int:
        """Ask for the text between two places, each (page, caret).

        It arrives in ``on_copied`` with the number this method returns.
        """
        with self._lock:
            self._copy_id += 1
            if self._path is None:
                return self._copy_id
            if self._ensure_started():
                self._send(("open", self._token, str(self._path), self._password))
            self._send(("copy", self._token, self._copy_id, start, stop))
            return self._copy_id

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

    def _drawable(self, requests: list[RenderRequest]) -> list[tuple[int, float, int]]:
        """The requests as the helper wants them, without the pages that killed it."""
        return [(r.page, r.zoom, r.rotation) for r in requests if r.page not in self._bad_pages]

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
                samples = connection.recv_bytes() if kind in ("page", "thumbnail") else b""
            except (EOFError, OSError, ValueError, TypeError):
                break
            if message[1] != self._token:
                continue  # belongs to a document that is no longer open
            if kind == "drawing":
                self._drawing = message[2]
            elif kind in ("page", "thumbnail"):
                _, _, page, zoom, width, height, stride, seconds, rotation = message
                self._drawing = None
                self._drawn_since_crash += 1
                if self._drawn_since_crash >= GOOD_PAGES_TO_FORGET_CRASHES:
                    self._crashes = 0  # the document is fine: the crash was a one-off
                drawn = RenderedPage(page, zoom, width, height, stride, samples, seconds, rotation)
                self._tell(self._on_page if kind == "page" else self._on_thumbnail, drawn)
            elif kind == "outline":
                self._tell(self._on_outline, message[2])
            elif kind == "text":
                self._tell(self._on_text, message[2], message[3])
            elif kind == "copied":
                self._tell(self._on_copied, message[2], message[3])
            elif kind == "page_failed":
                self._drawing = None
                self._tell(self._on_page_failed, message[2], message[3], message[4])
            elif kind == "open_failed":
                self._tell(self._on_open_failed, message[2])
            elif kind == "hits" and message[2] == self._search_id:
                self._tell(self._on_hits, message[2], message[3])
            elif kind == "search_done" and message[2] == self._search_id:
                self._searching = False
                self._tell(self._on_search_done, message[2], message[3])
        lost_search = bad_page = None
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
        if crashed and bad_page is not None:
            self._tell(self._on_page_failed, bad_page, 0.0, "the helper ended while drawing it")
        if crashed and lost_search is not None:
            self._tell(self._on_search_done, lost_search, False)  # ends early, with what was found
        if crashed and gave_up:
            self._tell(self._on_open_failed, "the helper process keeps crashing with this document")
        elif crashed:
            self._tell(self._on_crashed)
