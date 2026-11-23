"""Arrows and symbols inside the text written on the page.

The letters every PDF reader has (Helvetica, Times, Courier) bring no arrows
and no ticks. For those, the program carries a small font with only symbols
(taken from DejaVu Sans, a free font) and puts it inside the PDF the first time
one is used, so that every reader shows them. Normal letters keep their font.

The same font also carries the letters of other languages that those built-in
letters lack: every European language (Polish, Czech, Romanian, Turkish, Greek
old and new, Russian and the other Cyrillic ones…: «Łódź», «Ştefan», «Ἀθῆναι»,
«Москва»), Vietnamese, Armenian, Georgian, and small signs such as H₂O, x², ½
or ₽, so that a name written in a text looks the same everywhere. It comes in a
normal and a bold weight, for bold texts.

Scripts that are written from right to left or that join their letters
(Hebrew, Arabic) and the ones with thousands of signs (Chinese, Japanese,
Korean) are not in it: a text with them is written as the engine can (it shows
here, and in other readers that have a font for them).

Typing "->" gives an arrow, for those who want it (it can be turned off).
"""

import sys
import unicodedata
from functools import cache
from pathlib import Path

from app.core.settings import Settings

# How the pages of the PDF call the font of the symbols, normal and bold.
FONT_NAME = "LPSim2"  # "LPSim" was the smaller font of version 0.6 and earlier
BOLD_FONT_NAME = "LPSim2B"
FONT_FAMILY = "Lector PDF Simbolos"
_FONT_FOLDER = ("app", "recursos", "letras")
_FONT_FILES = {False: "simbolos.ttf", True: "simbolos-negrita.ttf"}

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
# Where the letters of other languages are (Unicode), for the font of the symbols.
EXTRA_RANGES = (
    (0x0100, 0x024F),  # Latin Extended-A and B (Łódź, Ştefan, ǅ…)
    (0x0250, 0x02FF),  # phonetic letters and accents written apart
    (0x0300, 0x036F),  # accents that go on the letter before
    (0x0370, 0x03FF),  # Greek
    (0x0400, 0x052F),  # Cyrillic
    (0x0530, 0x058F),  # Armenian
    (0x10A0, 0x10FF),  # Georgian
    (0x1E00, 0x1EFF),  # more Latin letters with accents (Vietnamese)
    (0x1F00, 0x1FFF),  # old Greek (Ἀθῆναι)
    (0x2000, 0x206F),  # dashes, spaces and other punctuation
    (0x2070, 0x209F),  # small numbers above and below (x², H₂O)
    (0x20A0, 0x20CF),  # currency signs (₽, ₹, ₺)
    (0x2100, 0x218F),  # letter-like signs and fractions (№, ℃, ½, Ⅳ)
)

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


def font_file(bold: bool = False) -> Path:
    """Where the font of the symbols is (its normal or its bold weight)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*_FONT_FOLDER, _FONT_FILES[bold])


def font_name(bold: bool = False) -> str:
    return BOLD_FONT_NAME if bold else FONT_NAME


def tidy(text: str) -> str:
    """The text with each accented letter as one letter ("e" + "´" → "é").

    Some keyboards and copied texts bring the accent apart; joined, the letter
    is found in the fonts and looks as it should.
    """
    return unicodedata.normalize("NFC", text)


def _built_in(letter: str) -> bool:
    """Whether the letters every reader has (WinAnsi) bring this one."""
    try:
        letter.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


@cache
def is_covered(letter: str) -> bool:
    """Whether a letter can be written so that every reader shows it: with the
    built-in letters or with the font of the symbols."""
    return _built_in(letter) or is_symbol(letter)


def all_covered(text: str) -> bool:
    return all(is_covered(letter) for letter in text if letter not in "\n\r")


@cache
def is_symbol(letter: str) -> bool:
    """Whether a letter is written with the font of the symbols: a symbol, or a
    letter of another language that the built-in letters (WinAnsi) lack."""
    if letter in SYMBOLS:
        return True
    if len(letter) != 1 or ord(letter) < 0x100:
        return False
    if _built_in(letter):
        return False  # the built-in letters have it (€, Œ, š…)
    try:
        return _font().has_glyph(ord(letter)) != 0
    except Exception:  # the font is missing: written as the engine can
        return False


def has_symbols(text: str) -> bool:
    return any(is_symbol(letter) for letter in text)


def runs(line: str) -> list[tuple[bool, str]]:
    """A line cut into pieces of one kind: (written with the symbols, the piece)."""
    pieces: list[tuple[bool, str]] = []
    for letter in line:
        kind = is_symbol(letter)
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
def _font(bold: bool = False):
    import pymupdf

    return pymupdf.Font(fontfile=str(font_file(bold)))


def width(text: str, size: float, bold: bool = False) -> float:
    """How wide a piece written with the symbols is, in points."""
    return _font(bold).text_length(text, fontsize=size)


def glyphs(text: str, bold: bool = False) -> str:
    """A piece of symbols as the PDF writes it: the number of each drawing, in hex."""
    font = _font(bold)
    return "".join(f"{font.has_glyph(ord(letter)):04x}" for letter in text)
