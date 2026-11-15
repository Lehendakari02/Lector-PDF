"""Drawing on the page: freehand strokes, lines, arrows, boxes and ovals.

All of them are ordinary PDF annotations ("Ink", "Line", "Square" and
"Circle"), so Adobe Reader, Edge and any other viewer show them the same. Each
one is put by an order, like every other change, and read back from the
document by ``page_drawings`` with all it is made of, so that the eraser can
take it away (and undo can bring it back exactly as it was).

``page_drawings`` also reads the highlights, underlines and strike-outs, for
the same eraser.
"""

import math
from dataclasses import dataclass

from app.core.commands import (
    MARKUP_KINDS,
    NAME_PREFIX,
    AddMarkup,
    Color,
    Command,
    CommandError,
    Mark,
    find_annotation,
    new_name,
    register_reader,
)
from app.core.search import Rect

INK = "ink"
LINE = "line"
ARROW = "arrow"
BOX = "box"
OVAL = "oval"
SHAPES = (LINE, ARROW, BOX, OVAL)
DRAWING_KINDS = (INK, *SHAPES)
# The tools that are held in hand: the pen, the shapes and the eraser.
DRAW = "draw"
SHAPE_TOOL = "shapes"
ERASER = "eraser"
DEFAULT_SHAPE = ARROW

Point = tuple[float, float]

DRAW_COLOR: Color = (0.13, 0.39, 0.85)  # pen blue
SHAPE_COLOR: Color = (0.85, 0.15, 0.15)  # pen red
WIDTHS = (1.0, 2.0, 4.0, 8.0)  # the thicknesses at hand, in points
DEFAULT_WIDTH = 2.0
MIN_WIDTH, MAX_WIDTH = 0.5, 24.0
MIN_SHAPE = 3.0  # points; a shape smaller than this is a slip of the hand
# PyMuPDF keeps a box or an oval in a rectangle this much bigger all round.
_BOX_PADDING = 1.0


def clamp_width(value: object) -> float:
    """A thickness that can be used, whatever was given."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_WIDTH
    if isinstance(value, bool) or number != number:
        return DEFAULT_WIDTH
    return max(MIN_WIDTH, min(MAX_WIDTH, number))


def _unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _color(values) -> Color:
    red, green, blue = (_unit(value) for value in values)
    return (red, green, blue)


def _points(values) -> tuple[Point, ...]:
    return tuple((float(x), float(y)) for x, y in values)


def _name_it(doc, annotation, name: str) -> None:
    doc.xref_set_key(annotation.xref, "NM", f"({name})")


def _remove(doc, page_number: int, name: str) -> list[int]:
    try:
        page = doc[page_number]
        annotation = find_annotation(page, name)
        if annotation is not None:
            page.delete_annot(annotation)
    except Exception as error:
        raise CommandError(f"cannot remove it: {error}") from error
    return [page_number]


@dataclass(frozen=True)
class AddInk:
    """Draw by hand: one or more strokes, each the points the pen went through."""

    page: int
    strokes: tuple[tuple[Point, ...], ...]  # as the page is shown
    color: Color
    width: float
    opacity: float
    name: str

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                turned = [
                    [tuple(pymupdf.Point(point) * page.derotation_matrix) for point in stroke]
                    for stroke in self.strokes
                    if len(stroke) >= 2
                ]
                if not turned:
                    raise CommandError("there is nothing drawn")
                annotation = page.add_ink_annot(turned)
                annotation.set_border(width=clamp_width(self.width))
                annotation.set_colors(stroke=self.color)
                annotation.set_opacity(max(0.05, _unit(self.opacity)))
                annotation.update()
                _name_it(doc, annotation, self.name)
        except CommandError:
            raise
        except Exception as error:  # PyMuPDF raises several unrelated error types
            raise CommandError(f"cannot draw: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        return _remove(doc, self.page, self.name)

    def to_dict(self) -> dict:
        return {
            "what": "add_ink",
            "page": self.page,
            "strokes": [[list(point) for point in stroke] for stroke in self.strokes],
            "color": list(self.color),
            "width": self.width,
            "opacity": self.opacity,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AddInk":
        return cls(
            int(data["page"]),
            tuple(_points(stroke) for stroke in data["strokes"]),
            _color(data["color"]),
            float(data["width"]),
            float(data.get("opacity", 1.0)),
            str(data["name"]),
        )


@dataclass(frozen=True)
class AddShape:
    """A line, an arrow, a box or an oval, from ``start`` to ``end``.

    For a line or an arrow those are its two ends (the arrow points at
    ``end``); for a box or an oval, two opposite corners.
    """

    kind: str  # one of SHAPES
    page: int
    start: Point  # as the page is shown
    end: Point
    color: Color
    width: float
    opacity: float
    name: str

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        if self.kind not in SHAPES:
            raise CommandError(f"unknown shape: {self.kind}")
        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                first = pymupdf.Point(self.start) * page.derotation_matrix
                last = pymupdf.Point(self.end) * page.derotation_matrix
                if self.kind in (LINE, ARROW):
                    annotation = page.add_line_annot(first, last)
                    if self.kind == ARROW:
                        annotation.set_line_ends(
                            pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_OPEN_ARROW
                        )
                else:
                    rect = pymupdf.Rect(first, last).normalize()
                    add = page.add_rect_annot if self.kind == BOX else page.add_circle_annot
                    annotation = add(rect)
                annotation.set_border(width=clamp_width(self.width))
                annotation.set_colors(stroke=self.color)
                annotation.set_opacity(max(0.05, _unit(self.opacity)))
                annotation.update()
                _name_it(doc, annotation, self.name)
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(f"cannot draw the shape: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        return _remove(doc, self.page, self.name)

    def to_dict(self) -> dict:
        return {
            "what": "add_shape",
            "kind": self.kind,
            "page": self.page,
            "start": list(self.start),
            "end": list(self.end),
            "color": list(self.color),
            "width": self.width,
            "opacity": self.opacity,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AddShape":
        (start, end) = _points((data["start"], data["end"]))
        return cls(
            str(data["kind"]),
            int(data["page"]),
            start,
            end,
            _color(data["color"]),
            float(data["width"]),
            float(data.get("opacity", 1.0)),
            str(data["name"]),
        )


register_reader("add_ink", AddInk.from_dict)
register_reader("add_shape", AddShape.from_dict)


def new_ink(
    page: int,
    strokes,
    color: Color = DRAW_COLOR,
    width: float = DEFAULT_WIDTH,
    opacity: float = 1.0,
) -> AddInk:
    kept = tuple(_points(stroke) for stroke in strokes)
    return AddInk(page, kept, color, clamp_width(width), opacity, new_name())


def new_shape(
    kind: str,
    page: int,
    start: Point,
    end: Point,
    color: Color = SHAPE_COLOR,
    width: float = DEFAULT_WIDTH,
    opacity: float = 1.0,
) -> AddShape | None:
    """The order for a shape, or None if it is too small to be meant."""
    (start, end) = _points((start, end))
    if math.dist(start, end) < MIN_SHAPE:
        return None
    return AddShape(kind, page, start, end, color, clamp_width(width), opacity, new_name())


def thinned(points, apart: float = 0.7) -> tuple[Point, ...]:
    """The points of a stroke without those almost on top of the one before.

    A mouse sends many more points than the line needs; the first and the
    last are always kept.
    """
    points = _points(points)
    if len(points) < 3:
        return points
    kept = [points[0]]
    for point in points[1:-1]:
        if math.dist(point, kept[-1]) >= apart:
            kept.append(point)
    kept.append(points[-1])
    return tuple(kept)


# ---- reading them back ----------------------------------------------------------


@dataclass(frozen=True)
class PageDrawing:
    """Something drawn or marked that is on a page, with all it is made of."""

    kind: str  # one of DRAWING_KINDS or of commands.MARKUP_KINDS
    page: int
    name: str
    rect: Rect  # the room it takes, as the page is shown
    strokes: tuple[tuple[Point, ...], ...]  # ink: its strokes; a shape: (start, end)
    color: Color
    width: float = DEFAULT_WIDTH
    opacity: float = 1.0
    rects: tuple[Rect, ...] = ()  # a text mark: one rectangle per line

    @property
    def ours(self) -> bool:
        """Made by this program: it can be removed."""
        return self.name.startswith(NAME_PREFIX)

    def order(self) -> Command:
        """The order that would put it as it is."""
        if self.kind in MARKUP_KINDS:
            mark = Mark(self.page, self.rects, self.name)
            return AddMarkup(self.kind, (mark,), self.color, self.opacity)
        if self.kind == INK:
            return AddInk(self.page, self.strokes, self.color, self.width, self.opacity, self.name)
        start, end = self.strokes[0]
        return AddShape(
            self.kind, self.page, start, end, self.color, self.width, self.opacity, self.name
        )

    def touches(self, x: float, y: float, reach: float = 3.0) -> bool:
        """Whether a point of the page is on it (on its line, not in its hollow)."""
        near = reach + self.width / 2
        if self.kind in MARKUP_KINDS:
            return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in self.rects)
        x0, y0, x1, y1 = self.rect
        if not (x0 - near <= x <= x1 + near and y0 - near <= y <= y1 + near):
            return False
        if self.kind == BOX:
            inside = x0 + near < x < x1 - near and y0 + near < y < y1 - near
            return not inside
        if self.kind == OVAL:
            return _near_oval(self.rect, x, y, near)
        return any(
            _to_segment((x, y), first, second) <= near
            for stroke in self.strokes
            for first, second in zip(stroke, stroke[1:], strict=False)
        )


def _to_segment(point: Point, first: Point, second: Point) -> float:
    """Distance from a point to the piece of line between two others."""
    (px, py), (ax, ay), (bx, by) = point, first, second
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    if length == 0:
        return math.dist(point, first)
    along = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.dist(point, (ax + along * dx, ay + along * dy))


def _near_oval(rect: Rect, x: float, y: float, near: float) -> bool:
    x0, y0, x1, y1 = rect
    half_w, half_h = max((x1 - x0) / 2, 0.01), max((y1 - y0) / 2, 0.01)
    dx, dy = x - (x0 + x1) / 2, y - (y0 + y1) / 2

    def level(grow: float) -> float:
        a, b = max(half_w + grow, 0.01), max(half_h + grow, 0.01)
        return (dx / a) ** 2 + (dy / b) ** 2

    outside_inner = min(half_w, half_h) <= near or level(-near) >= 1.0
    return level(near) <= 1.0 and outside_inner


def _shown(page, point) -> Point:
    import pymupdf

    turned = pymupdf.Point(point) * page.rotation_matrix
    return (turned.x, turned.y)


def _common(annotation) -> tuple[Color, float, float]:
    colors = annotation.colors or {}
    stroke = colors.get("stroke") or (0.0, 0.0, 0.0)
    color = _color(stroke) if len(stroke) == 3 else (0.0, 0.0, 0.0)
    width = (annotation.border or {}).get("width", DEFAULT_WIDTH)
    opacity = annotation.opacity
    return color, clamp_width(width), 1.0 if opacity is None or opacity < 0 else float(opacity)


def page_drawings(doc, page_number: int) -> list[PageDrawing]:
    """What is drawn or marked on a page, by this program or by any other."""
    import pymupdf

    found: list[PageDrawing] = []
    page = doc[page_number]
    for annotation in page.annots() or ():
        kind = annotation.type[1]
        name = str(annotation.info.get("id") or "")
        color, width, opacity = _common(annotation)
        whole = (annotation.rect * page.rotation_matrix).normalize()
        rect = (whole.x0, whole.y0, whole.x1, whole.y1)
        vertices = annotation.vertices or []
        if kind == "Ink":
            strokes = tuple(tuple(_shown(page, p) for p in stroke) for stroke in vertices)
            found.append(PageDrawing(INK, page_number, name, rect, strokes, color, width, opacity))
        elif kind == "Line" and len(vertices) == 2:
            ends = (_shown(page, vertices[0]), _shown(page, vertices[1]))
            arrow = annotation.line_ends[1] != pymupdf.PDF_ANNOT_LE_NONE
            shape = ARROW if arrow else LINE
            found.append(
                PageDrawing(shape, page_number, name, rect, (ends,), color, width, opacity)
            )
        elif kind in ("Square", "Circle"):
            inner = (
                whole.x0 + _BOX_PADDING,
                whole.y0 + _BOX_PADDING,
                whole.x1 - _BOX_PADDING,
                whole.y1 - _BOX_PADDING,
            )
            corners = ((inner[0], inner[1]), (inner[2], inner[3]))
            shape = BOX if kind == "Square" else OVAL
            found.append(
                PageDrawing(shape, page_number, name, inner, (corners,), color, width, opacity)
            )
        elif kind in _MARKUP_TYPES and len(vertices) >= 4:
            rects = []
            for index in range(0, len(vertices) - 3, 4):
                corners = [_shown(page, p) for p in vertices[index : index + 4]]
                xs, ys = [c[0] for c in corners], [c[1] for c in corners]
                rects.append((min(xs), min(ys), max(xs), max(ys)))
            found.append(
                PageDrawing(
                    _MARKUP_TYPES[kind],
                    page_number,
                    name,
                    rect,
                    (),
                    color,
                    width,
                    opacity,
                    tuple(rects),
                )
            )
    return found


_MARKUP_TYPES = {"Highlight": "highlight", "Underline": "underline", "StrikeOut": "strikeout"}


def drawing_at(drawings: list[PageDrawing], x: float, y: float, reach: float = 3.0):
    """What is drawn under a point of the page (the last one drawn wins)."""
    for drawing in reversed(drawings):
        if drawing.touches(x, y, reach):
            return drawing
    return None
