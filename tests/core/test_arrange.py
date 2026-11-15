"""Tests for app.core.arrange: moving, resizing and copying what is on a page."""

import pymupdf
import pytest

from app.core import arrange
from app.core.arrange import BOTTOM_RIGHT, TOP_LEFT, bounds, copy_of, handles, moved, resized
from app.core.commands import HIGHLIGHT, AddMarkup, Mark, command_from_dict, new_name
from app.core.drawing import ARROW, BOX, LINE, OVAL, new_ink, new_shape, page_drawings
from app.core.notes import NOTE_SIZE, SANS, new_note, new_text_box, page_notes

PAGE = (400.0, 300.0)
STROKE = ((50.0, 50.0), (80.0, 60.0), (120.0, 40.0), (150.0, 90.0))


@pytest.fixture
def doc():
    document = pymupdf.open()
    document.new_page(width=400, height=300)
    turned = document.new_page(width=300, height=400)
    turned.set_rotation(90)  # shown 400 wide and 300 tall, like the first
    yield document
    document.close()


def close_to(first, second, by: float = 0.01) -> bool:
    return all(abs(a - b) <= by for a, b in zip(first, second, strict=True))


def everything():
    return [
        new_note(0, (100, 100), "nota"),
        new_text_box(0, (100, 100), "dos\nlíneas", SANS, 12),
        new_ink(0, [STROKE]),
        new_shape(LINE, 0, (60, 70), (200, 150)),
        new_shape(ARROW, 0, (60, 70), (200, 150)),
        new_shape(BOX, 0, (60, 70), (200, 150)),
        new_shape(OVAL, 0, (60, 70), (200, 150)),
    ]


MARK = AddMarkup(HIGHLIGHT, (Mark(0, ((50.0, 50.0, 200.0, 62.0),), new_name()),), (1, 1, 0))


# ---- the frame -------------------------------------------------------------------


def test_the_frame_of_each_thing():
    note, text, ink, line, *_ = everything()
    assert bounds(note) == (100, 100, 100 + NOTE_SIZE, 100 + NOTE_SIZE)
    assert bounds(ink) == (50, 40, 150, 90)
    assert bounds(line) == (60, 70, 200, 150)
    assert bounds(MARK) == (50, 50, 200, 62)
    x0, y0, x1, y1 = bounds(text)
    assert (x0, y0) == (100, 100) and x1 > 120 and y1 - y0 == pytest.approx(2 * 15 + 4)


def test_the_frame_of_a_text_is_the_room_it_takes_on_the_page(doc):
    text = new_text_box(0, (100, 100), "dos\nlíneas", SANS, 12)
    text.apply(doc)
    (found,) = page_notes(doc, 0)
    assert close_to(found.rect, bounds(text, 400), 0.5)


def test_what_can_be_moved_and_resized():
    note, text, ink, line, arrow, box, oval = everything()
    assert all(arrange.can_move(order) for order in everything())
    assert not arrange.can_move(MARK) and not arrange.can_resize(MARK)
    assert not arrange.can_resize(note)
    assert all(arrange.can_resize(order) for order in (text, ink, line, arrow, box, oval))
    assert handles(note) == [] and handles(MARK) == []
    assert handles(line) == [(60, 70), (200, 150)]
    assert handles(box) == [(60, 70), (200, 70), (200, 150), (60, 150)]
    assert len(handles(ink)) == 4 and len(handles(text)) == 4


# ---- moving ----------------------------------------------------------------------


@pytest.mark.parametrize("order", everything(), ids=lambda order: type(order).__name__)
def test_moving_shifts_the_frame_and_keeps_the_name(order):
    change = moved(order, 30, -20, PAGE)
    x0, y0, x1, y1 = bounds(order)
    assert close_to(bounds(change.new), (x0 + 30, y0 - 20, x1 + 30, y1 - 20))
    assert change.old == order and change.new.name == order.name


def test_a_mark_does_not_move_and_no_movement_is_nothing():
    assert moved(MARK, 30, 30, PAGE) is None
    assert moved(new_shape(BOX, 0, (60, 70), (200, 150)), 0, 0, PAGE) is None


@pytest.mark.parametrize("order", everything(), ids=lambda order: type(order).__name__)
def test_nothing_is_moved_out_of_its_page(order):
    for dx, dy in ((1000, 1000), (-1000, -1000), (1000, -1000)):
        x0, y0, x1, y1 = bounds(moved(order, dx, dy, PAGE).new, PAGE[0])
        assert x0 >= -0.01 and y0 >= -0.01 and x1 <= PAGE[0] + 0.01 and y1 <= PAGE[1] + 0.01


def test_already_against_the_edge_it_does_not_move_further():
    box = new_shape(BOX, 0, (300, 70), (400, 150))
    assert moved(box, 50, 0, PAGE) is None
    assert bounds(moved(box, 50, 10, PAGE).new) == (300, 80, 400, 160)


def test_a_text_moved_to_the_edge_keeps_its_lines(doc):
    text = new_text_box(0, (20, 100), "una frase algo larga para ver si se parte", SANS, 12)
    change = moved(text, 1000, 0, PAGE)
    change.new.apply(doc)
    (found,) = page_notes(doc, 0)
    assert "\n" not in found.text
    assert found.rect[2] <= 400


@pytest.mark.parametrize("page", [0, 1])
@pytest.mark.parametrize("order", everything(), ids=lambda order: type(order).__name__)
def test_moving_in_the_document_and_undoing(doc, page, order):
    from dataclasses import replace

    order = replace(order, page=page)
    order.apply(doc)
    before = doc[page].get_pixmap().samples
    change = moved(order, 40, 25, PAGE)
    change.apply(doc)
    found = [*page_notes(doc, page), *page_drawings(doc, page)]
    assert len(found) == 1 and found[0].name == order.name
    x0, y0, _, _ = bounds(order, 400)
    assert close_to(bounds(found[0].order(), 400)[:2], (x0 + 40, y0 + 25), 0.6)
    assert doc[page].get_pixmap().samples != before
    change.undo(doc)
    assert doc[page].get_pixmap().samples == before


def test_a_move_is_written_down_and_read_back():
    for order in everything():
        change = moved(order, 30, 20, PAGE)
        assert command_from_dict(change.to_dict()) == change


# ---- resizing --------------------------------------------------------------------


def test_an_end_of_a_line_goes_where_it_is_taken_and_the_other_stays():
    arrow = new_shape(ARROW, 0, (60, 70), (200, 150))
    change = resized(arrow, 1, (250, 100), PAGE)
    assert (change.new.start, change.new.end) == ((60, 70), (250, 100))
    change = resized(arrow, 0, (10, 10), PAGE)
    assert (change.new.start, change.new.end) == ((10, 10), (200, 150))
    assert resized(arrow, 1, (61, 70), PAGE) is None, "the two ends on top of each other"
    assert resized(arrow, 1, (200, 150), PAGE) is None, "nothing changes"
    assert resized(arrow, 2, (250, 100), PAGE) is None


@pytest.mark.parametrize("kind", [BOX, OVAL])
def test_a_corner_of_a_box_goes_where_it_is_taken(kind):
    box = new_shape(kind, 0, (60, 70), (200, 150))
    assert bounds(resized(box, BOTTOM_RIGHT, (300, 250), PAGE).new) == (60, 70, 300, 250)
    assert bounds(resized(box, TOP_LEFT, (20, 30), PAGE).new) == (20, 30, 200, 150)
    assert bounds(resized(box, arrange.TOP_RIGHT, (260, 30), PAGE).new) == (60, 30, 260, 150)
    assert bounds(resized(box, arrange.BOTTOM_LEFT, (20, 200), PAGE).new) == (20, 70, 200, 200)


def test_a_corner_never_crosses_the_opposite_one_or_leaves_the_page():
    box = new_shape(BOX, 0, (60, 70), (200, 150))
    squeezed = bounds(resized(box, BOTTOM_RIGHT, (0, 0), PAGE).new)
    assert squeezed == (60, 70, 60 + arrange.MIN_SIDE, 70 + arrange.MIN_SIDE)
    assert bounds(resized(box, BOTTOM_RIGHT, (900, 900), PAGE).new) == (60, 70, 400, 300)


def test_a_drawing_stretches_with_its_frame():
    ink = new_ink(0, [STROKE, ((50.0, 40.0), (150.0, 90.0))])
    change = resized(ink, BOTTOM_RIGHT, (250, 140), PAGE)  # twice as wide and as tall
    assert bounds(change.new) == (50, 40, 250, 140)
    assert close_to(change.new.strokes[0][1], (110, 80))
    assert change.new.width == ink.width and change.new.name == ink.name
    shrunk = resized(ink, TOP_LEFT, (100, 65), PAGE)
    assert bounds(shrunk.new) == (100, 65, 150, 90)


def test_a_flat_stroke_only_stretches_along_itself():
    flat = new_ink(0, [((50.0, 80.0), (100.0, 80.0), (150.0, 80.0))])
    change = resized(flat, BOTTOM_RIGHT, (250, 200), PAGE)
    assert change.new.strokes[0] == ((50.0, 80.0), (150.0, 80.0), (250.0, 80.0))


def test_a_text_grows_by_the_size_of_its_letter():
    text = new_text_box(0, (100, 100), "dos\nlíneas", SANS, 12)
    x0, y0, x1, y1 = bounds(text)
    change = resized(text, BOTTOM_RIGHT, (x0 + 2 * (x1 - x0), y0 + 2 * (y1 - y0)), PAGE)
    assert 22 <= change.new.size <= 24 and change.new.size * 2 == int(change.new.size * 2)
    assert change.new.origin == (100, 100), "the opposite corner stays"
    smaller = resized(text, TOP_LEFT, ((x0 + x1) / 2, (y0 + y1) / 2), PAGE)
    assert 6 <= smaller.new.size <= 7
    assert close_to(bounds(smaller.new)[2:], (x1, y1), 0.01)
    assert resized(text, BOTTOM_RIGHT, (x1 + 0.2, y1 + 0.2), PAGE) is None
    huge = resized(text, BOTTOM_RIGHT, (4000, 4000), PAGE)
    assert huge.new.size <= 72


@pytest.mark.parametrize("page", [0, 1])
def test_resizing_in_the_document_and_undoing(doc, page):
    box = new_shape(BOX, page, (60, 70), (200, 150))
    box.apply(doc)
    before = doc[page].get_pixmap().samples
    change = resized(box, BOTTOM_RIGHT, (300, 250), PAGE)
    change.apply(doc)
    (found,) = page_drawings(doc, page)
    assert close_to(found.rect, (60, 70, 300, 250))
    change.undo(doc)
    assert doc[page].get_pixmap().samples == before


# ---- copying ---------------------------------------------------------------------


@pytest.mark.parametrize("order", everything(), ids=lambda order: type(order).__name__)
def test_a_copy_is_the_same_thing_a_little_further_with_its_own_name(order):
    copy = copy_of(order, 0, PAGE)
    assert type(copy) is type(order) and copy.name != order.name
    x0, y0, x1, y1 = bounds(order)
    assert close_to(bounds(copy), (x0 + 12, y0 + 12, x1 + 12, y1 + 12))


def test_a_copy_can_land_centred_on_a_point_of_another_page():
    box = new_shape(BOX, 0, (60, 70), (200, 150))
    copy = copy_of(box, 3, PAGE, center=(200, 200))
    assert copy.page == 3 and bounds(copy) == (130, 160, 270, 240)
    cornered = copy_of(box, 3, PAGE, center=(0, 0))
    assert bounds(cornered) == (0, 0, 140, 80), "it never leaves the page"


def test_a_mark_is_not_copied():
    assert copy_of(MARK, 0, PAGE) is None


def test_original_and_copy_live_together(doc):
    ink = new_ink(0, [STROKE])
    ink.apply(doc)
    copy_of(ink, 0, PAGE).apply(doc)
    assert len(page_drawings(doc, 0)) == 2
