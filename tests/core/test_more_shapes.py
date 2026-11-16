"""Tests for the shapes added after the first test of Phase 2: double and elbow
arrows, triangles, rhombuses and braces, filled or with a dashed line."""

from dataclasses import replace

import pymupdf
import pytest

from app.core import arrange
from app.core.commands import command_from_dict
from app.core.drawing import (
    ARROW,
    BOX,
    BRACE,
    DOUBLE_ARROW,
    ELBOW,
    FILLABLE,
    LINE_SHAPES,
    OVAL,
    RHOMBUS,
    SHAPES,
    TRIANGLE,
    drawing_at,
    fill_tone,
    new_shape,
    page_drawings,
    shape_points,
)
from app.core.notes import Replace

RED = (0.85, 0.15, 0.15)
PAGE = (595.0, 842.0)


@pytest.fixture
def doc():
    document = pymupdf.open()
    document.new_page(width=PAGE[0], height=PAGE[1])
    page = document[0]
    page.insert_text((110, 125), "Texto que queda debajo", fontsize=12)
    yield document
    document.close()


def put(doc, kind, start=(100, 100), end=(200, 160), **look):
    order = new_shape(kind, 0, start, end, RED, 2.0, 1.0, **look)
    order.apply(doc)
    return order


def same(first, second) -> bool:
    """The same shape, allowing for the rounding of numbers inside the PDF."""
    if replace(first, color=second.color, start=second.start, end=second.end) != second:
        return False
    numbers = [*first.color, *first.start, *first.end]
    others = [*second.color, *second.start, *second.end]
    return numbers == pytest.approx(others, abs=0.01)


def read(doc):
    (drawing,) = page_drawings(doc, 0)
    return drawing


@pytest.mark.parametrize("kind", SHAPES)
def test_every_shape_is_put_and_read_back_as_it_was(doc, kind):
    order = put(doc, kind)
    drawing = read(doc)
    assert drawing.kind == kind and drawing.ours
    assert same(drawing.order(), order)
    assert command_from_dict(order.to_dict()) == order
    order.undo(doc)
    assert page_drawings(doc, 0) == []


@pytest.mark.parametrize(
    ("kind", "subtype"),
    [
        (DOUBLE_ARROW, "Line"),
        (ELBOW, "PolyLine"),
        (TRIANGLE, "Polygon"),
        (RHOMBUS, "Polygon"),
        (BRACE, "PolyLine"),
    ],
)
def test_they_are_standard_annotations(doc, kind, subtype):
    put(doc, kind)
    page = doc[0]
    (annotation,) = page.annots()
    assert annotation.type[1] == subtype
    assert annotation.xref and doc.xref_get_key(annotation.xref, "AP/N")[0] == "xref"


def test_the_arrows_have_their_heads(doc):
    put(doc, DOUBLE_ARROW)
    put(doc, ELBOW, (100, 300), (200, 380))
    page = doc[0]
    ends = {a.type[1]: a.line_ends for a in page.annots()}
    arrow = pymupdf.PDF_ANNOT_LE_OPEN_ARROW
    assert ends["Line"] == (arrow, arrow)
    assert ends["PolyLine"] == (pymupdf.PDF_ANNOT_LE_NONE, arrow)


def test_an_arrow_made_elsewhere_pointing_back_is_read_the_right_way(doc):
    page = doc[0]
    line = page.add_line_annot((100, 100), (200, 100))
    line.set_line_ends(pymupdf.PDF_ANNOT_LE_OPEN_ARROW, pymupdf.PDF_ANNOT_LE_NONE)
    line.update()
    drawing = read(doc)
    assert drawing.kind == ARROW and drawing.strokes[0][1] == pytest.approx((100, 100))


def test_the_corners_of_each_shape():
    assert shape_points(TRIANGLE, (100, 100), (200, 160)) == [(150, 100), (200, 160), (100, 160)]
    assert shape_points(TRIANGLE, (200, 160), (100, 100))[0] == (150, 100), "always pointing up"
    assert shape_points(RHOMBUS, (100, 100), (200, 160)) == [
        (150, 100),
        (200, 130),
        (150, 160),
        (100, 130),
    ]
    assert shape_points(ELBOW, (100, 100), (200, 160)) == [(100, 100), (200, 100), (200, 160)]


def test_a_brace_has_its_tip_on_the_side_it_was_started_from():
    opening = shape_points(BRACE, (100, 100), (130, 300))  # left to right: "{"
    tip = min(opening, key=lambda p: p[0])
    assert tip[0] == pytest.approx(100) and tip[1] == pytest.approx(200)
    assert opening[0] == pytest.approx((130, 100)) and opening[-1] == pytest.approx((130, 300))
    closing = shape_points(BRACE, (130, 100), (100, 300))  # right to left: "}"
    assert max(closing, key=lambda p: p[0])[0] == pytest.approx(130)
    lying = shape_points(BRACE, (100, 100), (300, 120))  # wider than tall: lies down
    assert min(lying, key=lambda p: p[1]) == pytest.approx((200, 100))


def test_a_filled_shape_lets_the_text_underneath_be_read(doc):
    put(doc, BOX, (100, 110), (300, 135), fill=True)
    page = doc[0]
    (annotation,) = page.annots()
    assert annotation.colors["fill"] == pytest.approx(fill_tone(RED), abs=0.01)
    assert annotation.blendmode == "Multiply"
    assert read(doc).fill
    # Where the text is, the page still has dark letters.
    picture = page.get_pixmap(clip=(110, 113, 270, 128), dpi=72)
    assert min(picture.samples) < 90


@pytest.mark.parametrize("kind", [k for k in SHAPES if k not in FILLABLE])
def test_only_closed_shapes_are_filled(kind):
    assert not new_shape(kind, 0, (100, 100), (200, 160), fill=True).fill


def test_a_dashed_line(doc):
    put(doc, TRIANGLE, dashed=True)
    page = doc[0]
    (annotation,) = page.annots()
    assert annotation.border["dashes"]
    drawing = read(doc)
    assert drawing.dashed and not drawing.fill


def test_inside_a_filled_shape_is_on_it(doc):
    put(doc, RHOMBUS, (100, 100), (200, 200), fill=True)
    put(doc, TRIANGLE, (300, 100), (400, 200))
    drawings = page_drawings(doc, 0)
    assert drawing_at(drawings, 150, 150).kind == RHOMBUS, "filled: its middle"
    assert drawing_at(drawings, 350, 170) is None, "hollow: only its line"
    assert drawing_at(drawings, 350, 200).kind == TRIANGLE
    assert drawing_at(drawings, 325, 150).kind == TRIANGLE, "on a sloping side"


def test_a_brace_and_an_elbow_are_found_by_their_line(doc):
    put(doc, BRACE, (100, 100), (130, 300))
    put(doc, ELBOW, (300, 100), (400, 200))
    drawings = page_drawings(doc, 0)
    assert drawing_at(drawings, 100, 200).kind == BRACE, "its tip"
    assert drawing_at(drawings, 125, 150) is None, "not the empty part of its frame"
    assert drawing_at(drawings, 350, 100).kind == ELBOW
    assert drawing_at(drawings, 400, 150).kind == ELBOW
    assert drawing_at(drawings, 330, 170) is None


@pytest.mark.parametrize("kind", SHAPES)
def test_they_move_and_resize(doc, kind):
    order = put(doc, kind)
    change = arrange.moved(order, 50, 20, PAGE)
    assert change.new.start == (150, 120)
    grips = arrange.handles(order)
    assert len(grips) == (2 if kind in LINE_SHAPES else 4)
    change = arrange.resized(order, len(grips) - 2, (260, 220), PAGE)
    assert isinstance(change, Replace)
    change.apply(doc)
    assert same(read(doc).order(), change.new)


def test_a_brace_keeps_its_side_when_resized():
    order = new_shape(BRACE, 0, (130, 100), (100, 300))  # "}"
    change = arrange.resized(order, arrange.BOTTOM_RIGHT, (160, 320), PAGE)
    (sx, _), (ex, _) = change.new.start, change.new.end
    assert sx > ex, "still a closing brace"


def test_fill_and_dash_survive_a_move_and_a_copy(doc):
    order = put(doc, OVAL, fill=True, dashed=True)
    moved = arrange.moved(order, 10, 10, PAGE).new
    assert moved.fill and moved.dashed
    copy = arrange.copy_of(order, 0, PAGE)
    assert copy.fill and copy.dashed and copy.name != order.name


def test_on_a_turned_page(doc):
    doc[0].set_rotation(90)
    order = put(doc, TRIANGLE, (100, 100), (200, 160))
    drawing = read(doc)
    assert same(drawing.order(), order)
