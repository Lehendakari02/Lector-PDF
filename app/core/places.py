"""Find an article, a section or a part of a document by its number.

"art. 14", "artículo 14 bis", "3.2", "capítulo II", "título preliminar" or
"disposición adicional primera" are read as a *place*, and the place is looked
for at the start of the lines of the document, where headings are: "Artículo
14." in a law of the BOE, "3.2. Los derechos" in a syllabus. A mention in the
middle of a sentence ("según el artículo 14") is not a heading and is not
taken. Lines of a table of contents (with dot leaders or a page number at the
end) are only taken when nothing better is found.

Numbers can be written in any of the usual ways: "capítulo 2", "capítulo II"
and "capítulo segundo" are the same place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.search import PageText, Rect, normalize_for_search

ARTICLE = "article"  # "Artículo 14", "Art. 14 bis"
SECTION = "section"  # "3.2", "3.2.1", "apartado 3"
PART = "part"  # a word and a number: "capítulo II", "disposición adicional primera"

# How good a line is as the place wanted: the best one found is taken.
HEADING = 2  # starts with a capital letter and is not in a table of contents
MENTION = 1  # starts in small letters: probably a sentence that goes on
CONTENTS = 0  # a line of a table of contents

# Words that name parts of a document, as they are written once simplified.
# "disposicion adicional" and the like go before the shorter ones.
PART_WORDS = (
    "disposicion adicional",
    "disposicion transitoria",
    "disposicion derogatoria",
    "disposicion final",
    "disposicion",
    "capitulo",
    "titulo",
    "libro",
    "seccion",
    "subseccion",
    "anexo",
    "tema",
    "parte",
    "bloque",
    "leccion",
    "unidad",
)
SHORT_PART_WORDS = {
    "cap": "capitulo",
    "tit": "titulo",
    "secc": "seccion",
    "sec": "seccion",
    "disp adic": "disposicion adicional",
    "disp trans": "disposicion transitoria",
    "disp derog": "disposicion derogatoria",
    "disp final": "disposicion final",
    "da": "disposicion adicional",
    "dt": "disposicion transitoria",
    "dd": "disposicion derogatoria",
    "df": "disposicion final",
}
SECTION_WORDS = ("apartado", "punto", "epigrafe", "§")
LATIN = ("bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "nonies")
ORDINALS = {
    "primero": 1,
    "primera": 1,
    "primer": 1,
    "segundo": 2,
    "segunda": 2,
    "tercero": 3,
    "tercera": 3,
    "tercer": 3,
    "cuarto": 4,
    "cuarta": 4,
    "quinto": 5,
    "quinta": 5,
    "sexto": 6,
    "sexta": 6,
    "septimo": 7,
    "septima": 7,
    "setimo": 7,
    "octavo": 8,
    "octava": 8,
    "noveno": 9,
    "novena": 9,
    "decimo": 10,
    "decima": 10,
    "undecimo": 11,
    "undecima": 11,
    "duodecimo": 12,
    "duodecima": 12,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}
SAME_WORDS = {"unico": "unico", "unica": "unico", "preliminar": "preliminar"}
ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}

_ARTICLE_TYPED = re.compile(r"^(?:articulos?|arts?\.?|a\.)\s*(.+)$")
_ARTICLE_NUMBER = re.compile(r"^(\d+)\s*(?:\.\s*)?(" + "|".join(LATIN) + r")?\b")
_SECTION_NUMBER = re.compile(r"^(\d+(?:\.\d+)+|\d+)\.?$")
_CONTENTS_LINE = re.compile(r"(?:\.\s*){4,}|…{2,}|·{4,}|_{4,}|\s{2,}\d+\s*$|\.\s*\d+\s*$")


@dataclass(frozen=True)
class Wanted:
    """A place asked for. ``number`` is written in one way only ("14 bis",
    "3.2", "2", "preliminar"); ``word`` is the part's name ("capitulo")."""

    kind: str
    number: str
    word: str = ""


@dataclass(frozen=True)
class Place:
    """Where a place was found: the page, the letter its line starts with, the
    rectangle of that line (page points, as shown) and how good it is."""

    page: int
    letter: int
    rect: Rect
    rank: int


def _number_of(word: str) -> str | None:
    """A number written as digits, in Roman numerals or in words: "2", or None."""
    word = word.strip().rstrip(".").removesuffix("º").removesuffix("ª").rstrip(".")
    word = word.removesuffix(".o").removesuffix(".a")
    if not word:
        return None
    if word.isdigit():
        return str(int(word))
    if word in ORDINALS:
        return str(ORDINALS[word])
    if word in SAME_WORDS:
        return SAME_WORDS[word]
    if all(letter in ROMAN for letter in word):
        total, previous = 0, 0
        for letter in reversed(word):
            value = ROMAN[letter]
            total += -value if value < previous else value
            previous = max(previous, value)
        if total > 0 and len(word) <= 8:
            return str(total)
    return None


def _part_number(word: str) -> str | None:
    """The number of a part: as ``_number_of``, or a letter ("anexo B")."""
    number = _number_of(word)
    if number is None and len(word) == 1 and word.isalpha():
        return word
    return number


def _article_number(text: str) -> str | None:
    text = text.strip()
    if text in SAME_WORDS:
        return SAME_WORDS[text]
    found = _ARTICLE_NUMBER.match(text)
    if not found:
        return None
    number = str(int(found.group(1)))
    return f"{number} {found.group(2)}" if found.group(2) else number


def _simple(text: str) -> str:
    """Lower case, without accents, with single spaces (the ñ stays an ñ)."""
    return " ".join(normalize_for_search(text).split())


def parse_wanted(text: str) -> Wanted | None:
    """What a typed text asks for, or None if it is not a place.

    A bare number is a page, not a place: the page box keeps that meaning.
    """
    simple = _simple(text)
    if not simple or simple.isdigit():
        return None
    article = _ARTICLE_TYPED.match(simple)
    if article:
        number = _article_number(article.group(1))
        return Wanted(ARTICLE, number) if number else None
    for word in SECTION_WORDS:
        if simple.startswith(word):
            simple = simple[len(word) :].strip()
            break
    section = _SECTION_NUMBER.match(simple)
    if section:
        return Wanted(SECTION, ".".join(str(int(n)) for n in section.group(1).split(".")))
    loose = simple.replace(".", " ").replace("  ", " ")
    for short, word in sorted(SHORT_PART_WORDS.items(), key=lambda pair: -len(pair[0])):
        if loose == short or loose.startswith(short + " "):
            loose = word + loose[len(short) :]
            break
    for word in PART_WORDS:
        if loose == word or loose.startswith(word + " "):
            rest = loose[len(word) :].strip()
            if not rest:
                return Wanted(PART, "", word)
            number = _part_number(rest.split()[0])
            return Wanted(PART, number, word) if number else None
    return None


def line_matches(line: str, wanted: Wanted) -> bool:
    """Whether a line of text starts with the place wanted."""
    simple = _simple(line)
    if wanted.kind == ARTICLE:
        found = re.match(r"^(?:articulo|art\.?)\s*(.+)$", simple)
        return bool(found) and _article_number(found.group(1)) == wanted.number
    if wanted.kind == SECTION:
        found = re.match(r"^(\d+(?:\.\d+)*)(?:\.|\)|\s|-|$)", simple)
        if not found:
            return False
        return ".".join(str(int(n)) for n in found.group(1).split(".")) == wanted.number
    word = wanted.word
    if not simple.startswith(word):
        return False
    rest = simple[len(word) :]
    if rest and rest[0].isalnum():
        return False  # "disposiciones" is not "disposicion"
    if not wanted.number:
        return True
    pieces = rest.replace(".", " ").split()
    return bool(pieces) and _part_number(pieces[0].strip(".:,;-")) == wanted.number


def rank_of(line: str) -> int:
    stripped = line.strip()
    if _CONTENTS_LINE.search(stripped):
        return CONTENTS
    first = next((char for char in stripped if char.isalpha()), "")
    return MENTION if first.islower() else HEADING


def lines_of(text: PageText):
    """Every line of a page: (first letter, text, rectangle)."""
    for start, stop in text.line_spans():
        line = text.chars[start:stop]
        boxes = [
            text.box(index) for index in range(start, stop) if not line[index - start].isspace()
        ]
        if not boxes:
            continue
        rect = (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        yield start, line, rect


def places_in_page(text: PageText, wanted: Wanted, page: int) -> list[Place]:
    """Every line of a page that starts with the place, in reading order."""
    return [
        Place(page, start, rect, rank_of(line))
        for start, line, rect in lines_of(text)
        if line_matches(line, wanted)
    ]


class PlaceSearch:
    """Looks for a place page by page, so the helper can stop to draw.

    It starts after ``after`` (page, letter) — the place found before, to go on
    to the next one — or at the beginning, and goes round the document once.
    The first heading found is the answer; if there is none, the best of the
    rest (a sentence, then a table of contents).
    """

    def __init__(self, wanted: Wanted, page_count: int, after: tuple[int, int] | None = None):
        self.wanted = wanted
        self.page_count = page_count
        self.after = after
        start = after[0] if after is not None else 0
        # The page of the place found before is looked at again at the end,
        # for what comes before it there.
        self._order = (
            [(start + step) % page_count for step in range(page_count)] if page_count else []
        )
        if after is not None and page_count:
            self._order.append(start)
        self._next = 0
        self._first_lap = True
        self.found: Place | None = None
        self.best_other: Place | None = None

    @property
    def done(self) -> bool:
        return self.found is not None or self._next >= len(self._order)

    def next_page(self) -> int:
        return self._order[self._next]

    def take(self, text: PageText | None) -> None:
        """The letters of the next page (None if it could not be read)."""
        index = self._next
        page = self._order[index]
        self._next += 1
        if text is None:
            return
        for place in places_in_page(text, self.wanted, page):
            if not self._in_turn(index, place):
                continue
            if place.rank == HEADING:
                self.found = place
                return
            if self.best_other is None or place.rank > self.best_other.rank:
                self.best_other = place

    def _in_turn(self, index: int, place: Place) -> bool:
        """On the page of the place found before: after it the first time,
        before it (or it again) on the last look."""
        if self.after is None or place.page != self.after[0]:
            return True
        if index == 0:
            return place.letter > self.after[1]
        return place.letter <= self.after[1]

    @property
    def answer(self) -> Place | None:
        return self.found or self.best_other


_HEADING_START = re.compile(
    r"^(?:articulo|art\.|capitulo|titulo|libro|seccion|subseccion|disposicion|anexo|tema|"
    r"parte|bloque|leccion|unidad|\d+(?:\.\d+)*(?:\.|\)|\s))"
)
LONGEST_TITLE = 70


def heading_near(text: PageText, top: float, bottom: float) -> str:
    """The first heading of a page between two heights ("Artículo 14.
    Igualdad…"), to name a bookmark put there; empty if there is none."""
    for _start, line, rect in lines_of(text):
        if rect[3] < top or rect[1] > bottom:
            continue
        clean = " ".join(line.split())
        if rank_of(clean) == HEADING and _HEADING_START.match(_simple(clean)):
            if len(clean) > LONGEST_TITLE:
                clean = clean[: LONGEST_TITLE - 1].rstrip() + "…"
            return clean
    return ""
