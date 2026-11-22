"""Sticky notes and text boxes: the orders that put, change and remove them.

Both are ordinary PDF annotations, so Adobe Reader, Edge and any other viewer
show them the same:

- a **note** is a "Text" annotation: a small icon on the page that holds a text;
- a **text box** is a "FreeText" annotation: text written on the page itself.

Text boxes use only the three families every PDF reader has built in (without
serifs, with serifs and typewriter), each in its normal and its bold weight.
Any other font would have to travel inside the file as a drawing to look the
same elsewhere.

A text box is as wide as its longest line, or as wide as it was made by hand:
then its text is cut into lines to fit. The lines are cut here, with the real
widths of the letters, so the box looks the same in every viewer. What only
this program needs to put a box again just the same (the width chosen and the
weight) is kept in the annotation under keys of its own.

Changing or removing one is also an order, built on the order that would put
it: ``Remove`` takes it away and ``Replace`` swaps it for another. That needs
everything the annotation is made of, which ``page_notes`` reads back from the
document; so only the notes and boxes made by this program can be changed
(the ones of other programs carry things this program would lose).
"""

import functools
import re
from dataclasses import dataclass

from app.core import symbols
from app.core.commands import (
    NAME_PREFIX,
    Color,
    Command,
    CommandError,
    command_from_dict,
    find_annotation,
    new_name,
    register_reader,
)
from app.core.foreign import Foreign, families_of, foreign_of, key_of
from app.core.search import Rect

NOTE = "note"
TEXT_BOX = "text_box"

NOTE_COLOR: Color = (1.0, 0.82, 0.2)  # sticky-note yellow
NOTE_SIZE = 16.0  # side of the icon, in points (the engine draws it this size)

SANS = "sans"
SERIF = "serif"
MONO = "mono"
# The fonts every PDF reader has, by the names PyMuPDF gives them.
FONTS = {SANS: "Helv", SERIF: "TiRo", MONO: "Cour"}
# Their bold weights: the name PyMuPDF measures with and the one PDF readers know.
BOLD_FONTS = {
    SANS: ("hebo", "Helvetica-Bold"),
    SERIF: ("tibo", "Times-Bold"),
    MONO: ("cobo", "Courier-Bold"),
}
SYMBOL_FONT_KEY = "LectorPDFSymbols"  # where the document keeps the font of the symbols
WIDTH_KEY = "LectorPDFWidth"  # where the annotation keeps a width chosen by hand
BOLD_KEY = "LectorPDFBold"
TEXT_COLOR: Color = (0.1, 0.1, 0.1)
TEXT_SIZE = 12.0
MIN_SIZE, MAX_SIZE = 6.0, 72.0

LINE_HEIGHT = 1.25  # of the size of the letter
PADDING = 2.0  # points between the text and the edge of its box
# Room to spare, so that the engine never pushes the last word to another line.
WIDTH_SLACK = 1.02
MIN_BOX_WIDTH = 40.0
MAX_BOX_WIDTH = 5000.0
PAGE_MARGIN = 4.0


@dataclass(frozen=True)
class AddNote:
    """Stick a note on a page: an icon at ``point`` that holds ``text``."""

    page: int
    point: tuple[float, float]  # top left of the icon, as the page is shown
    text: str
    color: Color
    name: str

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                x, y = self.point
                shown = pymupdf.Rect(x, y, x + NOTE_SIZE, y + NOTE_SIZE)
                rect = (shown * page.derotation_matrix).normalize()
                annotation = page.add_text_annot(rect.tl, self.text, icon="Note")
                off = rect.tl - annotation.rect.tl
                if abs(off.x) > 0.01 or abs(off.y) > 0.01:
                    # On a turned page the engine puts the icon to another side
                    # of the point: put it again, moved by that much.
                    page.delete_annot(annotation)
                    annotation = page.add_text_annot(rect.tl + off, self.text, icon="Note")
                annotation.set_colors(stroke=self.color)
                annotation.update()
                doc.xref_set_key(annotation.xref, "NM", f"({self.name})")
        except Exception as error:  # PyMuPDF raises several unrelated error types
            raise CommandError(f"cannot put the note: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        return _remove(doc, self.page, self.name)

    def to_dict(self) -> dict:
        return {
            "what": "add_note",
            "page": self.page,
            "point": list(self.point),
            "text": self.text,
            "color": list(self.color),
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AddNote":
        x, y = (float(value) for value in data["point"])
        return cls(
            int(data["page"]), (x, y), str(data["text"]), _color(data["color"]), str(data["name"])
        )


@dataclass(frozen=True)
class AddTextBox:
    """Write text on a page, from ``origin`` to the right and down."""

    page: int
    origin: tuple[float, float]  # top left of the box, as the page is shown
    text: str
    font: str  # one of FONTS
    size: float
    color: Color
    name: str
    width: float = 0.0  # of the box, chosen by hand; 0: as wide as its longest line
    bold: bool = False

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        if self.font not in FONTS:
            raise CommandError(f"unknown font: {self.font}")
        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                shown_page = page.rect  # as shown: turned pages already count
                lines, shown = box_layout(
                    self.text,
                    self.font,
                    self.size,
                    self.origin,
                    shown_page.width,
                    self.width,
                    self.bold,
                )
                rect = (pymupdf.Rect(shown) * page.derotation_matrix).normalize()
                special = symbols.has_symbols(self.text)
                annotation = page.add_freetext_annot(
                    rect,
                    # The engine writes the plain letters; the symbols come after.
                    "\n".join(_plain(line) for line in lines) if special else "\n".join(lines),
                    fontsize=self.size,
                    fontname=FONTS[self.font],
                    text_color=self.color,
                    border_width=0,
                    rotate=page.rotation,  # upright for the reader on a turned page
                )
                annotation.update()
                xref = annotation.xref
                doc.xref_set_key(xref, "NM", f"({self.name})")
                # PyMuPDF leaves the line of a "callout" that was never asked for.
                doc.xref_set_key(xref, "CL", "null")
                # The text as it was written, not as it was cut into lines.
                doc.xref_set_key(xref, "Contents", pymupdf.get_pdf_str(self.text))
                if self.width > 0:
                    doc.xref_set_key(xref, WIDTH_KEY, f"{self.width:.2f}")
                if self.bold:
                    _make_bold(doc, xref, self.font)
                if special:
                    _write_symbols(doc, page, xref, lines, self.font, self.size)
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(f"cannot write the text: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        return _remove(doc, self.page, self.name)

    def to_dict(self) -> dict:
        return (
            {
                "what": "add_text_box",
                "page": self.page,
                "origin": list(self.origin),
                "text": self.text,
                "font": self.font,
                "size": self.size,
                "color": list(self.color),
                "name": self.name,
            }
            | ({"width": self.width} if self.width > 0 else {})
            | ({"bold": True} if self.bold else {})
        )

    @classmethod
    def from_dict(cls, data: dict) -> "AddTextBox":
        x, y = (float(value) for value in data["origin"])
        return cls(
            int(data["page"]),
            (x, y),
            str(data["text"]),
            str(data["font"]),
            float(data["size"]),
            _color(data["color"]),
            str(data["name"]),
            clamp_box_width(data.get("width", 0.0)),
            data.get("bold") is True,
        )


def clamp_box_width(value: object) -> float:
    """A width for a text box: 0 (as wide as its text) or one that can be used."""
    try:
        width = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not width > 0:
        return 0.0
    return max(MIN_BOX_WIDTH, min(MAX_BOX_WIDTH, width))


def _plain(line: str) -> str:
    """A line with a plain letter in the place of every symbol."""
    return "".join("?" if symbols.is_symbol(letter) else letter for letter in line)


def _pdf_text(piece: str) -> str:
    """A piece of plain letters as the look of an annotation writes it."""
    out = []
    for byte in piece.encode("cp1252", errors="replace"):
        if byte in b"()\\":
            out.append("\\" + chr(byte))
        elif 32 <= byte < 127:
            out.append(chr(byte))
        else:
            out.append(f"\\{byte:03o}")
    return f"({''.join(out)}) Tj"


def _symbol_font(doc, page) -> int:
    """The font of the symbols inside the document: put in the first time, then reused."""
    catalog = doc.pdf_catalog()
    kept = doc.xref_get_key(catalog, SYMBOL_FONT_KEY)
    if kept[0] == "xref":
        return int(kept[1].split()[0])
    xref = page.insert_font(fontname=symbols.FONT_NAME, fontfile=str(symbols.font_file()))
    doc.xref_set_key(catalog, SYMBOL_FONT_KEY, f"{xref} 0 R")
    return xref


def _write_symbols(doc, page, xref: int, lines: list[str], font: str, size: float) -> None:
    """Write the lines again in the look of a text box, each symbol with its font.

    The engine wrote every line with one letter font and a "?" where a symbol
    goes. Each of those lines is written again in pieces: the plain letters as
    they were, the symbols with the font of the symbols.
    """
    look = doc.xref_get_key(xref, "AP/N")
    if look[0] != "xref":
        return
    look_xref = int(look[1].split()[0])
    stream = doc.xref_stream(look_xref).decode("latin-1").split("\n")
    written = [i for i, row in enumerate(stream) if row.endswith(") Tj")]
    if len(written) != len(lines):
        return  # not the look that is known: left as the engine made it
    base = f"/{FONTS[font]} {size:g} Tf"
    special = f"/{symbols.FONT_NAME} {size:g} Tf"
    for place, line in zip(written, lines, strict=True):
        pieces = []
        for is_special, piece in symbols.runs(line):
            if is_special:
                pieces += [special, f"<{symbols.glyphs(piece)}> Tj"]
            else:
                pieces += [base, _pdf_text(piece)]
        stream[place] = "\n".join(pieces)
    doc.update_stream(look_xref, "\n".join(stream).encode("latin-1"))
    font_xref = _symbol_font(doc, page)
    doc.xref_set_key(look_xref, f"Resources/Font/{symbols.FONT_NAME}", f"{font_xref} 0 R")


def _make_bold(doc, xref: int, font: str) -> None:
    """Give the look of a text box the bold weight of its font.

    The engine only writes with the normal weight; the look it made names its
    font, and that name is pointed to the bold one. The lines were already
    cut with the widths of the bold letters.
    """
    look = doc.xref_get_key(xref, "AP/N")
    if look[0] != "xref":
        return
    bold = doc.get_new_xref()
    doc.update_object(
        bold,
        f"<</Type/Font/Subtype/Type1/BaseFont/{BOLD_FONTS[font][1]}/Encoding/WinAnsiEncoding>>",
    )
    doc.xref_set_key(int(look[1].split()[0]), f"Resources/Font/{FONTS[font]}", f"{bold} 0 R")
    doc.xref_set_key(xref, BOLD_KEY, "true")


@dataclass(frozen=True)
class Remove:
    """Take away a note or a text box: the order that put it, the other way round."""

    order: Command

    def pages(self) -> list[int]:
        return self.order.pages()

    def prepared(self, doc) -> "Remove":
        """Ready to be carried out on ``doc``: what is taken away keeps a copy
        of itself when it needs one (``Foreign.prepared``)."""
        ready = getattr(self.order, "prepared", None)
        return Remove(ready(doc)) if ready is not None else self

    def apply(self, doc) -> list[int]:
        return self.order.undo(doc)

    def undo(self, doc) -> list[int]:
        return self.order.apply(doc)

    def to_dict(self) -> dict:
        return {"what": "remove", "order": self.order.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "Remove":
        return cls(command_from_dict(data["order"]))


@dataclass(frozen=True)
class Replace:
    """Change a note or a text box: the old one goes and the new one comes."""

    old: Command
    new: Command

    def pages(self) -> list[int]:
        return sorted({*self.old.pages(), *self.new.pages()})

    def apply(self, doc) -> list[int]:
        return self._swap(doc, self.old, self.new)

    def undo(self, doc) -> list[int]:
        return self._swap(doc, self.new, self.old)

    def _swap(self, doc, gone: Command, come: Command) -> list[int]:
        gone.undo(doc)
        try:
            come.apply(doc)
        except CommandError:
            gone.apply(doc)  # all or nothing: what was there stays
            raise
        return self.pages()

    def to_dict(self) -> dict:
        return {"what": "replace", "old": self.old.to_dict(), "new": self.new.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "Replace":
        return cls(command_from_dict(data["old"]), command_from_dict(data["new"]))


register_reader("add_note", AddNote.from_dict)
register_reader("add_text_box", AddTextBox.from_dict)
register_reader("remove", Remove.from_dict)
register_reader("replace", Replace.from_dict)


def _remove(doc, page_number: int, name: str) -> list[int]:
    try:
        page = doc[page_number]
        annotation = find_annotation(page, name)
        if annotation is not None:
            page.delete_annot(annotation)
    except Exception as error:
        raise CommandError(f"cannot remove it: {error}") from error
    return [page_number]


def _color(values) -> Color:
    red, green, blue = (max(0.0, min(1.0, float(value))) for value in values)
    return (red, green, blue)


# ---- the size of a text box ---------------------------------------------------


def text_width(text: str, font: str, size: float, bold: bool = False) -> float:
    """How wide a line is, in points. Arrows and symbols have their own font."""
    if not symbols.has_symbols(text):
        return _font(font, bold).text_length(text, size)
    return sum(
        symbols.width(piece, size) if special else _font(font, bold).text_length(piece, size)
        for special, piece in symbols.runs(text)
    )


@functools.cache
def _font(font: str, bold: bool = False):
    import pymupdf

    return pymupdf.Font(BOLD_FONTS[font][0] if bold else FONTS[font].lower())


def wrap_text(text: str, font: str, size: float, width: float, bold: bool = False) -> list[str]:
    """The lines of ``text``, cutting at spaces those wider than ``width``.

    A word wider than the whole width is cut wherever it has to be.
    """
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        current = ""
        for word in line.split(" "):
            candidate = word if not current else f"{current} {word}"
            if not current or text_width(candidate, font, size, bold) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
            while text_width(current, font, size, bold) > width and len(current) > 1:
                cut = len(current) - 1
                while cut > 1 and text_width(current[:cut], font, size, bold) > width:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
        lines.append(current)
    return lines


def box_layout(
    text: str,
    font: str,
    size: float,
    origin: tuple[float, float],
    page_width: float,
    width: float = 0.0,
    bold: bool = False,
) -> tuple[list[str], Rect]:
    """The lines of a text box and the rectangle it takes, as the page is shown.

    Without ``width`` the box is as wide as its longest line. With it, the box
    is that wide and its text is cut into lines to fit. Either way it never
    goes past the right edge of the page: lines that would are cut at a space.
    """
    x, y = origin
    outer = max(MIN_BOX_WIDTH, page_width - PAGE_MARGIN - x)
    if width > 0:
        outer = min(outer, max(MIN_BOX_WIDTH, width))
    lines = wrap_text(text, font, size, (outer - 2 * PADDING - 2) / WIDTH_SLACK, bold)
    if width > 0:
        wide = outer
    else:
        widest = max(text_width(line, font, size, bold) for line in lines)
        wide = widest * WIDTH_SLACK + 2 * PADDING + 2
    height = len(lines) * size * LINE_HEIGHT + 2 * PADDING
    return lines, (x, y, x + wide, y + height)


# ---- reading them back ----------------------------------------------------------


@dataclass(frozen=True)
class PageNote:
    """A note or a text box that is on a page, with all it is made of."""

    kind: str  # NOTE or TEXT_BOX
    page: int
    name: str  # "" if it has none (it cannot be found again, so not changed)
    rect: Rect  # where it is, as the page is shown
    text: str
    color: Color
    font: str = SANS  # text boxes only
    size: float = TEXT_SIZE  # text boxes only
    width: float = 0.0  # text boxes only: chosen by hand, or 0
    bold: bool = False  # text boxes only
    foreign: Foreign | None = None  # made by another program: only taken away

    @property
    def ours(self) -> bool:
        """Made by this program: it can be changed and removed."""
        return self.name.startswith(NAME_PREFIX)

    @property
    def removable(self) -> bool:
        """It can be taken away: made here, or by another program."""
        return self.ours or self.foreign is not None

    def order(self) -> Command:
        """The order that would put it as it is."""
        if self.foreign is not None:
            return self.foreign
        origin = (self.rect[0], self.rect[1])
        if self.kind == NOTE:
            return AddNote(self.page, origin, self.text, self.color, self.name)
        return AddTextBox(
            self.page,
            origin,
            self.text,
            self.font,
            self.size,
            self.color,
            self.name,
            self.width,
            self.bold,
        )


_APPEARANCE = re.compile(r"/(\S+)\s+([\d.]+)\s+Tf")
_FONT_NAMES = {name.lower(): font for font, name in FONTS.items()}


def page_notes(doc, page_number: int) -> list[PageNote]:
    """The notes and text boxes of a page, of this program or of any other."""
    found: list[PageNote] = []
    page = doc[page_number]
    families = None  # read when the first annotation of another program comes
    for annotation in page.annots() or ():
        kind = {"Text": NOTE, "FreeText": TEXT_BOX}.get(annotation.type[1])
        if kind is None:
            continue
        rect = (annotation.rect * page.rotation_matrix).normalize()
        info = annotation.info
        colors = annotation.colors or {}
        font, size, color = SANS, TEXT_SIZE, colors.get("stroke") or NOTE_COLOR
        width, bold = 0.0, False
        if kind == TEXT_BOX:
            font, size, color = _text_style(doc, annotation.xref)
            wide = doc.xref_get_key(annotation.xref, WIDTH_KEY)
            width = clamp_box_width(wide[1]) if wide[0] in ("int", "float") else 0.0
            bold = doc.xref_get_key(annotation.xref, BOLD_KEY) == ("bool", "true")
        name = str(info.get("id") or "")
        box = (rect.x0, rect.y0, rect.x1, rect.y1)
        foreign = None
        if not name.startswith(NAME_PREFIX):
            families = families or families_of(doc, page_number)
            foreign = foreign_of(doc, page_number, annotation, box, families)
            name = key_of(annotation.xref)
        found.append(
            PageNote(
                kind,
                page_number,
                name,
                box,
                str(info.get("content") or ""),
                _color(color) if len(color) == 3 else NOTE_COLOR,
                font,
                size,
                width,
                bold,
                foreign,
            )
        )
    return found


def _text_style(doc, xref: int) -> tuple[str, float, Color]:
    """Font, size and colour of a text box, from its "default appearance"."""
    kind, written = doc.xref_get_key(xref, "DA")
    font, size, color = SANS, TEXT_SIZE, TEXT_COLOR
    if kind != "string":
        return font, size, color
    match = _APPEARANCE.search(written)
    if match:
        font = _FONT_NAMES.get(match.group(1).lower(), SANS)
        size = float(match.group(2)) or TEXT_SIZE
    numbers = re.match(r"\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg", written)
    gray = re.match(r"\s*([\d.]+)\s+g\b", written)
    if numbers:
        color = _color(numbers.groups())
    elif gray:
        color = _color([gray.group(1)] * 3)
    return font, size, color


def note_at(notes: list[PageNote], x: float, y: float) -> PageNote | None:
    """The note or text box under a point of the page (the last one drawn wins)."""
    for note in reversed(notes):
        x0, y0, x1, y1 = note.rect
        if x0 <= x <= x1 and y0 <= y <= y1:
            return note
    return None


def new_note(page: int, point: tuple[float, float], text: str, color: Color = NOTE_COLOR):
    return AddNote(page, point, text, color, new_name())


def new_text_box(
    page: int,
    origin: tuple[float, float],
    text: str,
    font: str = SANS,
    size: float = TEXT_SIZE,
    color: Color = TEXT_COLOR,
    width: float = 0.0,
    bold: bool = False,
) -> AddTextBox:
    return AddTextBox(
        page, origin, text, font, size, color, new_name(), clamp_box_width(width), bool(bold)
    )


def changed(note: PageNote, **changes) -> Replace:
    """The order that changes a note or a text box (text, colour, font, size)."""
    from dataclasses import replace

    return Replace(note.order(), replace(note, **changes).order())
