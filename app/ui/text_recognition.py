"""Reading the text of the scanned pages of a document, in the background.

The pages go one after another: the render helper draws the grey picture of
a page, a ``Recognizer`` (a process of its own) straightens and reads it, and
meanwhile the next picture is being drawn. The user goes on reading: drawing
the pages on screen always goes first.

Everything read is written into the document at the end, as one change:
Deshacer takes it all away at once, and it reaches the PDF when the user
saves. Cancelling keeps the pages already read.
"""

import contextlib
from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.ocr import OcrError, OcrFailure, OcrPage, Recognizer

POLL_MS = 100
WAITING = 2  # pictures given to the reader at once: one read, the next ready
TRIES = 2  # a picture that cannot be drawn is asked for once more


class TextRecognition(QObject):
    """Reads the text of some pages of the document in a ``PdfView``."""

    progressed = Signal(int, int)  # pages done, pages in all
    # Pages whose text was written, pages in all, pages that could not be
    # read, and whether the user stopped it.
    finished = Signal(int, int, int, bool)
    failed = Signal(str)  # the reader stopped working: details for the log

    def __init__(
        self, view, pages: list[int], parent: QObject | None = None, replace: bool = False
    ) -> None:
        super().__init__(parent)
        self.view = view
        self.replace = replace  # recognising again: the text the pages had goes
        self._document = view._document
        # Every page has a number of its own here, which does not change when
        # sheets are put in or taken away: where it is now is in ``_where``.
        self._where: dict[int, int | None] = dict(enumerate(sorted(set(pages))))
        self._queue: list[int] = list(self._where)
        self._asked: int | None = None  # its picture is being drawn
        self._reading: set[int] = set()  # given to the reader
        self._tries: dict[int, int] = {}
        self.done: dict[int, OcrPage] = {}
        self.failures = 0
        self.total = len(self._where)
        self.running = False
        self._recognizer: Recognizer | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        view.reading_ready.connect(self._picture)
        view.reading_failed.connect(self._picture_failed)
        view.pages_moved.connect(self._moved)

    @property
    def count_done(self) -> int:
        return len(self.done) + self.failures

    def start(self) -> None:
        self.running = True
        try:
            self._recognizer = Recognizer()
        except Exception as exc:  # the process could not be started
            self._fail(str(exc))
            return
        self._timer.start()
        self.progressed.emit(0, self.total)
        self._ask_next()

    def cancel(self) -> None:
        """Stop now. What was read already is written into the document."""
        if self.running:
            self._end(cancelled=True)

    def stop(self) -> None:
        """Stop now and write nothing: the document is being closed."""
        self.running = False
        self._timer.stop()
        if self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None
        self._disconnect()

    # ---- the pictures --------------------------------------------------

    def _ask_next(self) -> None:
        if not self.running or self._asked is not None or len(self._reading) >= WAITING:
            return
        while self._queue:
            key = self._queue.pop(0)
            page = self._where.get(key)
            if page is None:
                self.failures += 1  # the page was taken away meanwhile
                continue
            self._asked = key
            self.view.want_reading(page)
            return
        self._check_end()

    def _asked_page(self, page: int) -> bool:
        return self._asked is not None and self._where.get(self._asked) == page

    def _picture(self, page: int, width: int, height: int, dpi: int, samples: object) -> None:
        if not self.running or not self._asked_page(page) or not self._same_document():
            return
        key, self._asked = self._asked, None
        try:
            self._recognizer.read(key, width, height, dpi, bytes(samples))
        except OcrError as error:
            self._fail(str(error))
            return
        self._reading.add(key)
        self._ask_next()

    def _picture_failed(self, page: int, _details: str) -> None:
        if not self.running or not self._asked_page(page):
            return
        key, self._asked = self._asked, None
        self._tries[key] = self._tries.get(key, 0) + 1
        if self._tries[key] < TRIES:
            self._queue.insert(0, key)
        else:
            self.failures += 1
            self.progressed.emit(self.count_done, self.total)
        self._ask_next()

    def _moved(self, at: int, by: int) -> None:
        """A page was put in or taken away: the pages after it have other numbers.

        The helper forgets the picture it was asked for; it is asked again.
        """
        for key, page in self._where.items():
            if page is None or page < at:
                continue
            self._where[key] = None if by < 0 and page == at else page + by
        if self._asked is not None:
            self._queue.insert(0, self._asked)
            self._asked = None
            QTimer.singleShot(0, self._ask_next)  # after the view has finished moving

    # ---- what is read --------------------------------------------------

    def _poll(self) -> None:
        if not self.running or self._recognizer is None:
            return
        if not self._same_document():
            self.stop()
            return
        try:
            results = self._recognizer.results()
        except OcrError as error:
            self._fail(str(error))
            return
        for result in results:
            self._reading.discard(result.page)
            if isinstance(result, OcrFailure):
                self.failures += 1
                continue
            page = self._where.get(result.page)
            if page is None:
                self.failures += 1
            else:
                self.done[result.page] = result
        if results:
            self.progressed.emit(self.count_done, self.total)
            self._ask_next()

    def _check_end(self) -> None:
        if self.running and not self._queue and self._asked is None and not self._reading:
            self._end(cancelled=False)

    def _fail(self, details: str) -> None:
        self.failed.emit(details)
        self._end(cancelled=False)

    def _end(self, cancelled: bool) -> None:
        self.stop()
        pages = []
        for key, result in sorted(self.done.items()):
            page = self._where.get(key)
            if page is not None:
                pages.append(replace(result, page=page))
        if pages and self._same_document():
            self.view.add_text_layer(pages, self.replace)
        else:
            pages = []
        failures = self.total - len(pages) if not cancelled else self.failures
        self.finished.emit(len(pages), self.total, failures, cancelled)

    def _same_document(self) -> bool:
        return self.view._document is self._document and self._document is not None

    def _disconnect(self) -> None:
        for signal, slot in (
            (self.view.reading_ready, self._picture),
            (self.view.reading_failed, self._picture_failed),
            (self.view.pages_moved, self._moved),
        ):
            with contextlib.suppress(RuntimeError, TypeError):
                signal.disconnect(slot)
