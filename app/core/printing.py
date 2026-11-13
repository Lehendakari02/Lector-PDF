"""The arithmetic of printing: which pages, and where each one goes on the paper.

Nothing here talks to a printer; the interface does that. Kept apart so it can
be tested on its own.
"""

import re
from enum import Enum

# Pages are drawn for the printer at most this sharp. More only makes the job
# slower and heavier without anything the eye can tell on paper.
MAX_PRINT_DPI = 300
MIN_PRINT_DPI = 150


class Scaling(Enum):
    """The value is what is stored in the settings file."""

    FIT = "ajustar"  # as big as the paper allows, whole page visible
    ACTUAL = "real"  # the size the document says, even if something is cut off

    @classmethod
    def from_setting(cls, value: object) -> "Scaling":
        return next((scaling for scaling in cls if scaling.value == value), cls.FIT)


class PageRangeError(ValueError):
    """What was typed in "Páginas" cannot be understood. ``reason`` says why."""

    EMPTY = "empty"
    NOT_UNDERSTOOD = "not understood"
    OUT_OF_RANGE = "out of range"

    def __init__(self, reason: str, piece: str = "") -> None:
        super().__init__(f"{reason}: {piece!r}")
        self.reason = reason
        self.piece = piece


_PIECE = re.compile(r"^(\d*)\s*(?:(-)\s*(\d*))?$")


def parse_pages(text: str, page_count: int) -> list[int]:
    """Turn "1-3, 7, 10-" into page numbers counting from 0, in the order asked.

    "10-" means from page 10 to the end and "-3" from the first to page 3. A
    page asked for twice is printed once. Raises ``PageRangeError``.
    """
    pages: list[int] = []
    pieces = [
        piece.strip() for piece in re.split(r"[,;]", text.replace("–", "-").replace("—", "-"))
    ]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        raise PageRangeError(PageRangeError.EMPTY)
    for piece in pieces:
        match = _PIECE.match(piece)
        if match is None or not (match.group(1) or match.group(3)):
            raise PageRangeError(PageRangeError.NOT_UNDERSTOOD, piece)
        first_text, dash, last_text = match.groups()
        first = int(first_text) if first_text else 1
        last = (int(last_text) if last_text else page_count) if dash else first
        if not (1 <= first <= page_count and 1 <= last <= page_count):
            raise PageRangeError(PageRangeError.OUT_OF_RANGE, piece)
        step = 1 if last >= first else -1
        for number in range(first, last + step, step):
            if number - 1 not in pages:
                pages.append(number - 1)
    return pages


def print_zoom(printer_dpi: float) -> float:
    """How much to enlarge a page (72 points per inch) when drawing it for a printer."""
    return min(max(printer_dpi, MIN_PRINT_DPI), MAX_PRINT_DPI) / 72


def is_landscape(width: float, height: float) -> bool:
    return width > height


def placement(
    page_width: float, page_height: float, area_width: float, area_height: float, scaling: Scaling
) -> tuple[float, float, float, float]:
    """Where a page goes inside the printable area: (left, top, width, height).

    All sizes in the same unit, the page at its real size. The page is centred.
    Fitting never enlarges a page more than the paper allows and never deforms it.
    """
    if page_width <= 0 or page_height <= 0:
        return 0.0, 0.0, 0.0, 0.0
    factor = 1.0
    if scaling is Scaling.FIT:
        factor = min(area_width / page_width, area_height / page_height)
    width, height = page_width * factor, page_height * factor
    return (area_width - width) / 2, (area_height - height) / 2, width, height
