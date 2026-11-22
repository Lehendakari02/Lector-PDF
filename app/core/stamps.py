"""Quick marks and stamps for documents without fields: ✓, ✗, ●, today's date,
"Recibido" and stamps of one's own.

The marks are drawn (standard ink annotations), not letters, so they look the
same in every reader whatever fonts it has. The date and the stamps with words
are texts (standard free text annotations). Each one is an order like any
other drawing or text: moved, undone and saved in the same way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from app.core import drawing, notes
from app.core.commands import Color

CHECK = "check"
CROSS = "cross"
DOT = "dot"
TODAY = "today"
RECEIVED = "received"
OWN = "own"  # a stamp with words of one's own
MARKS = (CHECK, CROSS, DOT)

OWN_SETTING = "sellos/propios"
SIZE_SETTING = "sellos/tamano"
MARK_COLOR: Color = (0.1, 0.1, 0.1)
STAMP_COLOR: Color = (0.75, 0.1, 0.1)  # the red of a rubber stamp
DEFAULT_SIZE = 12.0  # points: about the size of a box of a form
SIZES = (9.0, 12.0, 16.0, 22.0)
MOST_OWN = 12


@dataclass(frozen=True)
class Stamp:
    kind: str
    words: str = ""  # for OWN (and RECEIVED, as it is called)

    def text(self, today: date | None = None) -> str:
        """The words it puts ("" for a mark)."""
        if self.kind == TODAY:
            return (today or date.today()).strftime("%d/%m/%Y")
        if self.kind in (RECEIVED, OWN):
            return self.words
        return ""


def _circle(cx: float, cy: float, radius: float, steps: int = 24):
    return tuple(
        (
            cx + radius * math.cos(2 * math.pi * i / steps),
            cy + radius * math.sin(2 * math.pi * i / steps),
        )
        for i in range(steps + 1)
    )


def mark_order(kind: str, page: int, x: float, y: float, size: float = DEFAULT_SIZE):
    """The drawing of a mark centred at (x, y) of the page as shown, ``size``
    points high."""
    half = size / 2
    width = max(1.0, size * 0.14)
    if kind == CHECK:
        strokes = [
            (
                (x - half * 0.8, y),
                (x - half * 0.2, y + half * 0.7),
                (x + half * 0.9, y - half * 0.8),
            )
        ]
    elif kind == CROSS:
        reach = half * 0.75
        strokes = [
            ((x - reach, y - reach), (x + reach, y + reach)),
            ((x - reach, y + reach), (x + reach, y - reach)),
        ]
    elif kind == DOT:
        # A circle as wide as its radius covers it from the middle out: a full dot.
        radius = half * 0.55
        return drawing.new_ink(page, [_circle(x, y, radius / 2)], MARK_COLOR, radius)
    else:
        raise ValueError(kind)
    return drawing.new_ink(page, strokes, MARK_COLOR, width)


def own_stamps(stored) -> list[str]:
    """The stamps of one's own kept in the settings, cleaned."""
    found: list[str] = []
    for words in stored if isinstance(stored, list) else ():
        if isinstance(words, str) and words.strip() and words.strip() not in found:
            found.append(words.strip())
    return found[:MOST_OWN]


def text_look(stamp: Stamp, size: float = DEFAULT_SIZE) -> dict:
    """How the words of a stamp are written: the date like handwriting in
    black; a stamp in red, bold."""
    if stamp.kind == TODAY:
        return {"font": notes.SANS, "size": size, "color": MARK_COLOR, "bold": False}
    return {"font": notes.SANS, "size": size, "color": STAMP_COLOR, "bold": True}
