"""Recognises the text of scanned pages (OCR) in Spanish, with Tesseract.

The Tesseract engine comes inside PyMuPDF, so no separate program has to be
installed or shipped: only the Spanish language file, 2 MB, which lives in
``app/recursos/tessdata``.

Recognising a page takes a second or more and blocks Python meanwhile, so the
window never does it itself: a ``Recognizer`` reads the pages of a document
one after another in a separate process, the same idea as drawing pages. It
is given the pictures of the pages (the render helper draws them), so it works
the same with documents that have a password or pages not yet saved.

Before reading a page its picture is straightened: the slant of the lines is
measured and the picture turned so that they are level, and a page that is
upside down or on its side is turned the right way. What comes out are the
words, with their place on the straightened picture and how to get from there
to the page as it is shown (``OcrPage.matrix``).
"""

import math
import multiprocessing
import queue
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from app.core.history import file_key
from app.core.settings import Settings

LANGUAGE = "spa"
MIN_DPI = 150
MAX_DPI = 300
# A page with fewer letters than this and a big picture is taken for a scan.
FEW_LETTERS = 20
BIG_PICTURE = 0.5  # part of the page the picture covers

Rect = tuple[float, float, float, float]

# Offering to recognise the text of a scanned document when it is opened.
OFFER_SETTING = "ofrecer_reconocer_texto"
DECLINED_SETTING = "reconocer_texto_no"  # documents where the user said "not again"
MAX_DECLINED = 300


def offer_wanted(settings: Settings) -> bool:
    return settings.get(OFFER_SETTING, True) is not False


def declined(settings: Settings, path: str | Path) -> bool:
    """Whether the user asked not to be offered it again for this document."""
    kept = settings.get(DECLINED_SETTING)
    return isinstance(kept, list) and file_key(path) in kept


def decline(settings: Settings, path: str | Path) -> None:
    kept = settings.get(DECLINED_SETTING)
    kept = [key for key in kept if isinstance(key, str)] if isinstance(kept, list) else []
    key = file_key(path)
    if key not in kept:
        kept.append(key)
    settings.set(DECLINED_SETTING, kept[-MAX_DECLINED:])


class OcrError(Exception):
    """The text could not be recognised."""


Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class OcrWord:
    rect: Rect  # on the straightened page, in points
    text: str


@dataclass(frozen=True)
class OcrPage:
    """The words read on a page."""

    page: int
    words: tuple[OcrWord, ...]
    # From the straightened page to the page as it is shown, in points.
    matrix: Matrix = IDENTITY
    dpi: int = 0
    seconds: float = 0.0
    turned: float = 0.0  # degrees the picture was turned to read it
    text: str = field(default="", compare=False)  # line by line

    def shown_rect(self, word: OcrWord) -> Rect:
        """Where a word is on the page as it is shown."""
        import pymupdf

        box = pymupdf.Rect(word.rect) * pymupdf.Matrix(*self.matrix)
        return (box.x0, box.y0, box.x1, box.y1)


def tessdata_dir() -> Path:
    """Folder with the language files, in the source tree or in the packaged program."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "app" / "recursos" / "tessdata"


def is_available() -> bool:
    return (tessdata_dir() / f"{LANGUAGE}.traineddata").is_file()


def _is_picture(page) -> bool:
    page_area = abs(page.rect) or 1.0
    covered = sum(abs(info["bbox"] and _rect(info["bbox"])) for info in page.get_image_info())
    return covered / page_area >= BIG_PICTURE


def looks_scanned(page) -> bool:
    """True if a PyMuPDF page is a picture of a page, without real text."""
    if len(page.get_text("text").strip()) >= FEW_LETTERS:
        return False
    return _is_picture(page)


def looks_recognised(page) -> bool:
    """True if a page is a picture with invisible text on it: a scan whose
    text was already recognised (here or by another program)."""
    from app.core.text_layer import has_invisible_text

    return _is_picture(page) and has_invisible_text(page)


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


def page_picture(page, dpi: int | None = None):
    """The picture to read a page from: grey, as it is shown, without annotations."""
    import pymupdf

    dpi = dpi or best_dpi(page)
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False, annots=False)
    return pixmap, dpi


# ---- straightening -------------------------------------------------------

MAX_SLANT = 10.0  # degrees: more than this is not a slanted scan
MIN_SLANT = 0.1  # less than this is not worth turning the picture
SLANT_WIDTH = 500  # the picture is made about this wide to measure the slant
SLANT_POINTS = 12000  # dark points used to measure it
GOOD_WORDS = 0.15  # below this share of common words, the page may be the wrong way up
# The most common Spanish words: about four in ten words of any Spanish text.
# A page read upside down gives letters too ("ap", "sejp"), but not these.
_COMMON = """a al algo ante como con contra cual cuando de del desde donde e el en entre era es
esa ese esta este fue ha han hasta la las le les lo los mas más muy ni no o otra otro para
pero por porque que qué se según ser si sí sin sobre son su sus también tiene todo todos un
una uno unos y ya artículo ley real decreto plazo caso cada día año"""
COMMON_WORDS = frozenset(_COMMON.split())
_EDGES = ".,;:()[]«»“”\"'¿?¡!-–—"


def quality(words) -> float:
    """The share of the words read that are common Spanish words.

    A page read the wrong way up gives bits and symbols: it scores low.
    """
    words = [text.strip(_EDGES).lower() for text in words]
    words = [text for text in words if text]
    if not words:
        return 0.0
    return sum(1 for text in words if text in COMMON_WORDS) / len(words)


def _dark_points(gray) -> list[tuple[int, int]]:
    import pymupdf

    small = pymupdf.Pixmap(gray)
    while small.width > SLANT_WIDTH * 2:
        small.shrink(1)
    # The first byte of each point is its grey (a copy may carry an alpha byte too).
    width, height, stride, n = small.width, small.height, small.stride, small.n
    samples = small.samples
    cut = 128
    points = [
        (x, y)
        for y in range(height)
        for x, value in enumerate(samples[y * stride : y * stride + width * n : n])
        if value < cut
    ]
    step = max(1, len(points) // SLANT_POINTS)
    return points[::step]


def _sharpness(points, degrees: float, across: bool) -> int:
    """How sharp the lines of text are when looked at turned ``degrees``:
    the dark points of each line fall in the same few rows."""
    sine, cosine = math.sin(math.radians(degrees)), math.cos(math.radians(degrees))
    if across:  # lines going up or down the page: look along the columns
        rows = Counter(int(x * cosine + y * sine) for x, y in points)
    else:
        rows = Counter(int(y * cosine - x * sine) for x, y in points)
    return sum(count * count for count in rows.values())


def _steps(centre: float, step: float, reach: float) -> list[float]:
    count = round(reach / step)
    return [round(centre + index * step, 4) for index in range(-count, count + 1)]


def measure_slant(gray) -> tuple[float, bool]:
    """The slant of the lines of a picture, in degrees (positive: they go
    down to the right), and whether they run up or down the page."""
    points = _dark_points(gray)
    if len(points) < 50:
        return 0.0, False
    best = (-1, 0.0, False)
    for across in (False, True):
        score, centre = max((_sharpness(points, d, across), d) for d in _steps(0.0, 1.0, MAX_SLANT))
        for step, reach in ((0.25, 1.0), (0.05, 0.25)):
            score, centre = max(
                (_sharpness(points, d, across), d) for d in _steps(centre, step, reach)
            )
        best = max(best, (score, centre, across))
    _, degrees, across = best
    return (degrees if abs(degrees) >= MIN_SLANT else 0.0), across


def _turned(gray, dpi: int, degrees: float):
    """The picture turned ``degrees``, as a colour picture to read, and the
    matrix from the turned picture back to the page, in points."""
    import pymupdf

    width, height = gray.width * 72 / dpi, gray.height * 72 / dpi
    if abs(degrees) < 1e-6:
        picture = pymupdf.Pixmap(pymupdf.csRGB, gray)
        picture.set_dpi(dpi, dpi)
        return picture, IDENTITY
    source = pymupdf.open()
    page = source.new_page(width=width, height=height)
    page.insert_image(page.rect, pixmap=gray)
    turn = math.radians(degrees)
    cosine, sine = abs(math.cos(turn)), abs(math.sin(turn))
    turned_width, turned_height = width * cosine + height * sine, width * sine + height * cosine
    target = pymupdf.open()
    turned = target.new_page(width=turned_width, height=turned_height)
    turned.show_pdf_page(turned.rect, source, 0, rotate=degrees)
    picture = turned.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    picture.set_dpi(dpi, dpi)
    back = (
        pymupdf.Matrix(1, 0, 0, 1, -turned_width / 2, -turned_height / 2)
        * pymupdf.Matrix(degrees)
        * pymupdf.Matrix(1, 0, 0, 1, width / 2, height / 2)
    )
    source.close()
    target.close()
    return picture, tuple(back)


def _read_picture(picture) -> tuple[list[OcrWord], str]:
    """Run Tesseract on a colour picture: its words, and its text line by line."""
    import pymupdf

    data = picture.pdfocr_tobytes(language=LANGUAGE, tessdata=str(tessdata_dir()))
    with pymupdf.open("pdf", data) as read:
        found = read[0].get_text("words")
    words, lines, line, last = [], [], [], None
    for x0, y0, x1, y1, text, block, line_number, _ in found:
        words.append(OcrWord((x0, y0, x1, y1), text))
        if (block, line_number) != last and line:
            lines.append(" ".join(line))
            line = []
        line.append(text)
        last = (block, line_number)
    if line:
        lines.append(" ".join(line))
    return words, "\n".join(lines)


def read_picture(gray, dpi: int, page_number: int = 0) -> OcrPage:
    """Straighten a grey picture of a page and read its words. Blocks for a while."""
    if not is_available():
        raise OcrError(f"Language file not found in {tessdata_dir()}")
    started = time.perf_counter()
    try:
        slant, across = measure_slant(gray)
        first = slant + (90 if across else 0)
        best = None
        for degrees in (first, first + 180):
            picture, matrix = _turned(gray, dpi, degrees)
            words, text = _read_picture(picture)
            score = quality(word.text for word in words)
            if best is None or score > best[0]:
                best = (score, words, text, matrix, degrees)
            if score >= GOOD_WORDS or len(words) < 3:
                break  # read the right way up (or nothing to read)
    except OcrError:
        raise
    except Exception as exc:
        raise OcrError(f"Text recognition failed: {exc}") from exc
    _, words, text, matrix, degrees = best
    return OcrPage(
        page_number,
        tuple(words),
        matrix,
        dpi,
        time.perf_counter() - started,
        (degrees + 180) % 360 - 180,
        text,
    )


def recognize_page(page, page_number: int = 0, dpi: int | None = None) -> OcrPage:
    """Read the text of a PyMuPDF page from its picture. Blocks for a while."""
    if not is_available():
        raise OcrError(f"Language file not found in {tessdata_dir()}")
    try:
        gray, dpi = page_picture(page, dpi)
    except Exception as exc:
        raise OcrError(f"The page cannot be drawn: {exc}") from exc
    return read_picture(gray, dpi, page_number)


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


# ---- the process that reads -----------------------------------------------


@dataclass(frozen=True)
class OcrFailure:
    page: int
    details: str


def _recognizer_main(pictures, connection) -> None:
    import pymupdf

    while True:
        try:
            message = pictures.recv()
            if message[0] != "read":
                return
            _, page, width, height, dpi = message
            samples = pictures.recv_bytes()
        except (EOFError, OSError):
            return
        try:
            gray = pymupdf.Pixmap(pymupdf.csGRAY, width, height, samples, False)
            gray.set_dpi(dpi, dpi)
            result: OcrPage | OcrFailure = read_picture(gray, dpi, page)
        except Exception as exc:
            result = OcrFailure(page, str(exc))
        try:
            connection.send(result)
        except (OSError, ValueError):
            return


class Recognizer:
    """Reads pages in a separate process, one after another, as they are given.

    ``read`` hands it the grey picture of a page; ``results`` gives what is
    ready, without waiting. Only one process for a whole document: starting
    it takes a moment, reading each page does not need to.

    The pictures go one way and the words come back another, and the
    pictures are handed over by a thread of their own: a picture is a few
    megabytes, and on Windows handing it over waits until the process takes
    it. The window never waits for that.
    """

    def __init__(self) -> None:
        context = multiprocessing.get_context("spawn")
        pictures_in, self._pictures = context.Pipe(duplex=False)
        self._connection, results_out = context.Pipe(duplex=False)
        self._process = context.Process(
            target=_recognizer_main, args=(pictures_in, results_out), daemon=True
        )
        self._process.start()
        pictures_in.close()
        results_out.close()
        self._closed = False
        self._broken = False
        self._waiting: queue.Queue = queue.Queue()
        self._sender = threading.Thread(target=self._send_pictures, daemon=True)
        self._sender.start()

    def read(self, page: int, width: int, height: int, dpi: int, samples: bytes) -> None:
        """Hand over the picture of a page, without waiting."""
        if self._closed or self._broken:
            raise OcrError("the recognition process stopped")
        self._waiting.put((page, width, height, dpi, samples))

    def _send_pictures(self) -> None:
        while True:
            picture = self._waiting.get()
            if picture is None:
                return
            page, width, height, dpi, samples = picture
            try:
                self._pictures.send(("read", page, width, height, dpi))
                self._pictures.send_bytes(samples)
            except (OSError, ValueError):
                self._broken = True  # the process has gone: ``results`` says so
                return

    def results(self) -> list[OcrPage | OcrFailure]:
        """What has been read since last asked. Raises ``OcrError`` if the
        process has stopped."""
        found: list[OcrPage | OcrFailure] = []
        if self._closed:
            return found
        try:
            while self._connection.poll():
                found.append(self._connection.recv())
        except (EOFError, OSError):
            self.close()
            raise OcrError("the recognition process stopped") from None
        if not found and (self._broken or not self._process.is_alive()):
            self.close()
            raise OcrError("the recognition process stopped")
        return found

    def close(self) -> None:
        """Stop at once, even in the middle of a page."""
        if self._closed:
            return
        self._closed = True
        self._waiting.put(None)
        if self._process.is_alive():
            self._process.terminate()
        self._process.join(timeout=2)
        self._connection.close()
        self._pictures.close()
