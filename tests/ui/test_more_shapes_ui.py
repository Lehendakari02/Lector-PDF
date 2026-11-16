"""Tests for the new shapes in the window: choosing them, drawing them, adjusting
the one just drawn, Shift, the fill and the dashed line."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core import arrange
from app.core.drawing import (
    ARROW,
    BOX,
    BRACE,
    DOUBLE_ARROW,
    ELBOW,
    LINE,
    OVAL,
    RHOMBUS,
    SHAPE_TOOL,
    TRIANGLE,
)
from app.core.favourites import Favourites
from app.core.marker_styles import MarkerStyles
from app.ui.main_window import MARKERS_SETTING

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
        return view, path

    return open_it


def place(view, page: int, x: float, y: float) -> QPoint:
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def drag(view, *points, keys=NO_KEYS) -> None:
    spots = [place(view, 0, x, y) for x, y in points]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    QTest.mouseRelease(view.viewport(), LEFT, keys, spots[-1])


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def near(first, second, by: float = 1.5) -> bool:
    return all(abs(a - b) <= by for a, b in zip(first, second, strict=True))


@pytest.mark.parametrize(
    ("shape", "subtype"),
    [
        (DOUBLE_ARROW, "Line"),
        (ELBOW, "PolyLine"),
        (TRIANGLE, "Polygon"),
        (RHOMBUS, "Polygon"),
        (BRACE, "PolyLine"),
    ],
)
def test_each_new_shape_is_drawn_and_saved(window, opened, wait_until, shape, subtype, capsys):
    view, path = opened()
    window.set_shape(shape)
    assert view.markup_tool == SHAPE_TOOL and window.shape_actions[shape].isChecked()
    assert not window.shape_actions[shape].icon().isNull()
    drag(view, (100, 300), (150, 340), (220, 420))
    view.viewport().grab()  # painted while it waits for the helper
    settle(view, wait_until)
    (found,) = view.drawings_of(0)
    assert found.kind == shape and near(found.strokes[0][1], (220, 420))
    view.viewport().grab()
    window.save_document()
    wait_until(lambda: not view.modified)
    with pymupdf.open(path) as doc:
        page = doc[0]
        assert [a.type[1] for a in page.annots()] == [subtype]
    assert "Traceback" not in capsys.readouterr().err


def test_the_shape_just_drawn_stays_picked_to_adjust_it(window, opened, wait_until):
    view, _ = opened()
    window.set_shape(BOX)
    drag(view, (100, 300), (200, 360))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert view.picked_item() == box and view.markup_tool == SHAPE_TOOL
    # Its corner is dragged: it changes size instead of starting another box.
    drag(view, (200, 360), (230, 380), (260, 400))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.strokes[0][1], (260, 400))
    # Dragged from its line, it moves.
    drag(view, (100, 330), (120, 340), (140, 350))
    settle(view, wait_until)
    (box,) = view.drawings_of(0)
    assert near(box.strokes[0][0], (140, 320))
    # Elsewhere, another shape starts and the first is let go.
    drag(view, (300, 500), (380, 560))
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 2
    assert view.picked_item().strokes[0][0] == pytest.approx((300, 500), abs=1.5)


def test_supr_takes_away_the_shape_just_drawn(window, opened, wait_until):
    view, _ = opened()
    window.set_shape(ARROW)
    drag(view, (100, 300), (200, 360))
    settle(view, wait_until)
    QTest.keyClick(view, Qt.Key.Key_Delete)
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and view.markup_tool == SHAPE_TOOL


def test_with_shift_a_line_is_straight(window, opened, wait_until):
    view, _ = opened()
    window.set_shape(LINE)
    drag(view, (100, 300), (250, 310), keys=SHIFT)
    settle(view, wait_until)
    (line,) = view.drawings_of(0)
    (start, end) = line.strokes[0]
    assert abs(end[1] - start[1]) < 0.5, "level"
    assert end[0] == pytest.approx(100 + (150**2 + 10**2) ** 0.5, abs=1)


def test_with_shift_a_box_is_square_and_an_oval_a_circle(window, opened, wait_until):
    view, _ = opened()
    for shape in (BOX, OVAL):
        window.set_shape(shape)
        drag(view, (100, 300), (180, 330), keys=SHIFT)
        settle(view, wait_until)
        found = view.drawings_of(0)[-1]
        (start, end) = found.strokes[0]
        assert end[0] - start[0] == pytest.approx(end[1] - start[1], abs=1)
        view.pick(None)
        view.undo()
        settle(view, wait_until)


def test_fill_and_dashed_line_are_chosen_and_remembered(window, opened, wait_until):
    view, path = opened()
    window.shape_fill_action.trigger()
    window.shape_dashed_action.trigger()
    assert view.markup_tool == SHAPE_TOOL, "choosing them takes the shapes"
    assert view.shape_fill and view.shape_dashed
    window.set_shape(TRIANGLE)
    drag(view, (100, 300), (200, 400))
    settle(view, wait_until)
    (found,) = view.drawings_of(0)
    assert found.fill and found.dashed
    kept = MarkerStyles.from_setting(window.settings.get(MARKERS_SETTING))
    assert kept.shape_fill and kept.shape_dashed
    window.shape_fill_action.trigger()
    assert not view.shape_fill and not window.shape_fill_action.isChecked()


def test_a_favourite_keeps_fill_and_dash(window, opened):
    opened()
    window.set_shape(RHOMBUS)
    window.shape_fill_action.trigger()
    window.ask_favourite_name = lambda *_args: ""
    window.add_favourite(SHAPE_TOOL)
    (favourite,) = Favourites.from_setting(window.settings.get("favoritas")).items
    assert favourite.shape == RHOMBUS and favourite.fill and not favourite.dashed
    assert "relleno" in window.favourite_name(favourite)
    window.shape_fill_action.trigger()
    window.use_favourite(0)
    assert window.marker_styles.shape_fill and window.shape_fill_action.isChecked()


def test_a_brace_drawn_to_the_left_closes(window, opened, wait_until):
    view, _ = opened()
    window.set_shape(BRACE)
    drag(view, (200, 300), (170, 400))
    settle(view, wait_until)
    (brace,) = view.drawings_of(0)
    (start, end) = brace.strokes[0]
    assert start[0] > end[0]
    grips = arrange.handles(view._order_of(brace))
    assert len(grips) == 4
