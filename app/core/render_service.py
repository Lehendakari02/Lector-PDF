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
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path

from app.core.search import (
    DEFAULT_OPTIONS,
    PageText,
    SearchHit,
    SearchOptions,
    find_in_page,
    read_page_text,
)

# Never draw absurdly large images, whatever is asked (protects memory).
MAX_PIXELS_PER_PAGE = 60_000_000
# If the helper dies this many times with the same document, the document is
# the cause: stop restarting it and report the document as unreadable.
MAX_CRASHES_PER_DOCUMENT = 3
# A search stops after this many results ("a" in a long book has 100 000).
MAX_SEARCH_HITS = 5000
# Pages whose letters are kept ready, so the next search is much faster.
MAX_PAGE_TEXTS = 3000


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


def _search_next_page(connection, token, doc, job: _SearchJob, page_texts) -> bool:
    """Search one page and send what was found. False when the search is over."""
    if job.next_page >= doc.page_count or job.found >= MAX_SEARCH_HITS:
        too_many = job.found >= MAX_SEARCH_HITS
        connection.send(("search_done", token, job.search_id, too_many))
        return False
    number = job.next_page
    job.next_page += 1
    try:
        text = page_texts.get(number)
        if text is None:
            if len(page_texts) >= MAX_PAGE_TEXTS:
                page_texts.clear()
            text = page_texts[number] = read_page_text(doc[number])
        hits = find_in_page(text, job.query, job.options, number)
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
    token = 0
    search: _SearchJob | None = None
    page_texts: dict[int, PageText] = {}  # letters of pages already read
    while True:
        # Read every waiting message before doing anything, so a newer list of
        # wanted pages (or a newer search) always wins over an older one.
        if not (wanted or search) or connection.poll():
            try:
                message = connection.recv()
            except (EOFError, OSError):
                return  # the program has gone
            kind = message[0]
            if kind == "quit":
                return
            if kind == "open":
                _, token, path, password = message
                wanted, search = [], None
                page_texts.clear()
                if doc is not None:
                    doc.close()
                    doc = None
                try:
                    doc = pymupdf.open(path, filetype="pdf")
                    if doc.needs_pass and not (password and doc.authenticate(password)):
                        raise ValueError("password required")
                    connection.send(("opened", token, doc.page_count))
                except Exception as exc:
                    doc = None
                    connection.send(("open_failed", token, str(exc)))
            elif kind == "want":
                _, want_token, items = message
                wanted = list(items) if want_token == token and doc is not None else []
            elif kind == "search":
                _, search_token, search_id, query, whole_word, exact = message
                search = None
                if search_token == token and doc is not None:
                    search = _SearchJob(search_id, query, SearchOptions(whole_word, exact))
            elif kind == "cancel_search":
                search = None
            elif kind == "close":
                wanted, search = [], None
                page_texts.clear()
                if doc is not None:
                    doc.close()
                    doc = None
            continue

        if not wanted:
            # Nothing to draw: search one more page. Drawing always goes first,
            # so searching a long document never slows the scrolling down.
            if not _search_next_page(connection, token, doc, search, page_texts):
                search = None
            continue

        page_index, zoom, rotation = wanted.pop(0)
        try:
            result = render_page(doc, page_index, zoom, rotation)
            connection.send(
                (
                    "page",
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
    ) -> None:
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
        self.restarts = 0

    # ---- public API -----------------------------------------------------

    def open(self, path: str | Path, password: str | None = None) -> None:
        """Tell the helper which document to draw from now on."""
        with self._lock:
            self._path, self._password = Path(path), password
            self._token += 1
            self._crashes = 0
            self._ensure_started()
            self._send(("open", self._token, str(self._path), password))

    def want(self, requests: list[RenderRequest]) -> None:
        """Replace the list of pages to draw, most urgent first."""
        with self._lock:
            if self._path is None:
                return
            if self._ensure_started():
                # A new helper knows nothing yet: give it the document again.
                self._send(("open", self._token, str(self._path), self._password))
            self._send(("want", self._token, [(r.page, r.zoom, r.rotation) for r in requests]))

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
                samples = connection.recv_bytes() if kind == "page" else b""
            except (EOFError, OSError, ValueError, TypeError):
                break
            if message[1] != self._token:
                continue  # belongs to a document that is no longer open
            if kind == "page":
                _, _, page, zoom, width, height, stride, seconds, rotation = message
                self._on_page(
                    RenderedPage(page, zoom, width, height, stride, samples, seconds, rotation)
                )
            elif kind == "page_failed":
                self._on_page_failed(message[2], message[3], message[4])
            elif kind == "open_failed":
                self._on_open_failed(message[2])
            elif kind == "hits" and message[2] == self._search_id:
                self._on_hits(message[2], message[3])
            elif kind == "search_done" and message[2] == self._search_id:
                self._searching = False
                self._on_search_done(message[2], message[3])
        lost_search = None
        with self._lock:
            crashed = not self._closing and connection is self._connection
            if crashed:
                with contextlib.suppress(OSError):
                    connection.close()
                self._process = self._connection = None
                self.restarts += 1
                self._crashes += 1
                gave_up = self._crashes >= MAX_CRASHES_PER_DOCUMENT
                lost_search = self._search_id if self._searching else None
                self._searching = False
        if crashed and lost_search is not None:
            self._on_search_done(lost_search, False)  # ends early, with what was found
        if crashed and gave_up:
            self._on_open_failed("the helper process keeps crashing with this document")
        elif crashed:
            self._on_crashed()
