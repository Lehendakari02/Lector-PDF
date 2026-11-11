"""Recognises the text of scanned pages (OCR) in Spanish, with Tesseract.

The Tesseract engine comes inside PyMuPDF, so no separate program has to be
installed or shipped: only the Spanish language file, 2 MB, which lives in
``app/recursos/tessdata``.

Recognising a page takes about a second and blocks Python meanwhile, so the
window must never do it itself: ``OcrJob`` does it in a separate process, the
same idea as drawing pages.
"""

import multiprocessing
import sys
import time
from dataclasses import dataclass
from pathlib import Path

LANGUAGE = "spa"
MIN_DPI = 150
MAX_DPI = 300
# A page with fewer letters than this and a big picture is taken for a scan.
FEW_LETTERS = 20
BIG_PICTURE = 0.5  # part of the page the picture covers

Rect = tuple[float, float, float, float]


class OcrError(Exception):
    """The text could not be recognised."""


@dataclass(frozen=True)
class OcrWord:
    rect: Rect  # in page points
    text: str


@dataclass(frozen=True)
class OcrPage:
    page: int
    text: str
    words: tuple[OcrWord, ...]
    dpi: int
    seconds: float


def tessdata_dir() -> Path:
    """Folder with the language files, in the source tree or in the packaged program."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "app" / "recursos" / "tessdata"


def is_available() -> bool:
    return (tessdata_dir() / f"{LANGUAGE}.traineddata").is_file()


def looks_scanned(page) -> bool:
    """True if a PyMuPDF page is a picture of a page, without real text."""
    if len(page.get_text("text").strip()) >= FEW_LETTERS:
        return False
    page_area = abs(page.rect) or 1.0
    covered = sum(abs(info["bbox"] and _rect(info["bbox"])) for info in page.get_image_info())
    return covered / page_area >= BIG_PICTURE


def _rect(box):
    import pymupdf

    return pymupdf.Rect(box)


def best_dpi(page) -> int:
    """Recognise at the resolution of the scan itself: enlarging it adds noise."""
    best = 0.0
    for info in page.get_image_info():
        box = _rect(info["bbox"])
        if box.width > 0:
            best = max(best, info["width"] / (box.width / 72))
    return int(min(MAX_DPI, max(MIN_DPI, round(best or MAX_DPI))))


def recognize_page(page, page_number: int = 0, dpi: int | None = None) -> OcrPage:
    """Read the text of a PyMuPDF page from its picture. Blocks for about a second."""
    if not is_available():
        raise OcrError(f"Language file not found in {tessdata_dir()}")
    started = time.perf_counter()
    dpi = dpi or best_dpi(page)
    try:
        text_page = page.get_textpage_ocr(
            language=LANGUAGE, dpi=dpi, full=True, tessdata=str(tessdata_dir())
        )
        words = tuple(
            OcrWord((x0, y0, x1, y1), word)
            for x0, y0, x1, y1, word, *_rest in page.get_text("words", textpage=text_page)
        )
        text = page.get_text("text", textpage=text_page)
    except Exception as exc:
        raise OcrError(f"Text recognition failed: {exc}") from exc
    return OcrPage(page_number, text, words, dpi, time.perf_counter() - started)


def add_text_layer(page, recognised: OcrPage) -> None:
    """Write the recognised words on the page as invisible text.

    The page looks the same, but its text can now be searched, selected and
    copied in any PDF reader: it is ordinary PDF text drawn in "invisible" mode.
    """
    import pymupdf

    for word in recognised.words:
        x0, y0, x1, y1 = word.rect
        text = word.text + " "
        try:
            width_at_size_1 = pymupdf.get_text_length(text, "helv", 1)
        except Exception:  # noqa: S112 - a letter the basic font lacks: skip the word
            continue
        if width_at_size_1 <= 0 or x1 <= x0 or y1 <= y0:
            continue
        size = min((y1 - y0) * 1.1, (x1 - x0) / width_at_size_1)
        page.insert_text(
            (x0, y1 - (y1 - y0) * 0.2), text, fontname="helv", fontsize=size, render_mode=3
        )


def recognize_file_page(path: str | Path, page_number: int) -> OcrPage:
    """Open the document, recognise one page and close it."""
    import pymupdf

    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:
        raise OcrError(f"Cannot open the document: {exc}") from exc
    with doc:
        if doc.needs_pass or not 0 <= page_number < doc.page_count:
            raise OcrError("The page cannot be read")
        return recognize_page(doc[page_number], page_number)


def _job_main(connection, path: str, page_number: int) -> None:
    try:
        connection.send(("done", recognize_file_page(path, page_number)))
    except Exception as exc:
        connection.send(("failed", str(exc)))


class OcrJob:
    """Recognises one page in a separate process; ask ``poll()`` now and then."""

    def __init__(self, path: str | Path, page_number: int) -> None:
        context = multiprocessing.get_context("spawn")
        self._connection, child_end = context.Pipe(duplex=False)
        self._process = context.Process(
            target=_job_main, args=(child_end, str(path), page_number), daemon=True
        )
        self._process.start()
        child_end.close()
        self._result: OcrPage | None = None
        self._error: str | None = None

    def poll(self) -> OcrPage | None:
        """The result if it is ready, None if still working. Raises ``OcrError``."""
        if self._result is None and self._error is None:
            if self._connection.poll():
                try:
                    kind, value = self._connection.recv()
                except (EOFError, OSError):
                    kind, value = "failed", "the recognition process stopped"
                if kind == "done":
                    self._result = value
                else:
                    self._error = value
                self._finish()
            elif not self._process.is_alive():
                self._error = "the recognition process stopped"
                self._finish()
        if self._error is not None:
            raise OcrError(self._error)
        return self._result

    def cancel(self) -> None:
        if self._process.is_alive():
            self._process.terminate()
        self._finish()
        if self._result is None and self._error is None:
            self._error = "cancelled"

    def _finish(self) -> None:
        self._process.join(timeout=2)
        self._connection.close()
