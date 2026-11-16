"""Drawing on the page: freehand strokes, lines, arrows, boxes, ovals and more.

All of them are ordinary PDF annotations ("Ink", "Line", "Square", "Circle",
"Polygon" and "PolyLine"), so Adobe Reader, Edge and any other viewer show them
the same. A closed shape can be filled with a light tone of its colour that
lets the text underneath be read (it is mixed like a highlighter), and any
shape can be drawn with a dashed line. Each
one is put by an order, like every other change, and read back from the
document by ``page_drawings`` with all it is made of, so that the eraser can
take it away (and undo can bring it back exactly as it was).

``page_drawings`` also reads the highlights, underlines and strike-outs, for
the same eraser.

A stroke made with a pen that feels pressure is thicker where the hand
pressed more. A standard "Ink" annotation has one thickness only, so such a
stroke is still a standard one (with its points and its usual thickness) that
also carries its look drawn: the "appearance" every viewer shows. How hard the
pen pressed at each point is kept in the annotation too, under a key of this
program, to put the stroke again just the same after moving or erasing it.
"""

import math
import re
from dataclasses import dataclass, replace

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
from app.core.foreign import OTHER, OTHER_TYPES, Foreign, families_of, foreign_of, key_of
from app.core.search import Rect

INK = "ink"
LINE = "line"
ARROW = "arrow"
DOUBLE_ARROW = "double_arrow"
ELBOW = "elbow"  # an arrow that goes across and then up or down
BOX = "box"
OVAL = "oval"
TRIANGLE = "triangle"
RHOMBUS = "rhombus"
BRACE = "brace"  # a curly bracket, "{", that groups what is next to it
SHAPES = (ARROW, DOUBLE_ARROW, ELBOW, LINE, BOX, OVAL, TRIANGLE, RHOMBUS, BRACE)
# Drawn from one end to the other; the rest fill the frame between two corners.
LINE_SHAPES = (LINE, ARROW, DOUBLE_ARROW, ELBOW)
FRAMED_SHAPES = (BOX, OVAL, TRIANGLE, RHOMBUS, BRACE)
# The ones that close and can be filled.
FILLABLE = (BOX, OVAL, TRIANGLE, RHOMBUS)
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
# With pressure, a stroke goes from this much to this much of its thickness.
THINNEST, THICKEST = 0.35, 1.65
PRESSURE_KEY = "LectorPDFPressure"  # where the annotation keeps the pressures
# Polygons and broken lines keep what they are and the two points they were
# drawn between (the PDF only knows their corners).
SHAPE_KEY = "LectorPDFShape"
ENDS_KEY = "LectorPDFEnds"
FILL_LIGHTNESS = 0.72  # how much white the fill has (the rest is the colour)
_CIRCLE = 0.5523  # how far the handles of a Bézier quarter of circle go
_NUMBER = re.compile(r"-?\d*\.?\d+")
_LIST = re.compile(r"\[([^\[\]]*)\]")


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
    # How hard the pen pressed at each point of each stroke, from 0 to 1.
    # Empty: drawn with a mouse, or with pressure turned off.
    pressures: tuple[tuple[float, ...], ...] = ()

    def pages(self) -> list[int]:
        return [self.page]

    @property
    def pressed(self) -> bool:
        """Whether it has a pressure for every point (and so a thickness that varies)."""
        return len(self.pressures) == len(self.strokes) and all(
            len(pressed) == len(stroke)
            for pressed, stroke in zip(self.pressures, self.strokes, strict=True)
        )

    def apply(self, doc) -> list[int]:
        import pymupdf

        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                kept = [index for index, stroke in enumerate(self.strokes) if len(stroke) >= 2]
                turned = [
                    [
                        tuple(pymupdf.Point(point) * page.derotation_matrix)
                        for point in self.strokes[index]
                    ]
                    for index in kept
                ]
                if not turned:
                    raise CommandError("there is nothing drawn")
                annotation = page.add_ink_annot(turned)
                annotation.set_border(width=clamp_width(self.width))
                annotation.set_colors(stroke=self.color)
                annotation.set_opacity(max(0.05, _unit(self.opacity)))
                annotation.update()
                _name_it(doc, annotation, self.name)
                if self.pressed:
                    pressures = [self.pressures[index] for index in kept]
                    _draw_pressed(doc, annotation, pressures, clamp_width(self.width), self.color)
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
        } | ({"pressures": [list(pressed) for pressed in self.pressures]} if self.pressures else {})

    @classmethod
    def from_dict(cls, data: dict) -> "AddInk":
        return cls(
            int(data["page"]),
            tuple(_points(stroke) for stroke in data["strokes"]),
            _color(data["color"]),
            float(data["width"]),
            float(data.get("opacity", 1.0)),
            str(data["name"]),
            tuple(
                tuple(_unit(value) for value in pressed) for pressed in data.get("pressures", ())
            ),
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
    fill: bool = False  # a closed shape: filled with a light tone of its colour
    dashed: bool = False

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        if self.kind not in SHAPES:
            raise CommandError(f"unknown shape: {self.kind}")
        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                turn = page.derotation_matrix
                first = pymupdf.Point(self.start) * turn
                last = pymupdf.Point(self.end) * turn
                none, arrow = pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_OPEN_ARROW
                if self.kind in (LINE, ARROW, DOUBLE_ARROW):
                    annotation = page.add_line_annot(first, last)
                    if self.kind != LINE:
                        start_end = arrow if self.kind == DOUBLE_ARROW else none
                        annotation.set_line_ends(start_end, arrow)
                elif self.kind in (BOX, OVAL):
                    rect = pymupdf.Rect(first, last).normalize()
                    add = page.add_rect_annot if self.kind == BOX else page.add_circle_annot
                    annotation = add(rect)
                else:
                    corners = [
                        pymupdf.Point(point) * turn
                        for point in shape_points(self.kind, self.start, self.end)
                    ]
                    if self.kind in (TRIANGLE, RHOMBUS):
                        annotation = page.add_polygon_annot(corners)
                    else:
                        annotation = page.add_polyline_annot(corners)
                        if self.kind == ELBOW:
                            annotation.set_line_ends(none, arrow)
                width = clamp_width(self.width)
                if self.dashed:
                    dash, gap = max(3, round(3 * width)), max(2, round(2 * width))
                    annotation.set_border(width=width, dashes=[dash, gap])
                else:
                    annotation.set_border(width=width)
                if self.fill and self.kind in FILLABLE:
                    annotation.set_colors(stroke=self.color, fill=fill_tone(self.color))
                    # Mixed like a highlighter: the text underneath is still read.
                    annotation.set_blendmode(pymupdf.PDF_BM_Multiply)
                else:
                    annotation.set_colors(stroke=self.color)
                annotation.set_opacity(max(0.05, _unit(self.opacity)))
                annotation.update()
                _name_it(doc, annotation, self.name)
                if self.kind not in (LINE, ARROW, DOUBLE_ARROW, BOX, OVAL):
                    ends = [*(pymupdf.Point(self.start) * turn), *(pymupdf.Point(self.end) * turn)]
                    doc.xref_set_key(annotation.xref, SHAPE_KEY, f"/{self.kind}")
                    numbers = " ".join(f"{value:.3f}" for value in ends)
                    doc.xref_set_key(annotation.xref, ENDS_KEY, f"[{numbers}]")
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(f"cannot draw the shape: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        return _remove(doc, self.page, self.name)

    def to_dict(self) -> dict:
        return (
            {
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
            | ({"fill": True} if self.fill else {})
            | ({"dashed": True} if self.dashed else {})
        )

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
            data.get("fill") is True,
            data.get("dashed") is True,
        )


def fill_tone(color: Color) -> Color:
    """The light tone a shape is filled with."""
    return tuple(FILL_LIGHTNESS + (1 - FILL_LIGHTNESS) * part for part in color)


def _quadratic(first: Point, control: Point, last: Point, steps: int = 8) -> list[Point]:
    """Points along a curve from ``first`` to ``last`` pulled towards ``control``."""
    points = []
    for step in range(1, steps + 1):
        t = step / steps
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        points.append(
            (
                a * first[0] + b * control[0] + c * last[0],
                a * first[1] + b * control[1] + c * last[1],
            )
        )
    return points


def _brace(length: float, across: float) -> list[Point]:
    """A curly bracket lying along ``length``, its tip at across 0 and its arms at
    ``across``, as (along, across) points."""
    half, bend = across / 2, min(across / 2, length * 0.12)
    middle = length / 2
    points: list[Point] = [(0.0, across)]
    points += _quadratic((0.0, across), (0.0, half), (bend, half))
    points.append((middle - bend, half))
    points += _quadratic((middle - bend, half), (middle, half), (middle, 0.0))
    points += _quadratic((middle, 0.0), (middle, half), (middle + bend, half))
    points.append((length - bend, half))
    points += _quadratic((length - bend, half), (length, half), (length, across))
    return points


def straightened(kind: str, start: Point, end: Point) -> Point:
    """Where ``end`` goes with Shift held: a line keeps to steps of 45 degrees,
    and a frame is as wide as it is tall (a square, a circle)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if kind in FRAMED_SHAPES:
        side = max(abs(dx), abs(dy))
        return (start[0] + math.copysign(side, dx or 1), start[1] + math.copysign(side, dy or 1))
    if kind == ELBOW:
        return end
    length = math.hypot(dx, dy)
    angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
    return (start[0] + length * math.cos(angle), start[1] + length * math.sin(angle))


def shape_points(kind: str, start: Point, end: Point) -> list[Point]:
    """The corners a shape is drawn through, as the page is shown.

    A triangle points up and a rhombus stands on a corner, in the frame from
    ``start`` to ``end``. An elbow goes across from ``start`` and then up or
    down to ``end``. A brace has its tip on the side it was started from: from
    left to right it is "{", the other way "}"; in a frame wider than tall it
    lies down.
    """
    (sx, sy), (ex, ey) = start, end
    x0, x1 = sorted((sx, ex))
    y0, y1 = sorted((sy, ey))
    if kind == TRIANGLE:
        return [((x0 + x1) / 2, y0), (x1, y1), (x0, y1)]
    if kind == RHOMBUS:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return [(mx, y0), (x1, my), (mx, y1), (x0, my)]
    if kind == ELBOW:
        return [start, (ex, sy), end]
    if kind == BRACE:
        if y1 - y0 >= x1 - x0:  # standing
            way = 1.0 if sx <= ex else -1.0
            return [(sx + way * across, y0 + along) for along, across in _brace(y1 - y0, x1 - x0)]
        way = 1.0 if sy <= ey else -1.0
        return [(x0 + along, sy + way * across) for along, across in _brace(x1 - x0, y1 - y0)]
    if kind in (BOX, OVAL):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [start, end]


register_reader("add_ink", AddInk.from_dict)
register_reader("add_shape", AddShape.from_dict)


def new_ink(
    page: int,
    strokes,
    color: Color = DRAW_COLOR,
    width: float = DEFAULT_WIDTH,
    opacity: float = 1.0,
    pressures=(),
) -> AddInk:
    """The order for a drawing. ``pressures``, if given, has one list per
    stroke with how hard the pen pressed at each of its points (0 to 1)."""
    kept = tuple(_points(stroke) for stroke in strokes)
    pressed = tuple(tuple(_unit(value) for value in stroke) for stroke in pressures)
    return AddInk(page, kept, color, clamp_width(width), opacity, new_name(), pressed)


def new_shape(
    kind: str,
    page: int,
    start: Point,
    end: Point,
    color: Color = SHAPE_COLOR,
    width: float = DEFAULT_WIDTH,
    opacity: float = 1.0,
    fill: bool = False,
    dashed: bool = False,
) -> AddShape | None:
    """The order for a shape, or None if it is too small to be meant."""
    (start, end) = _points((start, end))
    if math.dist(start, end) < MIN_SHAPE:
        return None
    fill = bool(fill) and kind in FILLABLE
    return AddShape(
        kind, page, start, end, color, clamp_width(width), opacity, new_name(), fill, bool(dashed)
    )


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


def thinned_stroke(points, pressures, apart: float = 0.7):
    """Like ``thinned``, for a stroke with a pressure at each point: both come
    back with the same points dropped."""
    points = _points(points)
    pressures = [_unit(value) for value in pressures]
    if len(points) != len(pressures):
        return thinned(points, apart), ()
    if len(points) < 3:
        return points, tuple(pressures)
    kept = [0]
    for index in range(1, len(points) - 1):
        if math.dist(points[index], points[kept[-1]]) >= apart:
            kept.append(index)
    kept.append(len(points) - 1)
    return tuple(points[i] for i in kept), tuple(pressures[i] for i in kept)


# ---- a stroke that is thicker where the pen pressed more ---------------------------


FELT = 0.03  # less difference of pressure than this along a stroke is none at all


def felt(pressures) -> bool:
    """Whether the pen really told how hard it pressed along a stroke.

    A pen that does not feel pressure says the same number all the time: its
    strokes are plain ones, with the thickness that was chosen.
    """
    values = [_unit(value) for value in pressures]
    return len(values) >= 2 and max(values) - min(values) >= FELT


def half_widths(pressures, width: float) -> list[float]:
    """Half the thickness of a stroke at each point, from how hard the pen pressed.

    Neighbours are evened out a little, so a trembling pressure does not
    leave lumps.
    """
    pressed = [_unit(value) for value in pressures]
    smooth = []
    for index, value in enumerate(pressed):
        around = pressed[max(0, index - 1) : index + 2]
        smooth.append((value + sum(around)) / (1 + len(around)))
    return [width / 2 * (THINNEST + (THICKEST - THINNEST) * value) for value in smooth]


def pressed_shape(points, radii) -> tuple[list[tuple[Point, Point, Point, Point]], list]:
    """What a stroke of varying thickness is made of: a four-sided piece from
    each point to the next and a disc ``(x, y, radius)`` on each point.

    Filled all together they are the stroke. Every piece goes round the same
    way, so that where they overlap they add up instead of leaving a hole.
    """
    points = _points(points)
    pieces = []
    for index in range(len(points) - 1):
        first, second = points[index], points[index + 1]
        r0, r1 = radii[index], radii[index + 1]
        length = math.dist(first, second)
        if length < 1e-6:
            continue
        nx, ny = -(second[1] - first[1]) / length, (second[0] - first[0]) / length
        piece = (
            (first[0] + nx * r0, first[1] + ny * r0),
            (second[0] + nx * r1, second[1] + ny * r1),
            (second[0] - nx * r1, second[1] - ny * r1),
            (first[0] - nx * r0, first[1] - ny * r0),
        )
        if _area(piece) < 0:
            piece = piece[::-1]
        pieces.append(piece)
    discs = [(x, y, radius) for (x, y), radius in zip(points, radii, strict=True)]
    return pieces, discs


def _area(corners) -> float:
    """Twice the area inside, positive when the corners go round one way."""
    return sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(corners, (*corners[1:], corners[0]), strict=True)
    )


def _draw_pressed(doc, annotation, pressures, width: float, color: Color) -> None:
    """Give an ink annotation the look of a stroke of varying thickness, and
    keep in it the pressures it was made with."""
    written = doc.xref_get_key(annotation.xref, "InkList")[1]
    look = doc.xref_get_key(annotation.xref, "AP/N")
    strokes = [
        [float(number) for number in _NUMBER.findall(stroke)] for stroke in _LIST.findall(written)
    ]
    if look[0] != "xref" or len(strokes) != len(pressures):
        return  # not the annotation that was expected: its plain look stays
    parts = ["q", "/H gs", "{:g} {:g} {:g} rg".format(*color)]
    for numbers, pressed in zip(strokes, pressures, strict=True):
        points = list(zip(numbers[0::2], numbers[1::2], strict=True))
        if len(points) != len(pressed):
            return
        pieces, discs = pressed_shape(points, half_widths(pressed, width))
        for piece in pieces:
            (x0, y0), *others = piece
            parts.append(
                f"{x0:.2f} {y0:.2f} m " + " ".join(f"{x:.2f} {y:.2f} l" for x, y in others) + " h"
            )
        for x, y, r in discs:
            k = r * _CIRCLE
            parts.append(
                f"{x + r:.2f} {y:.2f} m "
                f"{x + r:.2f} {y + k:.2f} {x + k:.2f} {y + r:.2f} {x:.2f} {y + r:.2f} c "
                f"{x - k:.2f} {y + r:.2f} {x - r:.2f} {y + k:.2f} {x - r:.2f} {y:.2f} c "
                f"{x - r:.2f} {y - k:.2f} {x - k:.2f} {y - r:.2f} {x:.2f} {y - r:.2f} c "
                f"{x + k:.2f} {y - r:.2f} {x + r:.2f} {y - k:.2f} {x + r:.2f} {y:.2f} c h"
            )
    parts += ["f", "Q", ""]
    doc.update_stream(int(look[1].split()[0]), "\n".join(parts).encode("ascii"))
    kept = " ".join(
        "[" + " ".join(f"{value:.2f}" for value in stroke) + "]" for stroke in pressures
    )
    doc.xref_set_key(annotation.xref, PRESSURE_KEY, f"[{kept}]")


def _read_pressures(doc, xref: int, strokes) -> tuple[tuple[float, ...], ...]:
    """The pressures an ink annotation keeps, if they fit its strokes."""
    kind, written = doc.xref_get_key(xref, PRESSURE_KEY)
    if kind != "array":
        return ()
    found = tuple(
        tuple(_unit(float(number)) for number in _NUMBER.findall(stroke))
        for stroke in _LIST.findall(written)
    )
    if len(found) != len(strokes):
        return ()
    if any(len(pressed) != len(stroke) for pressed, stroke in zip(found, strokes, strict=True)):
        return ()
    return found


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
    pressures: tuple[tuple[float, ...], ...] = ()  # ink drawn with a pen that feels it
    fill: bool = False  # a shape filled with a light tone of its colour
    dashed: bool = False
    foreign: Foreign | None = None  # made by another program: only taken away

    @property
    def ours(self) -> bool:
        """Made by this program: it can be removed."""
        return self.name.startswith(NAME_PREFIX)

    @property
    def removable(self) -> bool:
        """It can be taken away: made here, or by another program."""
        return self.ours or self.foreign is not None

    def order(self) -> Command:
        """The order that would put it as it is."""
        if self.foreign is not None:
            return self.foreign
        if self.kind in MARKUP_KINDS:
            mark = Mark(self.page, self.rects, self.name)
            return AddMarkup(self.kind, (mark,), self.color, self.opacity)
        if self.kind == INK:
            return AddInk(
                self.page,
                self.strokes,
                self.color,
                self.width,
                self.opacity,
                self.name,
                self.pressures,
            )
        start, end = self.strokes[0]
        return AddShape(
            self.kind,
            self.page,
            start,
            end,
            self.color,
            self.width,
            self.opacity,
            self.name,
            self.fill,
            self.dashed,
        )

    def touches(self, x: float, y: float, reach: float = 3.0) -> bool:
        """Whether a point of the page is on it (on its line, not in its hollow)."""
        near = reach + self.width / 2 * (THICKEST if self.pressures else 1.0)
        if self.kind in MARKUP_KINDS:
            return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in self.rects)
        x0, y0, x1, y1 = self.rect
        if self.kind == OTHER:  # only its place is known: anywhere on it
            return x0 - reach <= x <= x1 + reach and y0 - reach <= y <= y1 + reach
        if not (x0 - near <= x <= x1 + near and y0 - near <= y <= y1 + near):
            return False
        if self.kind == BOX:
            inside = x0 + near < x < x1 - near and y0 + near < y < y1 - near
            return self.fill or not inside
        if self.kind == OVAL:
            return _near_oval(self.rect, x, y, near) or (
                self.fill and _near_oval(self.rect, x, y, 0.0)
            )
        if self.kind in (TRIANGLE, RHOMBUS, ELBOW, BRACE):
            start, end = self.strokes[0]
            corners = shape_points(self.kind, start, end)
            closed = self.kind in (TRIANGLE, RHOMBUS)
            if closed and self.fill and _in_polygon((x, y), corners):
                return True
            pairs = zip(corners, corners[1:] + corners[:1] if closed else corners[1:], strict=False)
            return any(_to_segment((x, y), first, second) <= near for first, second in pairs)
        return any(
            _to_segment((x, y), first, second) <= near
            for stroke in self.strokes
            for first, second in zip(stroke, stroke[1:], strict=False)
        )


def _in_polygon(point: Point, corners: list[Point]) -> bool:
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1], strict=True):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


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


def _look(annotation) -> tuple[bool, bool]:
    """Whether a shape is filled and whether its line is dashed."""
    fill = bool((annotation.colors or {}).get("fill"))
    dashed = bool((annotation.border or {}).get("dashes"))
    return fill, dashed


def _our_shape(doc, page, annotation) -> tuple[str, tuple[Point, Point]] | None:
    """A polygon or a broken line made here: what it is and its two points."""
    kind = doc.xref_get_key(annotation.xref, SHAPE_KEY)
    ends = doc.xref_get_key(annotation.xref, ENDS_KEY)
    if kind[0] != "name" or ends[0] != "array":
        return None
    numbers = [float(n) for n in _NUMBER.findall(ends[1])]
    shape = kind[1].lstrip("/")
    if shape not in SHAPES or len(numbers) != 4:
        return None
    return shape, (_shown(page, numbers[:2]), _shown(page, numbers[2:]))


def page_drawings(doc, page_number: int) -> list[PageDrawing]:
    """What is drawn or marked on a page, by this program or by any other."""
    import pymupdf

    found: list[PageDrawing] = []
    page = doc[page_number]
    families = None  # read when the first annotation of another program comes
    for annotation in page.annots() or ():
        before = len(found)
        kind = annotation.type[1]
        name = str(annotation.info.get("id") or "")
        color, width, opacity = _common(annotation)
        whole = (annotation.rect * page.rotation_matrix).normalize()
        rect = (whole.x0, whole.y0, whole.x1, whole.y1)
        vertices = annotation.vertices or []
        if kind == "Ink":
            strokes = tuple(tuple(_shown(page, p) for p in stroke) for stroke in vertices)
            pressures = _read_pressures(doc, annotation.xref, strokes)
            found.append(
                PageDrawing(
                    INK, page_number, name, rect, strokes, color, width, opacity, (), pressures
                )
            )
        elif kind == "Line" and len(vertices) == 2:
            ends = (_shown(page, vertices[0]), _shown(page, vertices[1]))
            at_start, at_end = (end != pymupdf.PDF_ANNOT_LE_NONE for end in annotation.line_ends)
            if at_start and at_end:
                shape = DOUBLE_ARROW
            elif at_start or at_end:
                shape = ARROW
                if at_start:  # made elsewhere, pointing back: the same arrow
                    ends = (ends[1], ends[0])
            else:
                shape = LINE
            found.append(
                PageDrawing(
                    shape,
                    page_number,
                    name,
                    rect,
                    (ends,),
                    color,
                    width,
                    opacity,
                    (),
                    (),
                    False,
                    _look(annotation)[1],
                )
            )
        elif kind in ("Polygon", "PolyLine"):
            ours = _our_shape(doc, page, annotation)
            if ours is not None:
                shape, ends = ours
                fill, dashed = _look(annotation)
                found.append(
                    PageDrawing(
                        shape,
                        page_number,
                        name,
                        rect,
                        (ends,),
                        color,
                        width,
                        opacity,
                        (),
                        (),
                        fill,
                        dashed,
                    )
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
            fill, dashed = _look(annotation)
            found.append(
                PageDrawing(
                    shape,
                    page_number,
                    name,
                    inner,
                    (corners,),
                    color,
                    width,
                    opacity,
                    (),
                    (),
                    fill,
                    dashed,
                )
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
        if len(found) == before and kind in OTHER_TYPES:
            found.append(PageDrawing(OTHER, page_number, name, rect, (), color, width, opacity))
        if len(found) > before and not name.startswith(NAME_PREFIX):
            # Made by another program: known by its place in the document.
            families = families or families_of(doc, page_number)
            found[-1] = replace(
                found[-1],
                name=key_of(annotation.xref),
                foreign=foreign_of(doc, page_number, annotation, rect, families),
            )
    return found


_MARKUP_TYPES = {"Highlight": "highlight", "Underline": "underline", "StrikeOut": "strikeout"}


def drawing_at(drawings: list[PageDrawing], x: float, y: float, reach: float = 3.0):
    """What is drawn under a point of the page (the last one drawn wins)."""
    for drawing in reversed(drawings):
        if drawing.touches(x, y, reach):
            return drawing
    return None
