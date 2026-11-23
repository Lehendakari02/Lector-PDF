"""Tests for app.core.drawing: freehand strokes, lines, arrows, boxes and ovals."""

import pymupdf
import pytest

from app.core.commands import (
    HIGHLIGHT,
    STRIKEOUT,
    UNDERLINE,
    AddMarkup,
    CommandError,
    Mark,
    command_from_dict,
    new_name,
)
from app.core.drawing import (
    ARROW,
    BOX,
    DEFAULT_WIDTH,
    INK,
    LINE,
    OVAL,
    SHAPES,
    THICKEST,
    THINNEST,
    AddInk,
    AddShape,
    clamp_width,
    drawing_at,
    felt,
    half_widths,
    new_ink,
    new_shape,
    page_drawings,
    pressed_shape,
    thinned,
    thinned_stroke,
)
from app.core.notes import Remove

RED = (0.85, 0.15, 0.15)
STROKE = ((50.0, 50.0), (80.0, 60.0), (120.0, 40.0), (150.0, 90.0))


@pytest.fixture
def doc():
    document = pymupdf.open()
    document.new_page(width=400, height=300)
    turned = document.new_page(width=400, height=300)
    turned.set_rotation(90)
    yield document
    document.close()


def saved_again(document) -> pymupdf.Document:
    """The document as another program would find it in the file."""
    return pymupdf.open("pdf", document.tobytes())


def close_to(first, second, by: float = 0.01) -> bool:
    return all(abs(a - b) <= by for a, b in zip(first, second, strict=True))


def same_points(first, second) -> bool:
    return len(first) == len(second) and all(
        close_to(a, b) for a, b in zip(first, second, strict=True)
    )


def types(document, page: int = 0) -> list[str]:
    sheet = document[page]
    return [annotation.type[1] for annotation in sheet.annots() or ()]


# ---- drawing by hand -------------------------------------------------------------


def test_a_stroke_is_a_standard_ink_annotation(doc):
    order = new_ink(0, [STROKE], RED, 4, 0.5)
    assert order.apply(doc) == [0]
    with saved_again(doc) as again:
        page = again[0]
        (annotation,) = page.annots()
        assert annotation.type[1] == "Ink"
        assert same_points(annotation.vertices[0], STROKE)
        assert close_to(annotation.colors["stroke"], RED)
        assert annotation.border["width"] == 4
        assert annotation.opacity == pytest.approx(0.5)
        assert annotation.info["id"] == order.name


def test_a_stroke_is_seen_when_the_page_is_drawn(doc):
    before = doc[0].get_pixmap().samples
    new_ink(0, [STROKE], RED, 4).apply(doc)
    picture = doc[0].get_pixmap()
    assert picture.samples != before
    red, green, blue = picture.pixel(80, 60)
    assert red > 180 and green < 120 and blue < 120


def test_undo_takes_the_stroke_away_and_it_can_come_back(doc):
    order = new_ink(0, [STROKE])
    order.apply(doc)
    assert order.undo(doc) == [0]
    assert types(doc) == []
    order.apply(doc)
    order.apply(doc)  # twice is once
    assert types(doc) == ["Ink"]


def test_several_strokes_in_one_drawing(doc):
    second = ((200.0, 200.0), (220.0, 240.0))
    new_ink(0, [STROKE, second]).apply(doc)
    (found,) = page_drawings(doc, 0)
    assert len(found.strokes) == 2
    assert same_points(found.strokes[1], second)


def test_a_stroke_of_one_point_is_nothing(doc):
    with pytest.raises(CommandError):
        new_ink(0, [((10.0, 10.0),)]).apply(doc)
    assert types(doc) == []


def test_a_stroke_on_a_turned_page_is_read_where_it_was_drawn(doc):
    new_ink(1, [STROKE], RED, 2).apply(doc)
    (found,) = page_drawings(doc, 1)
    assert found.kind == INK and found.ours
    assert same_points(found.strokes[0], STROKE)
    x0, y0, x1, y1 = found.rect
    assert x0 <= 50 and x1 >= 150 and y0 <= 40 and y1 >= 90
    # And it is there in the picture of the page as it is shown.
    red, green, blue = doc[1].get_pixmap().pixel(80, 60)
    assert red > 180 and green < 120


def test_thinned_drops_points_on_top_of_each_other():
    crowded = [(0, 0), (0.1, 0), (0.2, 0), (5, 0), (5.1, 0.1), (9, 0), (9.2, 0)]
    assert thinned(crowded) == ((0.0, 0.0), (5.0, 0.0), (9.0, 0.0), (9.2, 0.0))
    assert thinned([(1, 1), (1.1, 1.1)]) == ((1.0, 1.0), (1.1, 1.1))


def test_the_thickness_is_always_usable():
    assert clamp_width(4) == 4
    assert clamp_width(0) == 0.5
    assert clamp_width(1000) == 24
    assert clamp_width("thick") == DEFAULT_WIDTH
    assert clamp_width(None) == DEFAULT_WIDTH
    assert clamp_width(float("nan")) == DEFAULT_WIDTH
    assert clamp_width(True) == DEFAULT_WIDTH


# ---- shapes ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "standard"),
    [(LINE, "Line"), (ARROW, "Line"), (BOX, "Square"), (OVAL, "Circle")],
)
def test_every_shape_is_a_standard_annotation(doc, kind, standard):
    order = new_shape(kind, 0, (60, 70), (200, 150), RED, 4, 0.8)
    order.apply(doc)
    with saved_again(doc) as again:
        page = again[0]
        (annotation,) = page.annots()
        assert annotation.type[1] == standard
        assert close_to(annotation.colors["stroke"], RED)
        assert annotation.border["width"] == 4
        assert annotation.opacity == pytest.approx(0.8)
        (found,) = page_drawings(again, 0)
    assert found.kind == kind and found.ours
    assert same_points(found.strokes[0], ((60, 70), (200, 150)))
    assert found.width == 4 and found.opacity == pytest.approx(0.8)
    assert close_to(found.color, RED)


def test_an_arrow_points_at_its_end(doc):
    new_shape(ARROW, 0, (60, 70), (200, 150)).apply(doc)
    page = doc[0]
    (annotation,) = page.annots()
    assert annotation.line_ends == (pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_OPEN_ARROW)
    assert close_to(annotation.vertices[1], (200, 150))


@pytest.mark.parametrize("kind", SHAPES)
def test_a_shape_on_a_turned_page_is_read_where_it_was_put(doc, kind):
    new_shape(kind, 1, (60, 70), (200, 150)).apply(doc)
    (found,) = page_drawings(doc, 1)
    assert found.kind == kind
    (x0, y0), (x1, y1) = found.strokes[0]
    assert close_to(sorted((x0, x1)), (60, 200)) and close_to(sorted((y0, y1)), (70, 150))
    if kind in (LINE, ARROW):  # these keep which end is which
        assert same_points(found.strokes[0], ((60, 70), (200, 150)))


def test_a_box_dragged_backwards_is_the_same_box(doc):
    new_shape(BOX, 0, (200, 150), (60, 70)).apply(doc)
    (found,) = page_drawings(doc, 0)
    assert close_to(found.rect, (60, 70, 200, 150))


def test_a_shape_too_small_is_a_slip_of_the_hand():
    assert new_shape(LINE, 0, (10, 10), (11, 11)) is None
    assert new_shape(BOX, 0, (10, 10), (14, 10)) is not None


def test_an_unknown_shape_is_refused(doc):
    with pytest.raises(CommandError):
        AddShape("star", 0, (10, 10), (50, 50), RED, 2, 1.0, new_name()).apply(doc)
    assert types(doc) == []


def test_undo_takes_the_shape_away(doc):
    order = new_shape(OVAL, 0, (60, 70), (200, 150))
    order.apply(doc)
    order.undo(doc)
    assert types(doc) == []


# ---- the journal -----------------------------------------------------------------


@pytest.mark.parametrize(
    "order",
    [
        new_ink(0, [STROKE, ((1.5, 2.5), (3.5, 4.5))], RED, 4, 0.5),
        new_shape(ARROW, 1, (60, 70), (200, 150), RED, 8, 0.3),
        Remove(new_ink(0, [STROKE])),
        Remove(new_shape(BOX, 0, (60, 70), (200, 150))),
    ],
)
def test_orders_are_written_down_and_read_back(order):
    assert command_from_dict(order.to_dict()) == order


def test_an_order_read_back_does_the_same(doc):
    order = command_from_dict(new_shape(BOX, 0, (60, 70), (200, 150), RED, 4).to_dict())
    order.apply(doc)
    (found,) = page_drawings(doc, 0)
    assert found.kind == BOX and found.width == 4


# ---- reading back, for the eraser -------------------------------------------------


def test_what_is_read_back_gives_the_order_that_made_it(doc):
    orders = [
        new_ink(0, [STROKE], RED, 4, 0.5),
        new_shape(LINE, 0, (60, 70), (200, 150), RED, 1, 1.0),
        new_shape(ARROW, 0, (60, 170), (200, 250), RED, 2, 0.6),
        new_shape(BOX, 0, (260, 70), (300, 150), RED, 8, 1.0),
        new_shape(OVAL, 0, (260, 170), (300, 250), RED, 2, 1.0),
    ]
    for order in orders:
        order.apply(doc)
    found = page_drawings(doc, 0)
    assert [item.name for item in found] == [order.name for order in orders]
    for item, order in zip(found, orders, strict=True):
        again = item.order()
        assert type(again) is type(order)
        assert again.name == order.name and again.width == order.width
        assert again.opacity == pytest.approx(order.opacity)
        assert close_to(again.color, order.color)


@pytest.mark.parametrize("page", [0, 1])
def test_erasing_and_undoing_leaves_it_as_it_was(doc, page):
    for order in (
        new_ink(page, [STROKE], RED, 4, 0.5),
        new_shape(ARROW, page, (60, 170), (200, 250), RED, 2, 0.6),
        new_shape(OVAL, page, (260, 170), (300, 250), RED, 2, 1.0),
    ):
        order.apply(doc)
    before = doc[page].get_pixmap().samples
    for item in page_drawings(doc, page):
        erase = Remove(item.order())
        erase.apply(doc)
        assert item.name not in [d.name for d in page_drawings(doc, page)]
        erase.undo(doc)
    assert len(page_drawings(doc, page)) == 3
    assert doc[page].get_pixmap().samples == before


@pytest.mark.parametrize("kind", [HIGHLIGHT, UNDERLINE, STRIKEOUT])
@pytest.mark.parametrize("page", [0, 1])
def test_marks_on_the_text_are_read_back_too(doc, kind, page):
    rects = ((50.0, 50.0, 200.0, 62.0), (50.0, 64.0, 120.0, 76.0))
    mark = AddMarkup(kind, (Mark(page, rects, new_name()),), RED, 0.7)
    mark.apply(doc)
    before = doc[page].get_pixmap().samples
    (found,) = page_drawings(doc, page)
    assert found.kind == kind and found.ours
    assert len(found.rects) == 2
    assert all(close_to(a, b) for a, b in zip(found.rects, rects, strict=True))
    erase = Remove(found.order())
    erase.apply(doc)
    assert page_drawings(doc, page) == []
    erase.undo(doc)
    assert doc[page].get_pixmap().samples == before


def test_what_another_program_drew_is_not_ours(doc):
    page = doc[0]
    page.add_ink_annot([[(10, 10), (50, 50)]])
    page.add_rect_annot(pymupdf.Rect(100, 100, 150, 150))
    found = page_drawings(doc, 0)
    assert [item.kind for item in found] == [INK, BOX]
    assert not any(item.ours for item in found)


# ---- what is under the pointer ----------------------------------------------------


def test_a_line_is_touched_on_it_and_not_beside_it(doc):
    new_shape(LINE, 0, (50, 50), (150, 150), RED, 2).apply(doc)
    (line,) = page_drawings(doc, 0)
    assert line.touches(100, 100)
    assert line.touches(102, 99)
    assert not line.touches(100, 120)  # inside its rectangle, far from the line
    assert not line.touches(160, 165)


def test_a_stroke_is_touched_along_its_way(doc):
    new_ink(0, [STROKE], RED, 2).apply(doc)
    (stroke,) = page_drawings(doc, 0)
    assert stroke.touches(65, 55)
    assert stroke.touches(135, 65)
    assert not stroke.touches(100, 80)


def test_a_box_is_touched_on_its_edge_not_in_its_hollow(doc):
    new_shape(BOX, 0, (50, 50), (200, 150), RED, 2).apply(doc)
    (box,) = page_drawings(doc, 0)
    assert box.touches(50, 100) and box.touches(120, 150) and box.touches(200, 52)
    assert not box.touches(120, 100)
    assert not box.touches(30, 100)


def test_an_oval_is_touched_on_its_edge_not_in_its_hollow(doc):
    new_shape(OVAL, 0, (50, 50), (250, 150), RED, 2).apply(doc)
    (oval,) = page_drawings(doc, 0)
    assert oval.touches(50, 100) and oval.touches(150, 50) and oval.touches(250, 101)
    assert not oval.touches(150, 100)
    assert not oval.touches(55, 55)  # the corner of its rectangle


def test_a_thick_line_is_easier_to_touch(doc):
    new_shape(LINE, 0, (50, 50), (250, 50), RED, 1).apply(doc)
    new_shape(LINE, 0, (50, 150), (250, 150), RED, 20).apply(doc)
    thin, thick = page_drawings(doc, 0)
    assert not thin.touches(100, 58)
    assert thick.touches(100, 158)


def test_a_mark_is_touched_anywhere_on_its_text(doc):
    rects = ((50.0, 50.0, 200.0, 62.0),)
    AddMarkup(HIGHLIGHT, (Mark(0, rects, new_name()),), RED).apply(doc)
    (mark,) = page_drawings(doc, 0)
    assert mark.touches(120, 56)
    assert not mark.touches(120, 70)


def test_the_last_one_drawn_is_the_one_on_top(doc):
    first = new_shape(LINE, 0, (50, 50), (150, 150))
    second = new_shape(LINE, 0, (150, 50), (50, 150))
    first.apply(doc)
    second.apply(doc)
    found = page_drawings(doc, 0)
    assert drawing_at(found, 100, 100).name == second.name
    assert drawing_at(found, 60, 60).name == first.name
    assert drawing_at(found, 100, 20) is None


def test_ink_orders_keep_their_strokes_as_plain_numbers():
    order = AddInk.from_dict(new_ink(0, [[(1, 2), (3, 4)]]).to_dict())
    assert order.strokes == (((1.0, 2.0), (3.0, 4.0)),)


# ---- strokes that are thicker where the pen pressed more ------------------------

PRESSED = (0.1, 0.4, 0.9, 0.5)


def dark_rows(document, page: int, x: float) -> int:
    """How many pixels of a column of the page are painted: how thick a stroke is there."""
    pixmap = document[page].get_pixmap(matrix=pymupdf.Matrix(4, 4))
    column = int(x * 4)
    return sum(1 for y in range(pixmap.height) if pixmap.pixel(column, y)[1] < 200)


@pytest.mark.parametrize("page", [0, 1])
def test_a_pressed_stroke_is_still_a_standard_one_and_keeps_its_pressures(doc, page):
    order = new_ink(page, [STROKE], RED, 4.0, 0.8, [PRESSED])
    assert order.pressed
    order.apply(doc)
    again = saved_again(doc)
    sheet = again[page]
    (annotation,) = sheet.annots()
    assert annotation.type[1] == "Ink" and annotation.border["width"] == pytest.approx(4.0)
    (found,) = page_drawings(again, page)
    assert same_points(found.strokes[0], STROKE)
    assert found.pressures == (PRESSED,)
    assert found.order().pressures == order.pressures and found.order().pressed


def test_a_pressed_stroke_is_thicker_where_the_pen_pressed_more(doc):
    flat = ((50.0, 100.0), (100.0, 100.0), (150.0, 100.0), (200.0, 100.0), (250.0, 100.0))
    new_ink(0, [flat], RED, 6.0, 1.0, [(0.0, 0.0, 0.5, 1.0, 1.0)]).apply(doc)
    again = saved_again(doc)
    soft, middle, hard = (dark_rows(again, 0, x) for x in (60, 150, 240))
    assert soft < middle < hard
    assert middle == pytest.approx(6.0 * 4, abs=3), "half the pressure: the thickness chosen"
    assert soft == pytest.approx(6.0 * THINNEST * 4, abs=3)
    assert hard == pytest.approx(6.0 * THICKEST * 4, abs=3)


def test_a_pressed_stroke_has_no_holes_where_its_pieces_overlap(doc):
    zigzag = ((100.0, 100.0), (130.0, 100.0), (100.0, 102.0), (130.0, 104.0))
    new_ink(0, [zigzag], (0.0, 0.0, 0.0), 8.0, 1.0, [(0.2, 0.9, 0.9, 0.2)]).apply(doc)
    pixmap = saved_again(doc)[0].get_pixmap()
    assert all(pixmap.pixel(x, 102)[0] < 60 for x in range(104, 127))


def test_a_pressed_stroke_keeps_its_colour_and_opacity(doc):
    new_ink(0, [STROKE], RED, 6.0, 0.5, [PRESSED]).apply(doc)
    red, green, _blue = saved_again(doc)[0].get_pixmap().pixel(120, 40)
    assert red > 200 and 100 < green < 180, "half see-through red on white"


@pytest.mark.parametrize("opacity", [1.0, 0.5])
def test_a_pressed_stroke_only_names_graphics_states_it_has(doc, opacity):
    # A solid stroke has no graphics state "H": naming it anyway is an error in
    # the file (MuPDF reports "cannot find ExtGState resource").
    new_ink(0, [STROKE], RED, 6.0, opacity, [PRESSED]).apply(doc)
    again = saved_again(doc)
    (annotation,) = again[0].annots()
    look = int(again.xref_get_key(annotation.xref, "AP/N")[1].split()[0])
    named = b"/H gs" in again.xref_stream(look)
    has = again.xref_get_key(look, "Resources/ExtGState/H")[0] != "null"
    assert named == has
    assert named == (opacity < 1.0)


def test_pressures_that_do_not_fit_the_points_are_left_aside(doc):
    order = new_ink(0, [STROKE], RED, 4.0, 1.0, [(0.2, 0.9)])
    assert not order.pressed
    order.apply(doc)
    assert page_drawings(doc, 0)[0].pressures == ()


def test_erasing_a_pressed_stroke_and_undoing_leaves_it_as_it_was(doc):
    order = new_ink(0, [STROKE], RED, 4.0, 1.0, [PRESSED])
    order.apply(doc)
    before = doc[0].get_pixmap().samples
    remove = Remove(page_drawings(doc, 0)[0].order())
    remove.apply(doc)
    assert page_drawings(doc, 0) == []
    remove.undo(doc)
    assert doc[0].get_pixmap().samples == before
    assert page_drawings(doc, 0)[0].pressures == (PRESSED,)


def test_a_pressed_stroke_is_written_in_the_journal_with_its_pressures():
    order = new_ink(0, [STROKE], RED, 4.0, 1.0, [PRESSED])
    assert command_from_dict(order.to_dict()) == order
    plain = new_ink(0, [STROKE])
    assert "pressures" not in plain.to_dict(), "old journals and new ones read the same"
    assert command_from_dict(plain.to_dict()) == plain


def test_pressures_are_thinned_with_their_points():
    points = [(0.0, 0.0), (0.1, 0.0), (0.2, 0.0), (5.0, 0.0), (5.1, 0.0), (9.0, 0.0)]
    kept, pressed = thinned_stroke(points, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    assert kept == ((0.0, 0.0), (5.0, 0.0), (9.0, 0.0))
    assert pressed == (0.1, 0.4, 0.6)
    assert thinned_stroke(points, [0.5])[1] == (), "pressures that do not fit are dropped"


def test_the_thickness_follows_the_pressure_between_its_limits():
    soft, hard = half_widths([0.0] * 3, 4.0)[1], half_widths([1.0] * 3, 4.0)[1]
    assert soft == pytest.approx(2.0 * THINNEST) and hard == pytest.approx(2.0 * THICKEST)
    assert half_widths([0.5] * 3, 4.0)[1] == pytest.approx(2.0)
    assert max(half_widths([7, -3, 2], 4.0)) <= 2.0 * THICKEST, "odd values never break it"
    lump = half_widths([0.2, 1.0, 0.2], 4.0)
    assert lump[1] < 2.0 * THICKEST, "one jump of pressure is evened out"


def test_a_pen_that_feels_no_pressure_says_nothing():
    assert not felt([1.0, 1.0, 1.0]) and not felt([0.5]) and not felt([])
    assert felt([0.2, 0.6, 0.4])


def test_the_pieces_of_a_pressed_stroke_all_go_round_the_same_way():
    points = [(0.0, 0.0), (10.0, 0.0), (0.0, 1.0), (-10.0, -5.0)]
    pieces, discs = pressed_shape(points, [1.0, 2.0, 3.0, 1.0])
    assert len(pieces) == 3 and len(discs) == 4

    def area(corners):
        return sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(corners, (*corners[1:], corners[0]), strict=True)
        )

    assert all(area(piece) > 0 for piece in pieces)


def test_a_pressed_stroke_is_touched_where_it_is_thick(doc):
    flat = ((50.0, 100.0), (150.0, 100.0), (250.0, 100.0))
    new_ink(0, [flat], RED, 10.0, 1.0, [(1.0, 1.0, 1.0)]).apply(doc)
    (found,) = page_drawings(doc, 0)
    assert found.touches(150, 107.5, reach=0.5), "thicker than the thickness it says"
    assert not found.touches(150, 112, reach=0.5)
