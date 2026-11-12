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
from array import array
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.text import normalize_for_search

# Hyphens that can split a word at the end of a line. The soft hyphen is an
# invisible "may be split here" mark and is always ignored.
_LINE_END_HYPHENS = "-‐"
_SOFT_HYPHEN = "­"
CONTEXT_CHARS = 45
# A phrase that goes on to the next page is looked for in the last lines of one
# page followed by the first lines of the next.
BOUNDARY_LINES = 6
# Lines at the same height of two pages in a row with the same words (numbers
# aside) are headers, footers or page numbers, not part of the reading text.
_SAME_HEIGHT_POINTS = 2.0

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
    # For a result that starts at the end of ``page`` and ends on the next one:
    # its marks on that next page.
    next_rects: tuple[Rect, ...] = ()


@dataclass
class PageText:
    """The letters of one page, in reading order, ready to be searched.

    Kept compact (one string and two arrays of numbers, not a Python object per
    letter): a long document has millions of letters.
    """

    chars: str = ""  # one character per letter of the page
    boxes: array = field(default_factory=lambda: array("f"))  # x0, y0, x1, y1 per letter
    lines: array = field(default_factory=lambda: array("I"))  # line number of every letter
    # Position of the hyphen where a word is split at a line end.
    split_hyphens: set[int] = field(default_factory=set)
    # Paragraph (block of the page) every line belongs to, by line number.
    line_blocks: array = field(default_factory=lambda: array("I"))
    _streams: dict = field(default_factory=dict, repr=False)
    _line_spans: list | None = field(default=None, repr=False)
    _line_keys: list | None = field(default=None, repr=False)
    # The lines around the break with the next page, built once: (next page, joint, seam).
    _boundary: tuple | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Accept plain lists too (handy in tests): letters, (x0, y0, x1, y1), numbers.
        if not isinstance(self.chars, str):
            self.chars = "".join(self.chars)
        if not isinstance(self.boxes, array):
            self.boxes = array("f", (value for box in self.boxes for value in box))
        if not isinstance(self.lines, array):
            self.lines = array("I", self.lines)

    def __len__(self) -> int:
        return len(self.chars)

    def box(self, letter: int) -> Rect:
        return tuple(self.boxes[4 * letter : 4 * letter + 4])

    def size_in_bytes(self) -> int:
        """Rough memory this page takes, counting the simplified copies made to search."""
        letters = len(self.chars)
        own = 4 * letters + self.boxes.itemsize * len(self.boxes) + self.lines.itemsize * letters
        return own + 2 * 8 * letters  # up to two simplified copies with their maps

    def without_caches(self) -> "PageText":
        """A copy with only the letters, to send to another process."""
        return PageText(
            self.chars, self.boxes, self.lines, set(self.split_hyphens), self.line_blocks
        )

    def line_spans(self) -> list[tuple[int, int]]:
        """First letter and one past the last letter of every line, in order."""
        if self._line_spans is None:
            spans: list[tuple[int, int]] = []
            start = 0
            for index in range(1, len(self.lines) + 1):
                if index == len(self.lines) or self.lines[index] != self.lines[start]:
                    spans.append((start, index))
                    start = index
            self._line_spans = spans
        return self._line_spans


@lru_cache(maxsize=4096)
def _simplify(char: str) -> str:
    return normalize_for_search(char)


@lru_cache(maxsize=4096)
def _keep_exact(char: str) -> str:
    return unicodedata.normalize("NFC", char)


def read_page_text(page) -> PageText:
    """Collect the letters of a PyMuPDF page with their position."""
    import pymupdf

    chars: list[str] = []
    boxes = array("f")
    lines = array("I")
    # Ligatures are not preserved: "ﬁ" arrives as "f" and "i", so "oficina" is found.
    flags = pymupdf.TEXT_PRESERVE_WHITESPACE
    line_number = 0
    line_blocks = array("I")
    for block_number, block in enumerate(page.get_text("rawdict", flags=flags)["blocks"]):
        for line in block.get("lines", ()):
            before = len(chars)
            for span in line["spans"]:
                for char in span["chars"]:
                    letter, box = char["c"], char["bbox"]
                    if len(letter) != 1:
                        continue
                    if unicodedata.combining(letter):
                        # An accent written as a separate piece ("n" + "~"): make it
                        # one letter with the one before, as if it had been typed "ñ".
                        if len(chars) > before:
                            joined = unicodedata.normalize("NFC", chars[-1] + letter)
                            if len(joined) == 1:
                                chars[-1] = joined
                        continue
                    chars.append(letter)
                    boxes.extend(box)
                    lines.append(line_number)
            if len(chars) > before:
                line_number += 1
                line_blocks.append(block_number)
    text = PageText("".join(chars), boxes, lines, line_blocks=line_blocks)
    _mark_split_hyphens(text)
    return text


def _mark_split_hyphens(text: PageText) -> None:
    """Find the hyphens that split a word at the end of a line."""
    chars, lines = text.chars, text.lines
    text.split_hyphens.clear()
    for _start, stop in text.line_spans()[:-1]:
        end = stop - 1
        last = end
        while last > 0 and chars[last].isspace() and lines[last - 1] == lines[end]:
            last -= 1
        following = end + 1
        while following < len(chars) and chars[following].isspace():
            following += 1
        if (
            chars[last] in _LINE_END_HYPHENS
            and last > 0
            and chars[last - 1].isalpha()
            and lines[last - 1] == lines[last]
            and following < len(chars)
            and chars[following].islower()
        ):
            text.split_hyphens.add(last)


def _stream(text: PageText, exact: bool, keep_split_hyphens: bool) -> tuple[str, array]:
    """Simplified text of the page and, for each character, its source letter.

    A source of -1 marks a space that stands for a line break.
    """
    key = (exact, keep_split_hyphens)
    if key in text._streams:
        return text._streams[key]
    simplify = _keep_exact if exact else _simplify
    out: list[str] = []
    source = array("i")
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
        x0, y0, x1, y1 = text.box(letter)
        box = by_line.get(text.lines[letter])
        if box is None:
            by_line[text.lines[letter]] = [x0, y0, x1, y1]
        else:
            box[0], box[1] = min(box[0], x0), min(box[1], y0)
            box[2], box[3] = max(box[2], x1), max(box[3], y1)
    return tuple(tuple(box) for box in by_line.values())


def _readable(text: PageText, source: array, start: int, end: int) -> str:
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
    return [hit for hit, _letters in _find(text, query, options, page)]


def _find(
    text: PageText, query: str, options: SearchOptions, page: int
) -> list[tuple[SearchHit, list[int]]]:
    """The results of a page, each with the letters of the page it covers."""
    needle = prepare_query(query, options)
    if not needle:
        return []
    found: dict[tuple[int, int], tuple[SearchHit, list[int]]] = {}
    # A split word is tried joined ("articu-lo" as "articulo") and, for words
    # that really carry a hyphen ("físico-químico"), with the hyphen kept.
    variants = [False] + ([True] if "-" in needle and text.split_hyphens else [])
    for keep_split_hyphens in variants:
        stream, source = _stream(text, options.exact, keep_split_hyphens)
        for start, end in _find_spans(stream, needle, options.whole_word):
            letters = [letter for letter in source[start:end] if letter >= 0]
            if not letters or (letters[0], letters[-1]) in found:
                continue
            hit = SearchHit(
                page=page,
                rects=_line_rects(text, [n for n in letters if not text.chars[n].isspace()]),
                before=_readable(text, source, start - CONTEXT_CHARS, start),
                match=_readable(text, source, start, end),
                after=_readable(text, source, end, end + CONTEXT_CHARS),
            )
            found[(letters[0], letters[-1])] = (hit, letters)
    return [found[key] for key in sorted(found)]


def _line_keys(text: PageText) -> list[tuple[str, float]]:
    """For every line: what it says without numbers, and its height on the page.

    Without numbers, "Página 4" and "Página 5" say the same.
    """
    if text._line_keys is None:
        keys = []
        for start, stop in text.line_spans():
            words = normalize_for_search(text.chars[start:stop])
            words = "".join(" " if char.isdigit() else char for char in words)
            keys.append((" ".join(words.split()), text.boxes[4 * start + 1]))
        text._line_keys = keys
    return text._line_keys


def _reading_lines(text: PageText, other: PageText) -> list[tuple[int, int]]:
    """Lines of ``text`` that are not headers, footers or page numbers.

    Those are recognised because the other page has the same words at the same height.
    """
    elsewhere: dict[str, list[float]] = {}
    for key, top in _line_keys(other):
        elsewhere.setdefault(key, []).append(top)
    kept = []
    for span, (key, top) in zip(text.line_spans(), _line_keys(text), strict=True):
        if not any(abs(top - there) <= _SAME_HEIGHT_POINTS for there in elsewhere.get(key, ())):
            kept.append(span)
    return kept


def _boundary(first: PageText, second: PageText) -> tuple[PageText, int] | None:
    """A small page made of the last lines of ``first`` and the first of ``second``.

    Returns it with the position of the first letter that belongs to ``second``.
    """
    if first._boundary is not None and first._boundary[0] is second:
        return first._boundary[1]
    tail = _reading_lines(first, second)[-BOUNDARY_LINES:]
    head = _reading_lines(second, first)[:BOUNDARY_LINES]
    made = None
    if tail and head:
        chars: list[str] = []
        boxes = array("f")
        lines = array("I")
        for text, spans in ((first, tail), (second, head)):
            for start, stop in spans:
                number = (lines[-1] + 1) if lines else 0
                chars.append(text.chars[start:stop])
                boxes.extend(text.boxes[4 * start : 4 * stop])
                lines.extend([number] * (stop - start))
        joint = PageText("".join(chars), boxes, lines)
        _mark_split_hyphens(joint)
        made = (joint, sum(stop - start for start, stop in tail))
    first._boundary = (second, made)
    return made


def find_across_pages(
    first: PageText,
    second: PageText,
    query: str,
    options: SearchOptions = DEFAULT_OPTIONS,
    page: int = 0,
) -> list[SearchHit]:
    """Results that start at the end of ``first`` (page ``page``) and end on ``second``.

    Covers a phrase that goes on to the next page and a word split by a hyphen
    at the very end of a page. Headers and footers in between are skipped.
    """
    if not len(first) or not len(second) or not prepare_query(query, options):
        return []
    boundary = _boundary(first, second)
    if boundary is None:
        return []
    joint, seam = boundary  # seam: first letter of the second page

    hits = []
    for hit, letters in _find(joint, query, options, page):
        if not (letters[0] < seam <= letters[-1]):
            continue  # entirely on one page: the search of that page already has it
        visible = [n for n in letters if not joint.chars[n].isspace()]
        hits.append(
            SearchHit(
                page=page,
                rects=_line_rects(joint, [n for n in visible if n < seam]),
                before=hit.before,
                match=hit.match,
                after=hit.after,
                next_rects=_line_rects(joint, [n for n in visible if n >= seam]),
            )
        )
    return hits


def search_document(doc, query: str, options: SearchOptions = DEFAULT_OPTIONS):
    """Yield ``(page_number, hits)`` for every page of an open PyMuPDF document.

    Results that go on to the next page come with the page where they start.
    """
    following = read_page_text(doc[0]) if doc.page_count else None
    for number in range(doc.page_count):
        text = following
        hits = find_in_page(text, query, options, number)
        if number + 1 < doc.page_count:
            following = read_page_text(doc[number + 1])
            hits += find_across_pages(text, following, query, options, number)
        yield number, hits
