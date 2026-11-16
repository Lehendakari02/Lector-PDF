"""Arrows and symbols inside the text written on the page.

The letters every PDF reader has (Helvetica, Times, Courier) bring no arrows
and no ticks. For those, the program carries a small font with only symbols
(taken from DejaVu Sans, a free font) and puts it inside the PDF the first time
one is used, so that every reader shows them. Normal letters keep their font.

Typing "->" gives an arrow, for those who want it (it can be turned off).
"""

import sys
from functools import cache
from pathlib import Path

from app.core.settings import Settings

FONT_NAME = "LPSim"  # how the pages of the PDF call the font of the symbols
FONT_FAMILY = "Lector PDF Simbolos"
_FONT_PATH = ("app", "recursos", "letras", "simbolos.ttf")

# What can be put with a click, by groups. The font holds exactly these.
GROUPS: tuple[tuple[str, str], ...] = (
    ("arrows", "→←↑↓↔↕⇒⇐⇔⇑⇓↳↵↗↘↙↖"),
    ("marks", "✓✗★☆☐☑☒♦"),
    ("bullets", "●○■□▲△▼▽◆◇▪◦"),
    ("numbers", "①②③④⑤⑥⑦⑧⑨⑩"),
    ("maths", "≠≈≤≥∞√∑∈∉∴∵⊂⊃∪∩"),
    ("greek", "αβγδεθλμπσφωΔΣΩ"),
)
SYMBOLS = frozenset("".join(symbols for _, symbols in GROUPS))

# Whether what is typed with plain keys turns into an arrow.
TYPED_SETTING = "texto_flechas"
# The longest first: "-->" must not be read as "-" and "->".
TYPED: tuple[tuple[str, str], ...] = (
    ("<-->", "↔"),
    ("<==>", "⇔"),
    ("-->", "→"),
    ("<--", "←"),
    ("<->", "↔"),
    ("==>", "⇒"),
    ("<=>", "⇔"),
    ("->", "→"),
    ("<-", "←"),
    ("=>", "⇒"),
)


_KEYS = frozenset("<>-=")
# The keys that are the beginning of longer ones.
_WAITING = frozenset(
    keys for keys, _ in TYPED if any(other != keys and other.startswith(keys) for other, _ in TYPED)
)


def typed_wanted(settings: Settings) -> bool:
    return settings.get(TYPED_SETTING, True) is not False


def font_file() -> Path:
    """Where the font of the symbols is."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*_FONT_PATH)


def is_symbol(letter: str) -> bool:
    return letter in SYMBOLS


def has_symbols(text: str) -> bool:
    return any(letter in SYMBOLS for letter in text)


def runs(line: str) -> list[tuple[bool, str]]:
    """A line cut into pieces of one kind: (written with the symbols, the piece)."""
    pieces: list[tuple[bool, str]] = []
    for letter in line:
        kind = letter in SYMBOLS
        if pieces and pieces[-1][0] == kind:
            pieces[-1] = (kind, pieces[-1][1] + letter)
        else:
            pieces.append((kind, letter))
    return pieces


def typed(text: str) -> str:
    """The text with the arrows that were typed with plain keys ("->")."""
    for keys, symbol in TYPED:
        text = text.replace(keys, symbol)
    return text


def typed_at(before: str) -> tuple[int, str] | None:
    """What to change in the text up to the caret, as it is being typed.

    Returns how many letters before the caret (not counting a last letter that
    is not part of the keys) turn into which arrow, or None. "->" changes at
    once. "<-" and "<--" may still grow ("<->", "<-->"), so they wait for the
    next letter, which stays after the arrow.
    """
    last = before[-1:] if before and before[-1] not in _KEYS else ""
    keys_end = before[: len(before) - len(last)]
    for keys, symbol in TYPED:
        if keys_end.endswith(keys):
            waits = keys in _WAITING
            if (last and waits) or (not last and not waits):
                return len(keys), symbol
            return None
    return None


@cache
def _font():
    import pymupdf

    return pymupdf.Font(fontfile=str(font_file()))


def width(text: str, size: float) -> float:
    """How wide a piece written with the symbols is, in points."""
    return _font().text_length(text, fontsize=size)


def glyphs(text: str) -> str:
    """A piece of symbols as the PDF writes it: the number of each drawing, in hex."""
    font = _font()
    return "".join(f"{font.has_glyph(ord(letter)):04x}" for letter in text)
