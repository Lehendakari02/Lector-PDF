"""Correcting the original text of a document («Corregir texto», task 6.1).

A PDF does not keep lines that flow like a word processor: it keeps letters
put at exact places, each with its font. A correction is made the way
Acrobat's «Editar texto» does it on one line:

1. The letters of the line are read with their font, size, colour and place.
2. Only the letters chosen are taken out of the page. What is drawn, the
   pictures, notes, links and the rest of the text stay as they are.
3. The new text is written in their place **with the font of the document
   itself**, when it has every letter needed (fonts are usually kept in a PDF
   with only the letters that are used, so a letter is taken from it only if
   the document shows it somewhere). The rest of the line moves so that
   nothing overlaps, and a justified line keeps its right edge: the gaps
   between its words grow or shrink a little, as in Word.
4. A letter that font lacks is written with the same font installed in the
   computer (Windows keeps Arial, Times New Roman, Calibri, Cambria…) or,
   failing that, with the most similar standard one. ``look`` tells which.

What is written is ordinary PDF text: it is found, selected and copied like
the rest, here and in any other program.

Until the document is closed it can be undone: the order keeps a copy of the
page as it was (as covering data does) and undoing puts it back.

Selections are given as seen on the page (turned if the page is turned),
like everything else the window sends; here they are turned back to the
page's own coordinates.
"""

import contextlib
import os
import re
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from statistics import median

from app.core import pdf_content
from app.core.commands import CommandError, register_reader
from app.core.page_orders import MAX_JOURNAL_COPY, DeletePages, copy_of_pages, put_back_pages

Box = tuple[float, float, float, float]

# Why a correction cannot be made: the start of the CommandError message
# (the window says each one in words).
NOT_THERE = "text_edit:not_there"  # the text chosen is not on the page (any more)
NOT_ONE_LINE = "text_edit:not_one_line"
SCANNED = "text_edit:scanned"  # letters recognised in a picture: nothing to change
NOT_LEVEL = "text_edit:not_level"  # text written slanting or upwards
TOO_LONG = "text_edit:too_long"  # the new text does not fit in the line
NO_LETTER = "text_edit:no_letter"  # a letter no font at hand has
CROWDED = "text_edit:crowded"  # letters of other lines lie on top of these

# Kinds of letter in PyMuPDF's text trace.
FILL, STROKE, INVISIBLE = 0, 1, 3
# Bits of a span's flags.
ITALIC, SERIF, MONO, BOLD = 2, 4, 8, 16

LOOK_SAME = ""  # the new text is written with the font of the document

# Ways a line may grow, shrink or be squeezed to take a longer text.
TIGHTEST_GAP = 0.5  # a gap between words can shrink to half of the usual one
LOOSEST_GAP = 3.0  # and grow to three times it, to keep a justified edge
NARROWEST = 0.93  # the new letters can be made this much narrower at most (more shows)

LEFT, JUSTIFIED, CENTRED = "left", "justified", "centred"
WORD_GAP = 0.2  # a gap wider than this (in font sizes) separates two words

RESOURCE = "LPdfF"  # name of the fonts this program adds to a page


@dataclass(frozen=True)
class ChangeText:
    """Write ``text`` in place of the text ``old`` chosen in ``boxes`` of a
    page (one line). ``copy`` keeps the page as it was, to undo it;
    ``look`` says which font the new letters had to borrow ("" if none)."""

    page: int
    boxes: tuple[Box, ...]
    old: str
    text: str  # what it says afterwards
    copy: DeletePages | None = None
    look: str = LOOK_SAME

    text_change = True  # the letters of this page are different afterwards

    def pages(self) -> list[int]:
        return [self.page]

    def prepared(self, doc) -> "ChangeText":
        """The same order, checked against the page (it fails here, before
        anything is touched, when it cannot be done) and with a copy of the
        page as it is now."""
        if not 0 <= self.page < doc.page_count:
            raise CommandError(f"{NOT_THERE}: there is no page {self.page + 1}")
        plan = _plan(doc, self.page, self.boxes, self.old, self.text)
        return replace(self, copy=copy_of_pages(doc, [self.page]), look=plan.look)

    def apply(self, doc) -> list[int]:
        if not 0 <= self.page < doc.page_count:
            raise CommandError(f"{NOT_THERE}: there is no page {self.page + 1}")
        plan = _plan(doc, self.page, self.boxes, self.old, self.text)
        try:
            _carry_out(doc, plan)
        except CommandError:
            self._put_back(doc)
            raise
        except Exception as error:  # PyMuPDF raises several unrelated error types
            self._put_back(doc)
            raise CommandError(f"cannot change the text: {error}") from error
        return [self.page]

    def _put_back(self, doc) -> None:
        if self.copy is not None and self.copy.kept:
            with contextlib.suppress(CommandError):
                put_back_pages(doc, self.copy)

    def undo(self, doc) -> list[int]:
        return put_back_pages(doc, self.copy)

    def to_dict(self) -> dict:
        copy = self.copy.to_dict() if self.copy is not None else None
        if copy is not None and len(self.copy.kept) > MAX_JOURNAL_COPY:
            copy["kept"] = ""
        return {
            "what": "change_text",
            "page": self.page,
            "boxes": [list(box) for box in self.boxes],
            "old": self.old,
            "new": self.text,
            "copy": copy,
            "look": self.look,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeText":
        copy = data.get("copy")
        return cls(
            int(data["page"]),
            tuple(tuple(float(v) for v in box) for box in data["boxes"]),
            str(data["old"]),
            str(data["new"]),
            DeletePages.from_dict(copy) if copy else None,
            str(data.get("look") or ""),
        )


def change_text(page: int, boxes, old: str, new: str) -> ChangeText:
    """Write ``new`` instead of the text ``old`` that lies in ``boxes``
    ((x0, y0, x1, y1), … as seen on the page): the text chosen."""
    return ChangeText(
        int(page),
        tuple(tuple(float(v) for v in box) for box in boxes),
        old,
        _clean(new),
    )


def _clean(text: str) -> str:
    """One line of text: line breaks and tabs become spaces, ends trimmed."""
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip()


def _same_letters(one: str, other: str) -> bool:
    def plain(text: str) -> str:
        return "".join(unicodedata.normalize("NFKC", text).split())

    return plain(one) == plain(other)


# ---- fonts of the document ----------------------------------------------------


@dataclass
class _Font:
    """A font of the document, as far as writing with it again goes."""

    xref: int
    name: str  # without the "ABCDEF+" of a font kept with only some letters
    two_bytes: bool  # codes of two bytes (Identity-H), or of one
    gid_codes: bool  # the code of a letter is the number of its drawing
    to_code: dict[str, bytes]  # letter → code
    widths: dict[int, float]  # code (as a number) → width, in 1/1000 of the size
    default_width: float
    # Letters this font is seen drawing in the document, with their code:
    # only those are sure to be in a font kept with only some letters.
    seen: dict[str, bytes] = field(default_factory=dict)
    # The whole font is there (kept whole in the file, or one every program
    # has): any letter of its encoding can be written.
    complete: bool = False
    from_code: dict[bytes, str] = field(default_factory=dict)  # what each code says

    def code_for_new(self, letter: str) -> bytes | None:
        """The code to write a new ``letter`` with this font, if it has it."""
        if letter in self.seen:
            return self.seen[letter]
        if self.complete:
            code = self.to_code.get(letter)
            if code is not None and self.width(code) > 0:
                return code
        return None

    def code(self, letter: str, gid: int | None = None) -> bytes | None:
        if gid is not None and self.gid_codes and gid > 0:
            return gid.to_bytes(2, "big")
        return self.to_code.get(letter)

    def width(self, code: bytes) -> float:
        return self.widths.get(int.from_bytes(code, "big"), self.default_width)


def _plain_name(name: str) -> str:
    name = re.sub(r"^[A-Z]{6}\+", "", name.lstrip("/"))
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _value(doc, xref: int, key: str) -> tuple[str, str]:
    """The value of a key, following it when it points to another object."""
    kind, value = doc.xref_get_key(xref, key)
    if kind == "xref":
        target = int(value.split()[0])
        return _object_kind(doc.xref_object(target, compressed=True)), doc.xref_object(
            target, compressed=True
        )
    return kind, value


def _object_kind(text: str) -> str:
    text = text.strip()
    if text.startswith("["):
        return "array"
    if text.startswith("<<"):
        return "dict"
    return "other"


def _ref(value: str) -> int | None:
    found = re.match(r"\s*\[?\s*(\d+)\s+0\s+R", value)
    return int(found.group(1)) if found else None


_TOKEN = re.compile(r"\[|\]|[-+]?(?:\d+\.?\d*|\.\d+)")


def _array(text: str) -> list:
    """A PDF array of numbers (maybe with arrays inside) as Python lists."""
    stack: list[list] = [[]]
    for token in _TOKEN.findall(text):
        if token == "[":
            stack.append([])
        elif token == "]":
            if len(stack) > 1:
                done = stack.pop()
                stack[-1].append(done)
        else:
            stack[-1].append(float(token))
    while len(stack) > 1:
        done = stack.pop()
        stack[-1].append(done)
    result = stack[0]
    return result[0] if len(result) == 1 and isinstance(result[0], list) else result


def _cid_widths(text: str) -> dict[int, float]:
    """The /W array of a font with two-byte codes."""
    widths: dict[int, float] = {}
    items = _array(text)
    at = 0
    while at < len(items):
        first = items[at]
        if at + 1 < len(items) and isinstance(items[at + 1], list):
            for step, width in enumerate(items[at + 1]):
                if not isinstance(width, list):
                    widths[int(first) + step] = width
            at += 2
        elif at + 2 < len(items):
            last, width = items[at + 1], items[at + 2]
            numbers = not isinstance(last, list) and not isinstance(width, list)
            if numbers and int(last) - int(first) <= 0xFFFF:
                for code in range(int(first), int(last) + 1):
                    widths[code] = width
            at += 3
        else:
            break
    return widths


def _hex_text(hexdigits: str) -> str:
    raw = bytes.fromhex(hexdigits if len(hexdigits) % 2 == 0 else hexdigits + "0")
    return raw.decode("utf-16-be", errors="ignore")


def _to_unicode(data: bytes) -> dict[bytes, str]:
    """Code → text, from a ToUnicode CMap."""
    text = data.decode("latin-1")
    found: dict[bytes, str] = {}
    for section in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for code, letters in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", section):
            found[bytes.fromhex(code)] = _hex_text(letters)
    for section in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        pattern = r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])"
        for low, high, target in re.findall(pattern, section):
            size = len(low) // 2
            first, last = int(low, 16), int(high, 16)
            if last < first or last - first > 0xFFFF:
                continue
            if target.startswith("["):
                for step, letters in enumerate(re.findall(r"<([0-9A-Fa-f]*)>", target)):
                    if first + step <= last:
                        found[(first + step).to_bytes(size, "big")] = _hex_text(letters)
            else:
                start = _hex_text(target[1:-1])
                if not start:
                    continue
                for step in range(last - first + 1):
                    letters = start[:-1] + chr(ord(start[-1]) + step)
                    found[(first + step).to_bytes(size, "big")] = letters
    return found


# The usual meaning of each code in the encodings of simple fonts.
_STANDARD_DIFFERENT = {0x27: "’", 0x60: "‘"}


def _encoding_letters(doc, xref: int) -> dict[int, str]:
    """Code → letter for a font of one-byte codes, from its /Encoding."""
    import pymupdf

    base, differences = "", ""
    kind, value = _value(doc, xref, "Encoding")
    if kind == "name":
        base = value
    elif kind == "dict":
        base_found = re.search(r"/BaseEncoding\s*/(\w+)", value)
        base = "/" + base_found.group(1) if base_found else ""
        diff_found = re.search(r"/Differences\s*\[(.*?)\]", value, re.S)
        differences = diff_found.group(1) if diff_found else ""
    letters: dict[int, str] = {}
    if base in ("/WinAnsiEncoding", "", "/StandardEncoding"):
        for code in range(32, 256):
            try:
                letters[code] = bytes([code]).decode("cp1252")
            except UnicodeDecodeError:
                continue
        if base != "/WinAnsiEncoding":  # standard: only plain ASCII is the same
            letters = {code: letter for code, letter in letters.items() if code < 127}
            letters.update(_STANDARD_DIFFERENT)
    elif base == "/MacRomanEncoding":
        for code in range(32, 256):
            letters[code] = bytes([code]).decode("mac_roman")
    code = 0
    for token in re.findall(r"/[^\s/\[\]]+|\d+", differences):
        if token.startswith("/"):
            letter = pymupdf.glyph_name_to_unicode(token[1:])
            if letter and letter > 0:
                letters[code] = chr(letter)
            else:
                letters.pop(code, None)
            code += 1
        else:
            code = int(token)
    return letters


def _base14_widths(name: str) -> dict[int, float]:
    """Widths of a standard font kept outside the PDF, by WinAnsi code."""
    import pymupdf

    plain = _plain_name(name)
    font = "helv"
    if "times" in plain:
        font = "tiro"
    elif "courier" in plain:
        font = "cour"
    bold = "bold" in plain
    italic = "italic" in plain or "oblique" in plain
    font = {
        ("helv", True, False): "hebo",
        ("helv", False, True): "heit",
        ("helv", True, True): "hebi",
        ("tiro", True, False): "tibo",
        ("tiro", False, True): "tiit",
        ("tiro", True, True): "tibi",
        ("cour", True, False): "cobo",
        ("cour", False, True): "coit",
        ("cour", True, True): "cobi",
    }.get((font, bold, italic), font)
    shape = pymupdf.Font(font)
    widths = {}
    for code in range(32, 256):
        try:
            letter = bytes([code]).decode("cp1252")
        except UnicodeDecodeError:
            continue
        widths[code] = shape.glyph_advance(ord(letter)) * 1000
    return widths


def _load_font(doc, xref: int) -> _Font | None:
    """What it takes to write again with a font of the document, or None if
    this program cannot (fonts drawn by the document itself, other code
    systems…)."""
    kind, subtype = doc.xref_get_key(xref, "Subtype")
    _kind, name = doc.xref_get_key(xref, "BaseFont")
    name = re.sub(r"^/", "", name)
    in_part = bool(re.match(r"^[A-Z]{6}\+", name))  # kept with only some letters
    name = re.sub(r"^[A-Z]{6}\+", "", name)
    unicode_ref = _ref(doc.xref_get_key(xref, "ToUnicode")[1])
    mapping: dict[bytes, str] = {}
    if unicode_ref is not None:
        try:
            mapping = _to_unicode(doc.xref_stream(unicode_ref) or b"")
        except Exception:
            mapping = {}
    if subtype == "/Type0":
        if doc.xref_get_key(xref, "Encoding") != ("name", "/Identity-H"):
            return None
        descendant = _ref(doc.xref_get_key(xref, "DescendantFonts")[1])
        if descendant is None:
            return None
        widths = _cid_widths(_value(doc, descendant, "W")[1])
        default = doc.xref_get_key(descendant, "DW")
        default_width = float(default[1]) if default[0] in ("int", "float") else 1000.0
        gid_map = doc.xref_get_key(descendant, "CIDToGIDMap")
        cid_type = doc.xref_get_key(descendant, "Subtype")[1]
        gid_codes = cid_type == "/CIDFontType2" and gid_map[0] in ("null", "name")
        if gid_map[0] == "name" and gid_map[1] != "/Identity":
            gid_codes = False
        to_code = _invert({code: text for code, text in mapping.items() if len(code) == 2})
        two = {code: text for code, text in mapping.items() if len(code) == 2}
        return _Font(
            xref,
            name,
            True,
            gid_codes,
            to_code,
            widths,
            default_width,
            complete=not in_part,
            from_code=two,
        )
    if subtype not in ("/TrueType", "/Type1", "/MMType1"):
        return None  # Type3 fonts are drawn by the document: not written again
    has_encoding = doc.xref_get_key(xref, "Encoding")[0] != "null"
    descriptor = _ref(doc.xref_get_key(xref, "FontDescriptor")[1])
    symbolic = False
    if descriptor is not None:
        flags = doc.xref_get_key(descriptor, "Flags")
        symbolic = flags[0] == "int" and bool(int(flags[1]) & 4)
    if not has_encoding and not mapping and symbolic:
        return None  # its codes mean what the font file says: unknown here
    by_code = _encoding_letters(doc, xref)
    for code, text in mapping.items():
        if len(code) == 1 and len(text) == 1:
            by_code[code[0]] = text
    first = doc.xref_get_key(xref, "FirstChar")
    widths_text = _value(doc, xref, "Widths")[1]
    widths: dict[int, float] = {}
    if first[0] == "int" and widths_text.strip().startswith("["):
        for step, width in enumerate(_array(widths_text)):
            if not isinstance(width, list):
                widths[int(first[1]) + step] = width
    elif not widths_text or widths_text == "null":
        widths = _base14_widths(name)
    missing = 0.0
    if descriptor is not None:
        found = doc.xref_get_key(descriptor, "MissingWidth")
        if found[0] in ("int", "float"):
            missing = float(found[1])
    to_code = _invert({bytes([code]): letter for code, letter in by_code.items()})
    embedded = descriptor is not None and any(
        doc.xref_get_key(descriptor, key)[0] != "null"
        for key in ("FontFile", "FontFile2", "FontFile3")
    )
    complete = not embedded or not in_part
    return _Font(xref, name, False, False, to_code, widths, missing, complete=complete)


def _invert(mapping: dict[bytes, str]) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for code in sorted(mapping):
        letter = mapping[code]
        if letter and letter not in found:
            found[letter] = code
    return found


# ---- the letters of a page --------------------------------------------------


@dataclass
class _Glyph:
    letter: str
    gid: int
    x: float  # where its baseline starts, on the page not turned
    y: float
    box: tuple[float, float, float, float]
    span: int  # which span of the text trace it belongs to
    font: _Font | None = None
    code: bytes | None = None
    width: float = 0.0  # how far it moves the pen, in points
    style: tuple = ()  # what is needed to write it again (see ``_style``)

    @property
    def rider(self) -> bool:
        """The second letter of a ligature ("fi" drawn as one): it is written
        with the first one."""
        return self.gid < 0

    @property
    def end(self) -> float:
        return self.x + self.width

    @property
    def space(self) -> bool:
        return self.letter.isspace()


@dataclass
class _Span:
    font_name: str
    size: float  # horizontal size, in points (with any squeezing)
    height: float  # vertical size, in points
    level: bool  # written from left to right, not turned
    kind: int
    color: tuple
    colorspace: int
    opacity: float
    linewidth: float
    flags: int


def _read_trace(page) -> tuple[list[_Span], list[_Glyph]]:
    spans, glyphs = [], []
    for number, span in enumerate(page.get_texttrace()):
        direction = span.get("dir", (1.0, 0.0))
        box = span.get("bbox") or (0, 0, 0, 0)
        spans.append(
            _Span(
                font_name=span.get("font", ""),
                size=float(span.get("size") or 0),
                # The box of a letter is as tall as the vertical size (the
                # box of a span may cover several lines).
                height=_letter_height(span.get("chars") or (), box),
                level=abs(direction[0] - 1) < 1e-3 and abs(direction[1]) < 1e-3,
                kind=int(span.get("type", FILL)),
                color=tuple(span.get("color") or (0.0,)),
                colorspace=int(span.get("colorspace") or 1),
                opacity=float(span.get("opacity", 1.0) if span.get("opacity") is not None else 1),
                linewidth=float(span.get("linewidth") or 0),
                flags=int(span.get("flags") or 0),
            )
        )
        for ucs, gid, origin, char_box in span.get("chars", ()):
            glyphs.append(
                _Glyph(chr(ucs) if ucs > 0 else "", gid, origin[0], origin[1], char_box, number)
            )
    return spans, glyphs


def _letter_height(chars, span_box) -> float:
    heights = sorted(char[3][3] - char[3][1] for char in chars if len(char) > 3)
    if heights:
        return float(heights[len(heights) // 2])
    return float(span_box[3] - span_box[1])


def _middle(glyph: _Glyph, span: _Span) -> tuple[float, float]:
    """A point well inside the letter: halfway across, at half its x-height."""
    x0, _y0, x1, _y1 = glyph.box
    return ((x0 + x1) / 2, glyph.y - 0.3 * max(span.height, 0.1))


@dataclass
class _Plan:
    page: int
    remove: list[_Glyph]  # letters taken out
    write: list[tuple[_Glyph, float, tuple]]  # letters written: (glyph, x, style)
    keep: list[_Glyph]  # every other letter of the page, to check nothing else went
    points: list[tuple[float, float]]  # where to take the letters out
    borrowed: dict = field(default_factory=dict)  # style key → font to add to the page
    look: str = LOOK_SAME
    new: str = ""
    baseline: float = 0.0
    before: _Glyph | None = None  # the letter drawn just before those taken out


def _plan(doc, number: int, boxes, old: str, new: str) -> _Plan:
    import pymupdf

    page = doc[number]
    new = _clean(new)
    rects = [
        (pymupdf.Rect(box) * page.derotation_matrix).normalize() + (-0.5, -0.5, 0.5, 0.5)
        for box in boxes
    ]
    if not rects:
        raise CommandError(f"{NOT_THERE}: nothing chosen")
    spans, glyphs = _read_trace(page)

    def chosen(glyph: _Glyph) -> bool:
        point = pymupdf.Point(_middle(glyph, spans[glyph.span]))
        return any(point in rect for rect in rects)

    picked = [glyph for glyph in glyphs if chosen(glyph) and glyph.letter]
    if any(spans[glyph.span].kind == INVISIBLE for glyph in picked):
        raise CommandError(f"{SCANNED}: these letters were recognised in a picture")
    picked = [glyph for glyph in picked if spans[glyph.span].kind != INVISIBLE]
    if not any(not glyph.space for glyph in picked):
        raise CommandError(f"{NOT_THERE}: there are no letters there")
    if any(not spans[glyph.span].level for glyph in picked):
        raise CommandError(f"{NOT_LEVEL}: the text is not written level")
    first = min((glyph for glyph in picked if not glyph.space), key=lambda glyph: glyph.x)
    height = max(spans[first.span].height, 1.0)
    if any(abs(glyph.y - first.y) > 0.3 * height for glyph in picked):
        raise CommandError(f"{NOT_ONE_LINE}: the text is in more than one line")

    line_box, block_box, align = _line_around(page, first, spans[first.span])
    line = [
        glyph
        for glyph in glyphs
        if glyph.letter
        and spans[glyph.span].level
        and spans[glyph.span].kind != INVISIBLE
        and abs(glyph.y - first.y) <= 0.3 * height
        and line_box[0] - 1 <= glyph.x <= line_box[2] + 1
    ]
    line.sort(key=lambda glyph: glyph.x)
    picked_ids = {id(glyph) for glyph in picked}
    places = [at for at, glyph in enumerate(line) if id(glyph) in picked_ids]
    if not places:
        raise CommandError(f"{NOT_THERE}: the text is not in that line")
    start, stop = places[0], places[-1] + 1
    while start < stop and line[start].space:
        start += 1
    while stop > start and line[stop - 1].space:
        stop -= 1
    if any(id(glyph) not in picked_ids for glyph in line[start:stop] if not glyph.space):
        raise CommandError(f"{NOT_ONE_LINE}: the letters chosen are not together")
    if old and not _same_letters(old, "".join(glyph.letter for glyph in line[start:stop])):
        raise CommandError(f"{NOT_THERE}: the text there is different")

    fonts = _PageFonts(doc, page, spans, glyphs)
    for at, glyph in enumerate(line):
        riders = ""
        following = at + 1
        while following < len(line) and line[following].rider:
            riders += line[following].letter
            following += 1
        fonts.dress(glyph, riders)
    for at, glyph in enumerate(line):  # a ligature that cannot be written again
        if glyph.rider and at and not line[at - 1].style:
            glyph.style = ()
    word_gap = _usual_word_gap(line, spans)
    if align == JUSTIFIED and not _stretched(line, spans, word_gap):
        align = LEFT

    if not new:  # taking a word away takes one gap with it
        while stop < len(line) and line[stop].space:
            stop += 1
        if stop == len(line):  # the last word: the gap before it goes instead
            while start > 0 and line[start - 1].space:
                start -= 1

    model = (
        line[start]
        if line[start].style
        else next((glyph for glyph in line[start:stop] if glyph.style), None)
    )
    model_span = spans[(model or line[start]).span]
    written, look, borrowed = _new_letters(new, model, model_span, fonts, word_gap)

    # The stretch of the line that is written again: from the chosen letters
    # (or from the start of a justified or centred line) to the end, or to
    # the first letter that cannot be written again, which stays where it is.
    end = stop
    while end < len(line) and line[end].style:
        end += 1
    whole = (
        align in (JUSTIFIED, CENTRED)
        and end == len(line)
        and all(glyph.style for glyph in line[:start])
    )
    begin = 0 if whole else start
    items: list[tuple[_Glyph, float, tuple, bool]] = []  # glyph, x, style, word gap before
    for glyph in line[begin:start]:
        items.append((glyph, glyph.x, glyph.style, False))
    for glyph, _style in written:
        glyph.y = first.y
    pen = line[start].x
    gap_next = False
    new_items = []
    for glyph, style in written:
        if glyph.space:
            pen += word_gap
            gap_next = True
            continue
        new_items.append((glyph, pen, style, gap_next))
        pen += glyph.width
        gap_next = False
    if stop < len(line):
        if new:
            before = line[stop - 1]
            after = max(line[stop].x - (before.end if before.width else before.box[2]), 0.0)
            shift = pen + after - line[stop].x
        else:
            shift = line[start].x - line[stop].x
    else:
        shift = 0.0
    items += new_items
    for glyph in line[stop:end]:
        items.append((glyph, glyph.x + shift, glyph.style, False))
    items = _mark_gaps(items, height)

    letters = [glyph for glyph in line[:end] if not glyph.space and not glyph.rider]
    old_end = max((glyph.end for glyph in letters), default=line[0].x)
    new_end = _end(items, line[start].x)
    if end < len(line):
        limit = old_end  # what follows stays: the stretch must end before it
        target = None
    elif whole and align == JUSTIFIED:
        limit = old_end
        target = old_end
    elif whole:  # centred: it grows or shrinks by half on each side
        half = (new_end - old_end) / 2
        left = min(glyph.x for glyph in line)
        half = min(half, left - _left_margin(page, line_box))
        items = [(glyph, x - half, style, gap) for glyph, x, style, gap in items]
        new_end -= half
        limit = _right_limit(page, glyphs, line, spans, line_box, block_box, word_gap)
        target = None
    else:
        limit = _right_limit(page, glyphs, line, spans, line_box, block_box, word_gap)
        target = None
    items = _fit(items, new_end, limit, target, word_gap, new_items, begin == start)

    removed = line[begin:end]
    removed_ids = _ids(removed)
    keep = [glyph for glyph in glyphs if id(glyph) not in removed_ids and glyph.letter]
    points = _take_out_points(removed, keep, spans)
    write = [(glyph, x, style) for glyph, x, style, _gap in items]
    order = {id(glyph): at for at, glyph in enumerate(glyphs)}
    first_out = min(order[id(glyph)] for glyph in removed)
    before = next(
        (
            glyph
            for glyph in reversed(glyphs[:first_out])
            if id(glyph) not in removed_ids and glyph.letter and not glyph.rider
        ),
        None,
    )
    return _Plan(number, removed, write, keep, points, borrowed, look, new, first.y, before)


def _ids(glyphs) -> set[int]:
    return {id(glyph) for glyph in glyphs}


def _mark_gaps(items, height):
    """Mark the gaps between words in the stretch written again (needed to
    widen or narrow them): after a space, or a wide jump between two letters."""
    marked = []
    previous_end = None
    after_space = False
    for glyph, x, style, gap in items:
        if glyph.rider:
            marked.append((glyph, x, style, False))
            continue
        if glyph.space:
            marked.append((glyph, x, style, False))
            after_space = True
            continue
        jump = previous_end is not None and x - previous_end > WORD_GAP * height
        marked.append((glyph, x, style, gap or after_space or jump))
        after_space = False
        previous_end = x + glyph.width
    return marked


def _end(items, default: float) -> float:
    ends = [x + glyph.width for glyph, x, _style, _gap in items if not glyph.space]
    return max(ends) if ends else default


def _fit(items, end, limit, target, word_gap, new_items, keeps_start):
    """Make the stretch end at ``target`` (a justified line) or not later
    than ``limit``: first the gaps between words, then the new letters a
    little narrower. Raises TOO_LONG if it cannot fit."""
    gaps = sum(1 for _glyph, _x, _style, gap in items if gap)
    tolerance = 0.25
    if target is not None and gaps:
        each = (target - end) / gaps
        if -TIGHTEST_GAP * word_gap <= each <= (LOOSEST_GAP - 1) * word_gap:
            return _spread(items, each)
        if each > 0:  # too loose to keep the edge: the line ends earlier
            return items
    if end <= limit + tolerance:
        return items
    if gaps:
        each = max((limit - end) / gaps, -TIGHTEST_GAP * word_gap)
        items = _spread(items, each)
        end += each * gaps
        if end <= limit + tolerance:
            return items
    new_width = sum(glyph.width for glyph, *_rest in new_items if not glyph.space)
    if new_width > 0:
        factor = 1 - (end - limit) / new_width
        if factor >= NARROWEST:
            return _narrow(items, new_items, factor)
    raise CommandError(f"{TOO_LONG}: the new text does not fit in the line")


def _spread(items, each):
    out, count = [], 0
    for glyph, x, style, gap in items:
        if gap:
            count += 1
        out.append((glyph, x + count * each, style, gap))
    return out


def _narrow(items, new_items, factor):
    """Make the new letters narrower by ``factor``; what follows them moves
    back as much."""
    new_ids = _ids(glyph for glyph, *_rest in new_items)
    out, saved = [], 0.0
    origin = None
    for glyph, x, style, gap in items:
        if id(glyph) in new_ids:
            if origin is None:
                origin = x
            moved = origin + (x - origin) * factor
            saved = (x + glyph.width) - (moved + glyph.width * factor)
            glyph.width *= factor
            style = style[:-1] + (style[-1] * factor,)
            out.append((glyph, moved, style, gap))
        else:
            out.append((glyph, x - saved, style, gap))
    return out


def _usual_word_gap(line: list[_Glyph], spans: list[_Span]) -> float:
    """The usual room between two words of the line, in points."""
    gaps = []
    word_end = None
    for glyph in line:
        if glyph.space or glyph.rider:
            continue
        height = max(spans[glyph.span].height, 1.0)
        if word_end is not None and glyph.x - word_end > WORD_GAP * height:
            gaps.append(glyph.x - word_end)
        word_end = glyph.end if glyph.width else glyph.box[2]
    if gaps:
        return median(gaps)
    for glyph in line:
        if glyph.space and glyph.width:
            return glyph.width
    return 0.25 * max(spans[line[0].span].height, 1.0)


def _line_around(page, glyph: _Glyph, span: _Span):
    """The line and the paragraph this letter is in (as PyMuPDF groups them),
    and how the line is aligned: justified (it reaches the right edge of a
    paragraph that goes on after it), centred (a title in the middle of the
    page, or a paragraph of lines centred on the same middle) or left."""
    x = glyph.x + 0.1
    for block in page.get_text("dict")["blocks"]:
        lines = block.get("lines", ())
        for at, line in enumerate(lines):
            x0, _y0, x1, _y1 = line["bbox"]
            on_it = any(
                abs(part["origin"][1] - glyph.y) <= 0.3 * max(span.height, 1.0)
                for part in line["spans"]
            )
            if not (on_it and x0 - 0.5 <= x <= x1 + 0.5):
                continue
            block_box = tuple(block["bbox"])
            align = LEFT
            if (
                len(lines) >= 2
                and at < len(lines) - 1
                and abs(x1 - block_box[2]) <= max(1.0, 0.1 * span.height)
            ):
                align = JUSTIFIED
            elif _centred(page, lines, line):
                align = CENTRED
            return tuple(line["bbox"]), block_box, align
    return (*glyph.box,), (*glyph.box,), LEFT


def _stretched(line: list[_Glyph], spans, word_gap: float) -> bool:
    """Whether the gaps between the words of a line are wider or narrower
    than a plain space of its font: the mark of a justified line (a line
    that only happens to be as long as the others is not)."""
    for glyph in line:
        font = glyph.font
        if font is None:
            continue
        code = font.code_for_new(" ")
        if code is None:
            return True  # nothing to compare with
        natural = font.width(code) * spans[glyph.span].size / 1000
        return natural <= 0 or abs(word_gap - natural) > 0.05 * natural
    return True


def _centred(page, lines, line) -> bool:
    middle = (line["bbox"][0] + line["bbox"][2]) / 2
    if len(lines) == 1:
        width = page.cropbox.width
        return abs(middle - width / 2) <= 2.5 and line["bbox"][0] > 0.15 * width
    middles = [(other["bbox"][0] + other["bbox"][2]) / 2 for other in lines]
    widths = [other["bbox"][2] - other["bbox"][0] for other in lines]
    return max(middles) - min(middles) <= 2.0 and max(widths) - min(widths) > 5.0


def _left_margin(page, line_box) -> float:
    lefts = [
        line["bbox"][0]
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", ())
    ]
    return min(min(lefts, default=line_box[0]), line_box[0])


def _right_limit(page, glyphs, line, spans, line_box, block_box, word_gap) -> float:
    """How far right a line that is not justified can grow: to the right
    margin of the page (as wide as the left one), never over other text on
    its right (another column, a number at the end…)."""
    lefts = [
        line_["bbox"][0]
        for block in page.get_text("dict")["blocks"]
        for line_ in block.get("lines", ())
    ]
    left = min(lefts, default=line_box[0])
    limit = max(page.cropbox.width - left, line_box[2], block_box[2])
    first = line[0]
    height = max(spans[first.span].height, 1.0)
    in_line = _ids(line)
    for glyph in glyphs:
        if (
            id(glyph) not in in_line
            and glyph.letter
            and not glyph.space
            and glyph.box[0] >= line_box[2] - 0.5
            and first.y - 0.8 * height <= glyph.y <= first.y + 0.3 * height
        ):
            limit = min(limit, glyph.box[0] - word_gap)
    return limit


def _take_out_points(removed, keep, spans) -> list[tuple[float, float]]:
    """A point inside each letter to take out that is not inside any letter
    that stays (MuPDF takes out every letter whose box touches the area)."""
    points = []
    for glyph in removed:
        if not glyph.letter or glyph.rider:
            continue
        span = spans[glyph.span]
        x0, y0, x1, y1 = glyph.box
        if x1 - x0 < 0.2:  # an empty box: nothing to take out there
            continue
        near = [
            other
            for other in keep
            if other.box[0] <= x1
            and other.box[2] >= x0
            and other.box[1] <= y1
            and other.box[3] >= y0
        ]
        found = None
        for down in (0.3, 0.15, 0.45, 0.05, 0.6):
            for across in (0.5, 0.35, 0.65, 0.2, 0.8):
                x = x0 + (x1 - x0) * across
                y = glyph.y - down * max(span.height, 0.1)
                if not any(
                    other.box[0] - 0.2 <= x <= other.box[2] + 0.2
                    and other.box[1] - 0.2 <= y <= other.box[3] + 0.2
                    for other in near
                ):
                    found = (x, y)
                    break
            if found:
                break
        if found is None:
            raise CommandError(f"{CROWDED}: other letters lie on top of these")
        points.append(found)
    return points


class _PageFonts:
    """Which font of the document draws each span of the page, and which of
    its letters it is seen drawing."""

    def __init__(self, doc, page, spans, glyphs) -> None:
        self.doc = doc
        self.page = page
        self.spans = spans
        self.glyphs = glyphs
        self.fonts: dict[int, _Font | None] = {}
        self.by_span: dict[int, _Font | None] = {}
        self.resources: dict[int, str] = {}
        self.page_fonts = page.get_fonts(full=True)
        self._other_pages_read = False
        for xref, _ext, _type, _base, refname, _enc, referencer in self.page_fonts:
            if referencer == 0 and refname:
                self.resources.setdefault(xref, refname)

    def font(self, xref: int) -> _Font | None:
        if xref not in self.fonts:
            try:
                self.fonts[xref] = _load_font(self.doc, xref)
            except Exception:
                self.fonts[xref] = None
        return self.fonts[xref]

    def of_span(self, number: int) -> _Font | None:
        if number not in self.by_span:
            self.by_span[number] = self._find(number)
        return self.by_span[number]

    def _find(self, number: int) -> _Font | None:
        span = self.spans[number]
        letters = [glyph for glyph in self.glyphs if glyph.span == number and glyph.letter]
        wanted = _plain_name(span.font_name)
        candidates = []
        for xref, _ext, _type, base, _ref_name, _enc, _referencer in self.page_fonts:
            if xref in candidates:
                continue
            plain = _plain_name(base)
            if plain == wanted or (
                wanted
                and plain
                and (plain.startswith(wanted) or wanted.startswith(plain) or plain.endswith(wanted))
            ):
                candidates.append(xref)
        best, best_score = None, -1.0
        for xref in candidates:
            font = self.font(xref)
            if font is None:
                continue
            codes = [font.code(glyph.letter, glyph.gid) for glyph in letters]
            if any(code is None for code in codes):
                continue
            if any(
                font.width(code) <= 0 and not glyph.space and not glyph.rider
                for glyph, code in zip(letters, codes, strict=True)
            ):
                continue  # a letter this font does not have: another font draws it
            if font.gid_codes and any(
                font.from_code.get(code, glyph.letter) not in (glyph.letter, "")
                and not glyph.rider
                and not font.from_code.get(code, "").startswith(glyph.letter)
                for glyph, code in zip(letters, codes, strict=True)
            ):
                continue  # its drawing of that number is another letter
            score = _width_agreement(letters, codes, font, span.size)
            if _plain_name(self.doc.xref_get_key(xref, "BaseFont")[1]) == wanted:
                score += 0.05  # the very name, when the widths say nothing
            if score > best_score:
                best, best_score = font, score
        return best

    def dress(self, glyph: _Glyph, riders: str = "") -> None:
        """Find out how to write this letter again (its style), if it can be.
        ``riders``: the letters drawn together with it (a ligature)."""
        span = self.spans[glyph.span]
        font = self.of_span(glyph.span)
        if font is None:
            return
        if glyph.rider:
            glyph.font = font
            if span.kind in (FILL, STROKE) and span.opacity >= 0.999:
                glyph.style = ("rider",)
            return
        if riders and not font.gid_codes:
            code = font.to_code.get(glyph.letter + riders)
        else:
            code = font.code(glyph.letter, glyph.gid)
        if code is None:
            return
        glyph.font, glyph.code = font, code
        glyph.width = font.width(code) * span.size / 1000
        if not riders:
            font.seen.setdefault(glyph.letter, code)
        if span.kind in (FILL, STROKE) and span.opacity >= 0.999:
            glyph.style = _style(("doc", font.xref), span, span.size)

    def learn_letters(self, font: _Font, wanted: set[str]) -> None:
        """Look for the letters ``wanted`` drawn with ``font`` in the rest of
        this page and then in the other pages that use it."""
        wanted = {letter for letter in wanted if font.code_for_new(letter) is None}
        if not wanted:
            return
        for glyph in self.glyphs:
            if glyph.letter in wanted and self.of_span(glyph.span) is font:
                code = font.code(glyph.letter, glyph.gid)
                if code is not None:
                    font.seen.setdefault(glyph.letter, code)
        if wanted <= set(font.seen) or self._other_pages_read:
            return
        self._other_pages_read = True
        doc = self.doc
        for number in range(doc.page_count):
            if wanted <= set(font.seen):
                return
            if number == self.page.number:
                continue
            other = doc[number]
            if not any(entry[0] == font.xref for entry in other.get_fonts(full=True)):
                continue
            spans, glyphs = _read_trace(other)
            reader = _PageFonts(doc, other, spans, glyphs)
            reader.fonts = self.fonts  # the same font objects
            for glyph in glyphs:
                new_letter = glyph.letter in wanted and glyph.letter not in font.seen
                if new_letter and reader.of_span(glyph.span) is font:
                    code = font.code(glyph.letter, glyph.gid)
                    if code is not None:
                        font.seen[glyph.letter] = code


def _width_agreement(letters, codes, font: _Font, size: float) -> float:
    """How well the widths of a font explain where its letters are (0 to 1)."""
    good = total = 0
    for at in range(len(letters) - 1):
        glyph, following = letters[at], letters[at + 1]
        if glyph.space or following.space:
            continue
        expected = font.width(codes[at]) * size / 1000
        if expected <= 0:
            continue
        total += 1
        if abs((following.x - glyph.x) - expected) <= max(0.05 * expected, 0.3):
            good += 1
    return good / total if total else 0.5


def _style(font_key, span: _Span, size: float) -> tuple:
    """Everything needed to write a letter: font, kind, colour, line width,
    height and horizontal size (last, so it can be narrowed)."""
    return (
        font_key,
        span.kind,
        span.colorspace,
        tuple(round(value, 4) for value in span.color),
        round(span.linewidth, 3),
        span.height,
        size,
    )


def _new_letters(new: str, model: _Glyph | None, span: _Span, fonts: _PageFonts, word_gap):
    """The letters of the new text, each with its width and style: with the
    font of the document when it has the letter, or else a borrowed one."""
    written: list[tuple[_Glyph, tuple]] = []
    borrowed: dict = {}
    look = LOOK_SAME
    font = model.font if model is not None and model.style else None
    if font is not None:
        fonts.learn_letters(font, {letter for letter in new if not letter.isspace()})
    size = span.size
    spare = None
    for letter in new:
        glyph = _Glyph(letter, 0, 0.0, 0.0, (0, 0, 0, 0), model.span if model else -1)
        if letter.isspace():
            if font is not None and " " in font.seen:
                glyph.font, glyph.code = font, font.seen[" "]
            written.append((glyph, ()))
            continue
        code = font.code_for_new(letter) if font is not None else None
        if code is not None:
            glyph.font, glyph.code = font, code
            glyph.width = font.width(glyph.code) * size / 1000
            written.append((glyph, model.style))
            continue
        if spare is None:
            spare = _spare_font(font.name if font else span.font_name, span.flags)
        code, width = spare.code(letter)
        if code is None:
            raise CommandError(f"{NO_LETTER}: no font at hand has the letter {letter!r}")
        glyph.code = code
        glyph.width = width * size / 1000
        key = ("spare", spare.key)
        borrowed[key] = spare
        written.append((glyph, _style(key, span, size)))
        look = spare.label
    return written, look, borrowed


# ---- fonts borrowed from the computer -----------------------------------------


@dataclass
class _Spare:
    """A font to write the letters the document's font does not have."""

    key: str  # file path, or the name of a standard PDF font
    label: str  # what the user is told
    buffer: bytes | None  # the font file, or None for a standard font
    shape: object  # a pymupdf.Font

    def code(self, letter: str) -> tuple[bytes | None, float]:
        if self.buffer is None:  # one-byte codes (WinAnsi)
            try:
                code = letter.encode("cp1252")
            except UnicodeEncodeError:
                return None, 0.0
            return code, self.shape.glyph_advance(ord(letter)) * 1000
        gid = self.shape.has_glyph(ord(letter))
        if not gid:
            return None, 0.0
        return gid.to_bytes(2, "big"), self.shape.glyph_advance(ord(letter)) * 1000


# Fonts made to look the same as the usual Windows ones (and the old names
# of those), so a document made with them finds the Windows one.
_SAME_AS = {
    "arimo": "arial",
    "liberationsans": "arial",
    "helvetica": "arial",
    "tinos": "timesnewroman",
    "liberationserif": "timesnewroman",
    "times": "timesnewroman",
    "timesroman": "timesnewroman",
    "cousine": "couriernew",
    "liberationmono": "couriernew",
    "courier": "couriernew",
    "carlito": "calibri",
    "caladea": "cambria",
}
_STYLE_WORDS = (
    "bolditalic",
    "boldoblique",
    "bold",
    "italic",
    "oblique",
    "regular",
    "book",
    "normal",
    "plain",
)


def _family(name: str) -> tuple[str, bool, bool]:
    """Family (plain letters), bold and italic, from a font name such as
    "ABCDEF+Arial-BoldItalicMT", "TimesNewRomanPSMT" or "Calibri,Bold"."""
    name = re.sub(r"^[A-Z]{6}\+", "", name)
    parts = re.split(r"[,\-]", name, maxsplit=1)
    family = re.sub(r"(PSMT|PS|MT)$", "", parts[0])
    style = parts[1] if len(parts) > 1 else ""
    plain = re.sub(r"[^a-z0-9]", "", family.lower())
    changed = True
    while changed:
        changed = False
        for word in _STYLE_WORDS:
            if plain.endswith(word) and len(plain) > len(word):
                plain = plain[: -len(word)]
                style += word
                changed = True
    style = style.lower()
    return (
        plain,
        "bold" in style or "black" in style or "heavy" in style,
        ("italic" in style or "oblique" in style),
    )


def font_folders() -> list[Path]:
    """Where the computer keeps its fonts."""
    folders = []
    windows = os.environ.get("WINDIR") or os.environ.get("SYSTEMROOT")
    if windows:
        folders.append(Path(windows) / "Fonts")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        folders.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    folders += [
        Path("/usr/share/fonts"),
        Path.home() / ".fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
    ]
    return folders


_installed: dict | None = None
BIGGEST_FONT_FILE = 6 * 1024 * 1024


def _installed_fonts() -> dict[tuple[str, bool, bool], Path]:
    """(family, bold, italic) → font file, for the fonts of the computer
    (read once)."""
    global _installed
    if _installed is not None:
        return _installed
    import pymupdf

    found: dict[tuple[str, bool, bool], Path] = {}
    for folder in font_folders():
        try:
            files = sorted(folder.rglob("*")) if folder.is_dir() else []
        except OSError:
            continue
        for path in files:
            if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            try:
                if path.stat().st_size > BIGGEST_FONT_FILE:
                    continue  # fonts for Chinese or Japanese: not what is looked for
            except OSError:
                continue
            try:
                shape = pymupdf.Font(fontfile=str(path))
            except Exception:
                continue
            family, bold, italic = _family(shape.name)
            found.setdefault((family, bold, italic), path)
    _installed = found
    return found


def _spare_font(name: str, flags: int) -> _Spare:
    """The font to borrow for a font of the document called ``name``: the
    same one installed in the computer, or the most similar standard one."""
    import pymupdf

    family, bold, italic = _family(name)
    bold = bold or bool(flags & BOLD)
    italic = italic or bool(flags & ITALIC)
    installed = _installed_fonts()
    for wanted in dict.fromkeys((family, _SAME_AS.get(family, family))):
        path = installed.get((wanted, bold, italic))
        if path is not None:
            try:
                data = path.read_bytes()
                shape = pymupdf.Font(fontbuffer=data)
            except Exception:
                continue
            return _Spare(str(path), shape.name, data, shape)
    if flags & MONO or family in ("couriernew", "courier", "cousine"):
        base, label = "cour", "Courier"
    elif flags & SERIF or "times" in family or "serif" in family:
        base, label = "tiro", "Times"
    else:
        base, label = "helv", "Helvetica"
    base = {
        ("helv", True, False): "hebo",
        ("helv", False, True): "heit",
        ("helv", True, True): "hebi",
        ("tiro", True, False): "tibo",
        ("tiro", False, True): "tiit",
        ("tiro", True, True): "tibi",
        ("cour", True, False): "cobo",
        ("cour", False, True): "coit",
        ("cour", True, True): "cobi",
    }.get((base, bold, italic), base)
    return _Spare(base, label, None, pymupdf.Font(base))


# ---- changing the page --------------------------------------------------------


def _carry_out(doc, plan: _Plan) -> None:
    import pymupdf

    page = doc[plan.page]
    if plan.points:
        for x, y in plan.points:
            page.add_redact_annot(pymupdf.Rect(x - 0.1, y - 0.1, x + 0.1, y + 0.1), fill=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
        _check_nothing_else_went(page, plan)
    if not plan.write:
        return
    names = _font_names(doc, page, plan)
    content = _content(page, plan, names)
    _put_content(doc, page, plan, content)


def _check_nothing_else_went(page, plan: _Plan) -> None:
    """Every letter that was to stay is still there."""
    _spans, after = _read_trace(page)
    left: dict[tuple, int] = {}
    for glyph in after:
        key = (glyph.letter, round(glyph.x, 1), round(glyph.y, 1))
        left[key] = left.get(key, 0) + 1
    for glyph in plan.keep:
        key = (glyph.letter, round(glyph.x, 1), round(glyph.y, 1))
        if left.get(key, 0) <= 0:
            raise CommandError(f"{CROWDED}: other letters would go too")
        left[key] -= 1


def _font_names(doc, page, plan: _Plan) -> dict:
    """The name of each font on the page, adding it there when needed."""
    names: dict = {}
    resources: dict[int, str] = {}
    for xref, _ext, _type, _base, refname, _enc, referencer in page.get_fonts(full=True):
        if referencer == 0 and refname:
            resources.setdefault(xref, refname)
    for _glyph, _x, style in plan.write:
        key = style[0]
        if key in names:
            continue
        if key[0] == "doc":
            xref = key[1]
            if xref not in resources:
                resources[xref] = f"{RESOURCE}{xref}"
                _add_font_resource(doc, page, resources[xref], xref)
            names[key] = resources[xref]
        else:
            spare: _Spare = plan.borrowed[key]
            names[key] = _put_spare(doc, page, spare, resources)
    return names


def _add_font_resource(doc, page, name: str, xref: int) -> None:
    kind, value = doc.xref_get_key(page.xref, "Resources")
    if kind == "xref":
        holder, path = int(value.split()[0]), f"Font/{name}"
    else:
        holder, path = page.xref, f"Resources/Font/{name}"
    doc.xref_set_key(holder, path, f"{xref} 0 R")


SPARE_FONTS = "lector_spare_fonts"  # on the open document: fonts already put in


def _put_spare(doc, page, spare: _Spare, resources: dict[int, str]) -> str:
    """Put a borrowed font in the document (once) and on the page."""
    known: dict = getattr(doc, SPARE_FONTS, None) or {}
    xref = known.get(spare.key)
    if xref is not None:
        try:
            if doc.xref_get_key(xref, "Type") != ("name", "/Font"):
                xref = None
        except Exception:
            xref = None
    if xref is None:
        name = f"{RESOURCE}s{len(known) + 1}"
        while name in resources.values():
            name += "x"
        if spare.buffer is None:  # a standard font: nothing is put in the file
            xref = page.insert_font(fontname=spare.key)
            name = spare.key
        else:
            xref = page.insert_font(fontname=name, fontbuffer=spare.buffer)
        known[spare.key] = xref
        setattr(doc, SPARE_FONTS, known)
        resources[xref] = name
        return name
    if xref not in resources:
        resources[xref] = f"{RESOURCE}{xref}"
        _add_font_resource(doc, page, resources[xref], xref)
    return resources[xref]


def _pdf_point(page, x: float, y: float) -> tuple[float, float]:
    """From the page not turned (top left, downwards) to the PDF's own
    coordinates (bottom left, upwards)."""
    return x + page.cropbox_position.x, page.mediabox.y1 - page.cropbox.y0 - y


def _number(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _color(colorspace: int, color: tuple, stroke: bool) -> str:
    values = " ".join(_number(value) for value in color)
    if colorspace == 4 and len(color) == 4:
        return f"{values} {'K' if stroke else 'k'}"
    if colorspace == 3 and len(color) == 3:
        return f"{values} {'RG' if stroke else 'rg'}"
    if len(color) == 1:
        return f"{values} {'G' if stroke else 'g'}"
    return f"0 {'G' if stroke else 'g'}"


def _content(page, plan: _Plan, names: dict) -> bytes:
    """The PDF orders that write the letters, each at its exact place."""
    out = ["q"]
    runs: list[list[tuple[_Glyph, float, tuple]]] = []
    for entry in sorted(plan.write, key=lambda entry: entry[1]):
        glyph, _x, style = entry
        if glyph.code is None or not style or glyph.rider:
            continue
        if runs and runs[-1][0][2] == style:
            runs[-1].append(entry)
        else:
            runs.append([entry])
    for run in runs:
        first, x0, style = run[0]
        font_key, kind, colorspace, color, linewidth, height, size = style
        px, py = _pdf_point(page, x0, first.y)
        parts = []
        for at, (glyph, x, _style) in enumerate(run):
            parts.append(f"<{glyph.code.hex()}>")
            if at + 1 < len(run):
                following = run[at + 1][1]
                natural = glyph.font.width(glyph.code) if glyph.font else None
                if natural is None:
                    natural = glyph.width * 1000 / size if size else 0
                move = natural - (following - x) * 1000 / size if size else 0
                if abs(move) > 0.001:
                    parts.append(_number(move))
        mode = 1 if kind == STROKE else 0
        out += [
            "BT",
            f"/{names[font_key]} 1 Tf",
            "0 Tc 0 Tw 100 Tz 0 Ts",
            f"{mode} Tr",
            _color(colorspace, color, stroke=kind == STROKE),
        ]
        if kind == STROKE:
            out.append(f"{_number(linewidth or 1)} w")
        out += [
            f"{_number(size)} 0 0 {_number(height)} {_number(px)} {_number(py)} Tm",
            "[" + " ".join(parts) + "] TJ",
            "ET",
        ]
    out.append("Q")
    return ("\n".join(out) + "\n").encode("latin-1")


def _put_content(doc, page, plan: _Plan, content: bytes) -> None:
    """Put the new letters among the drawing orders of the page, right after
    the letter drawn before them, so that every program reads them in their
    place (search, selection, copying, screen readers). If the page's own
    orders cannot be followed, they go at the end."""
    data = page.read_contents()
    try:
        after = None
        if plan.before is not None:
            after = _pdf_point(page, plan.before.x, plan.before.y)
        place = pdf_content.insertion_point(data, after)
        joined = pdf_content.splice(data, place, content)
    except pdf_content.ContentError:
        if not page.is_wrapped:
            page.wrap_contents()
        data = page.read_contents()
        joined = data + b"\n" + content
    xref = doc.get_new_xref()
    doc.update_object(xref, "<<>>")
    doc.update_stream(xref, joined, compress=True)
    doc.xref_set_key(page.xref, "Contents", f"{xref} 0 R")


register_reader("change_text", ChangeText.from_dict)
