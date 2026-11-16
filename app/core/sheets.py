"""Sheets put between the pages, to write on: plain, ruled or squared.

A sheet is an ordinary page of the PDF, the size of the page it follows. Its
lines are part of the page (not annotations), drawn thin and light, so that
what is written over them stands out. Any reader shows it.

Putting a sheet moves every later page one place down; taking it away (undo)
moves them back. The order says so with ``page_change``, so that the window
can follow without reading the whole document again.
"""

from dataclasses import dataclass

from app.core.commands import CommandError, new_name, register_reader

PLAIN = "blank"
RULED = "ruled"
SQUARED = "squared"
SHEETS = (PLAIN, RULED, SQUARED)
DEFAULT_SHEET = PLAIN

SHEET_KEY = "LectorPDFSheet"  # kept in the page: how the order finds its sheet again
MM = 72 / 25.4
LINE_GAP = 8 * MM  # between the lines of a ruled sheet, as in a notebook
SQUARE = 5 * MM  # the side of a square
MARGIN = 15 * MM  # the lines start and end this far from the edge
TOP = 25 * MM  # a ruled sheet leaves room above, for a title
LINE_COLOR = (0.62, 0.74, 0.88)  # light blue, as in paper notebooks
GRID_COLOR = (0.74, 0.80, 0.88)
LINE_WIDTH = 0.5
GRID_WIDTH = 0.35

Size = tuple[float, float]


def clamp_size(size) -> Size:
    """A page size that can be used (in points), whatever was given."""
    try:
        width, height = (float(value) for value in size)
    except (TypeError, ValueError):
        return (595.0, 842.0)  # A4
    if not (width > 0 and height > 0):
        return (595.0, 842.0)
    return (max(72.0, min(14400.0, width)), max(72.0, min(14400.0, height)))


@dataclass(frozen=True)
class InsertSheet:
    """A new sheet at place ``at`` (counting from 0): it becomes that page."""

    at: int
    kind: str  # one of SHEETS
    size: Size  # width and height, in points
    name: str

    def pages(self) -> list[int]:
        return [self.at]

    def page_change(self, undone: bool) -> tuple[int, int]:
        """Where the pages change and how: one more there, or one less."""
        return self.at, -1 if undone else 1

    def apply(self, doc) -> list[int]:
        if self.kind not in SHEETS:
            raise CommandError(f"unknown sheet: {self.kind}")
        if not 0 <= self.at <= doc.page_count:
            raise CommandError(f"no place {self.at} for a sheet")
        if _find(doc, self.name) is not None:
            return self.pages()
        try:
            width, height = clamp_size(self.size)
            page = doc.new_page(pno=self.at, width=width, height=height)
            _draw_lines(page, self.kind)
            doc.xref_set_key(page.xref, SHEET_KEY, f"({self.name})")
        except Exception as error:
            raise CommandError(f"cannot put the sheet: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        place = _find(doc, self.name)
        if place is None:
            raise CommandError("the sheet is not there")
        if doc.page_count == 1:
            raise CommandError("a document cannot be left without pages")
        doc.delete_page(place)
        return [place]

    def to_dict(self) -> dict:
        return {
            "what": "insert_sheet",
            "at": self.at,
            "kind": self.kind,
            "size": list(self.size),
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InsertSheet":
        return cls(int(data["at"]), str(data["kind"]), clamp_size(data["size"]), str(data["name"]))


register_reader("insert_sheet", InsertSheet.from_dict)


def new_sheet(at: int, kind: str = DEFAULT_SHEET, size=(595.0, 842.0)) -> InsertSheet:
    return InsertSheet(
        int(at), kind if kind in SHEETS else DEFAULT_SHEET, clamp_size(size), new_name()
    )


def _find(doc, name: str) -> int | None:
    """The place of the sheet with that name, if it is in the document."""
    wanted = f"({name})"
    for number in range(doc.page_count):
        kept = doc.xref_get_key(doc.page_xref(number), SHEET_KEY)
        if kept[0] == "string" and f"({kept[1]})" == wanted:
            return number
    return None


def is_sheet(doc, number: int) -> bool:
    """Whether a page is a sheet put by this program."""
    return doc.xref_get_key(doc.page_xref(number), SHEET_KEY)[0] == "string"


def _draw_lines(page, kind: str) -> None:
    if kind == PLAIN:
        return
    width, height = page.rect.width, page.rect.height
    shape = page.new_shape()
    if kind == RULED:
        y = TOP
        while y <= height - MARGIN:
            shape.draw_line((MARGIN, y), (width - MARGIN, y))
            y += LINE_GAP
        shape.finish(color=LINE_COLOR, width=LINE_WIDTH)
    else:
        columns = int((width - 2 * MARGIN) // SQUARE)
        rows = int((height - 2 * MARGIN) // SQUARE)
        left = (width - columns * SQUARE) / 2
        top = (height - rows * SQUARE) / 2
        for column in range(columns + 1):
            x = left + column * SQUARE
            shape.draw_line((x, top), (x, top + rows * SQUARE))
        for row in range(rows + 1):
            y = top + row * SQUARE
            shape.draw_line((left, y), (left + columns * SQUARE, y))
        shape.finish(color=GRID_COLOR, width=GRID_WIDTH)
    shape.commit()
