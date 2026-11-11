"""Finds text in PDF pages the way a person expects.

- Accents and capitals do not matter: "articulo" finds "Artículo". But "ñ" is
  its own letter: "año" never finds "ano".
- A word split with a hyphen at the end of a line ("Artícu-" / "lo") is found
  as one word, and a phrase that continues on the next line is found too.
- Options: whole words only, and exact match (accents and capitals count).

How it works: the text of a page is turned into one long simplified string
(the "stream"), remembering which letter of the page each character came from.
Searching is then a plain search in that string, and every result can be
traced back to its place on the page.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.text import normalize_for_search

# Hyphens that can split a word at the end of a line. The soft hyphen is an
# invisible "may be split here" mark and is always ignored.
_LINE_END_HYPHENS = "-‐"
_SOFT_HYPHEN = "­"
CONTEXT_CHARS = 45

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class SearchOptions:
    whole_word: bool = False
    exact: bool = False  # accents and capitals must match too


DEFAULT_OPTIONS = SearchOptions()


@dataclass(frozen=True)
class SearchHit:
    """One result: where it is and the sentence around it."""

    page: int
    rects: tuple[Rect, ...]  # one per line the result touches, in page points
    before: str
    match: str
    after: str


@dataclass
class PageText:
    """The letters of one page, in reading order, ready to be searched."""

    chars: list[str] = field(default_factory=list)
    boxes: list[Rect] = field(default_factory=list)
    lines: list[int] = field(default_factory=list)  # line number of every letter
    # Position of the hyphen where a word is split at a line end -> True.
    split_hyphens: set[int] = field(default_factory=set)
    _streams: dict = field(default_factory=dict, repr=False)


@lru_cache(maxsize=4096)
def _simplify(char: str) -> str:
    return normalize_for_search(char)


@lru_cache(maxsize=4096)
def _keep_exact(char: str) -> str:
    return unicodedata.normalize("NFC", char)


def read_page_text(page) -> PageText:
    """Collect the letters of a PyMuPDF page with their position."""
    import pymupdf

    text = PageText()
    flags = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_PRESERVE_LIGATURES
    line_number = 0
    line_ends: list[int] = []  # index of the last letter of every line
    for block in page.get_text("rawdict", flags=flags)["blocks"]:
        for line in block.get("lines", ()):
            before = len(text.chars)
            for span in line["spans"]:
                for char in span["chars"]:
                    text.chars.append(char["c"])
                    text.boxes.append(char["bbox"])
                    text.lines.append(line_number)
            if len(text.chars) > before:
                line_ends.append(len(text.chars) - 1)
                line_number += 1

    chars = text.chars
    for end in line_ends[:-1]:
        last = end
        while last > 0 and chars[last].isspace() and text.lines[last - 1] == text.lines[end]:
            last -= 1
        following = end + 1
        while following < len(chars) and chars[following].isspace():
            following += 1
        if (
            chars[last] in _LINE_END_HYPHENS
            and last > 0
            and chars[last - 1].isalpha()
            and text.lines[last - 1] == text.lines[last]
            and following < len(chars)
            and chars[following].islower()
        ):
            text.split_hyphens.add(last)
    return text


def _stream(text: PageText, exact: bool, keep_split_hyphens: bool) -> tuple[str, list[int]]:
    """Simplified text of the page and, for each character, its source letter.

    A source of -1 marks a space that stands for a line break.
    """
    key = (exact, keep_split_hyphens)
    if key in text._streams:
        return text._streams[key]
    simplify = _keep_exact if exact else _simplify
    out: list[str] = []
    source: list[int] = []
    previous_line = 0
    joined = False  # the previous line ended in a split word
    pending_space = -2  # source of a space waiting to be written, -2 = none
    for index, char in enumerate(text.chars):
        line = text.lines[index]
        if line != previous_line:
            previous_line = line
            if not joined and pending_space == -2:
                pending_space = -1
            joined = False
        if char == _SOFT_HYPHEN:
            continue
        if index in text.split_hyphens:
            joined = True
            pending_space = -2
            if keep_split_hyphens:
                out.append("-")
                source.append(index)
            continue
        if char.isspace():
            if not joined and pending_space == -2:
                pending_space = index
            continue
        if pending_space != -2:
            if out:
                out.append(" ")
                source.append(pending_space)
            pending_space = -2
        for piece in simplify(char):
            out.append(piece)
            source.append(index)
    result = ("".join(out), source)
    text._streams[key] = result
    return result


def prepare_query(query: str, options: SearchOptions = DEFAULT_OPTIONS) -> str:
    """Simplify what the person typed in the same way as the page text."""
    query = query.replace(_SOFT_HYPHEN, "")
    query = unicodedata.normalize("NFC", query) if options.exact else normalize_for_search(query)
    return re.sub(r"\s+", " ", query).strip()


def _is_word_char(char: str) -> bool:
    return char.isalnum()


def _find_spans(stream: str, needle: str, whole_word: bool) -> list[tuple[int, int]]:
    spans = []
    start = stream.find(needle)
    while start != -1:
        end = start + len(needle)
        inside_word = (
            start > 0 and _is_word_char(stream[start - 1]) and _is_word_char(needle[0])
        ) or (end < len(stream) and _is_word_char(stream[end]) and _is_word_char(needle[-1]))
        if not (whole_word and inside_word):
            spans.append((start, end))
        start = stream.find(needle, start + 1)
    return spans


def _line_rects(text: PageText, letters: list[int]) -> tuple[Rect, ...]:
    by_line: dict[int, list[float]] = {}
    for letter in letters:
        x0, y0, x1, y1 = text.boxes[letter]
        box = by_line.get(text.lines[letter])
        if box is None:
            by_line[text.lines[letter]] = [x0, y0, x1, y1]
        else:
            box[0], box[1] = min(box[0], x0), min(box[1], y0)
            box[2], box[3] = max(box[2], x1), max(box[3], y1)
    return tuple(tuple(box) for box in by_line.values())


def _readable(text: PageText, source: list[int], start: int, end: int) -> str:
    """The original letters (capitals and accents) of a stretch of the stream."""
    pieces = []
    previous = None
    for position in range(max(0, start), min(len(source), end)):
        letter = source[position]
        if letter == previous and letter != -1:
            continue  # one letter that became two characters when simplified
        previous = letter
        pieces.append(" " if letter == -1 or text.chars[letter].isspace() else text.chars[letter])
    return "".join(pieces)


def find_in_page(
    text: PageText, query: str, options: SearchOptions = DEFAULT_OPTIONS, page: int = 0
) -> list[SearchHit]:
    """All the places of a page where ``query`` appears, in reading order."""
    needle = prepare_query(query, options)
    if not needle:
        return []
    found: dict[tuple[int, int], SearchHit] = {}
    # A split word is tried joined ("articu-lo" as "articulo") and, for words
    # that really carry a hyphen ("físico-químico"), with the hyphen kept.
    variants = [False] + ([True] if "-" in needle and text.split_hyphens else [])
    for keep_split_hyphens in variants:
        stream, source = _stream(text, options.exact, keep_split_hyphens)
        for start, end in _find_spans(stream, needle, options.whole_word):
            letters = [letter for letter in source[start:end] if letter >= 0]
            if not letters or (letters[0], letters[-1]) in found:
                continue
            found[(letters[0], letters[-1])] = SearchHit(
                page=page,
                rects=_line_rects(text, [n for n in letters if not text.chars[n].isspace()]),
                before=_readable(text, source, start - CONTEXT_CHARS, start),
                match=_readable(text, source, start, end),
                after=_readable(text, source, end, end + CONTEXT_CHARS),
            )
    return [found[key] for key in sorted(found)]


def search_document(doc, query: str, options: SearchOptions = DEFAULT_OPTIONS):
    """Yield ``(page_number, hits)`` for every page of an open PyMuPDF document."""
    for number in range(doc.page_count):
        yield number, find_in_page(read_page_text(doc[number]), query, options, number)
