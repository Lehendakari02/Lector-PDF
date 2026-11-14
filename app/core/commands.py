"""Changes to a document, each one an "order" that knows how to apply and undo itself.

Everything that modifies a PDF (a highlight, a note, a deleted page…) is one of
these orders. An order holds everything it needs, as plain data: it can be
applied to the open document, undone, sent to the helper process that owns the
document, and written down (the recovery journal of task 2.5 and undo/redo of
task 2.4 are built on this same piece, not on separate systems).

What an order writes is always standard PDF: the marks made here are ordinary
PDF annotations that Adobe Reader, Edge and any other viewer show the same.
"""

import uuid
from dataclasses import dataclass

from app.core.search import PageText, Rect
from app.core.selection import selection_rects

HIGHLIGHT = "highlight"
UNDERLINE = "underline"
STRIKEOUT = "strikeout"
MARKUP_KINDS = (HIGHLIGHT, UNDERLINE, STRIKEOUT)

Color = tuple[float, float, float]  # red, green, blue, each from 0 to 1

# The colour each tool starts with (task 2.3 lets the user choose any other).
DEFAULT_COLORS: dict[str, Color] = {
    HIGHLIGHT: (1.0, 0.92, 0.23),  # marker yellow
    UNDERLINE: (0.85, 0.15, 0.15),  # pen red
    STRIKEOUT: (0.85, 0.15, 0.15),
}

NAME_PREFIX = "lectorpdf-"


class CommandError(Exception):
    """An order could not be applied or undone on this document."""


def new_name() -> str:
    """A name no other annotation has: it is how an order finds its own later."""
    return NAME_PREFIX + uuid.uuid4().hex


@dataclass(frozen=True)
class Mark:
    """The part of a text mark that lies on one page: one rectangle per line."""

    page: int
    rects: tuple[Rect, ...]  # in the coordinates the page is shown and read with
    name: str


def _find_annotation(page, name: str):
    for annotation in page.annots() or ():
        if annotation.info.get("id") == name:
            return annotation
    return None


@dataclass(frozen=True)
class AddMarkup:
    """Highlight, underline or strike out text. One order may span several pages."""

    kind: str
    marks: tuple[Mark, ...]
    color: Color
    opacity: float = 1.0

    def pages(self) -> list[int]:
        return sorted({mark.page for mark in self.marks})

    def apply(self, doc) -> list[int]:
        """Put the marks on ``doc`` (a PyMuPDF document). Returns the pages changed."""
        import pymupdf

        if self.kind not in MARKUP_KINDS:
            raise CommandError(f"unknown kind of mark: {self.kind}")
        done: list[Mark] = []
        try:
            for mark in self.marks:
                page = doc[mark.page]
                if _find_annotation(page, mark.name) is not None:
                    continue  # already there (the order is applied only once)
                # The rectangles come from the page as it is shown; an annotation
                # is stored in the page's own coordinates, which differ when the
                # page is kept turned inside the file.
                quads = [pymupdf.Rect(rect).quad * page.derotation_matrix for rect in mark.rects]
                if not quads:
                    continue
                add = {
                    HIGHLIGHT: page.add_highlight_annot,
                    UNDERLINE: page.add_underline_annot,
                    STRIKEOUT: page.add_strikeout_annot,
                }[self.kind]
                annotation = add(quads=quads)
                annotation.set_colors(stroke=self.color)
                annotation.set_opacity(max(0.05, min(1.0, self.opacity)))
                annotation.update()
                doc.xref_set_key(annotation.xref, "NM", f"({mark.name})")
                done.append(mark)
        except CommandError:
            raise
        except Exception as error:  # PyMuPDF raises several unrelated error types
            # All or nothing: what was already put is taken away again.
            for mark in done:
                self._remove(doc, mark)
            raise CommandError(f"cannot mark the text: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        """Take the marks away again. Returns the pages changed."""
        try:
            for mark in self.marks:
                self._remove(doc, mark)
        except Exception as error:
            raise CommandError(f"cannot remove the mark: {error}") from error
        return self.pages()

    @staticmethod
    def _remove(doc, mark: Mark) -> None:
        page = doc[mark.page]
        annotation = _find_annotation(page, mark.name)
        if annotation is not None:
            page.delete_annot(annotation)

    def to_dict(self) -> dict:
        return {
            "what": "add_markup",
            "kind": self.kind,
            "color": list(self.color),
            "opacity": self.opacity,
            "marks": [
                {"page": mark.page, "name": mark.name, "rects": [list(r) for r in mark.rects]}
                for mark in self.marks
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AddMarkup":
        marks = tuple(
            Mark(
                int(mark["page"]),
                tuple(tuple(float(v) for v in rect) for rect in mark["rects"]),
                str(mark["name"]),
            )
            for mark in data["marks"]
        )
        color = tuple(float(v) for v in data["color"])
        return cls(str(data["kind"]), marks, color, float(data.get("opacity", 1.0)))


Command = AddMarkup  # the only kind of order so far; later ones join here

_READERS = {"add_markup": AddMarkup.from_dict}


def command_from_dict(data: dict) -> Command:
    """Read back an order written with ``to_dict`` (for the recovery journal)."""
    try:
        return _READERS[data["what"]](data)
    except (KeyError, TypeError, ValueError) as error:
        raise CommandError(f"not an order this program knows: {error}") from error


def markup_for_selection(
    kind: str,
    start: tuple[int, int],
    stop: tuple[int, int],
    page_text,
    color: Color | None = None,
    opacity: float = 1.0,
) -> AddMarkup | None:
    """The order that marks the text between two places, each (page, caret).

    ``page_text(number)`` gives the ``PageText`` of a page. Returns None when
    there is no text between the two places.
    """
    if kind not in MARKUP_KINDS:
        raise CommandError(f"unknown kind of mark: {kind}")
    if stop < start:
        start, stop = stop, start
    marks = []
    for number in range(start[0], stop[0] + 1):
        text: PageText = page_text(number)
        first = start[1] if number == start[0] else 0
        last = stop[1] if number == stop[0] else len(text)
        rects = tuple(_solid(rect) for rect in selection_rects(text, first, last))
        rects = tuple(rect for rect in rects if rect is not None)
        if rects:
            marks.append(Mark(number, rects, new_name()))
    if not marks:
        return None
    return AddMarkup(kind, tuple(marks), color or DEFAULT_COLORS[kind], opacity)


def _solid(rect: Rect) -> Rect | None:
    """The rectangle, if it has some width and height (spaces alone have none)."""
    x0, y0, x1, y1 = rect
    if x1 - x0 < 0.5 or y1 - y0 < 0.5:
        return None
    return (float(x0), float(y0), float(x1), float(y1))
