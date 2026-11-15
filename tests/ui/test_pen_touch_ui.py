"""Tests for the pen and the fingers on the page.

There is no pen or touch screen here: the events are made by hand, the way Qt
gives them. What a real pen or a real hand does is in the list of manual tests.
"""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QInputDevice, QPointingDevice, QTabletEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core import pen
from app.core.commands import HIGHLIGHT
from app.core.drawing import DRAW, ERASER, INK, SHAPE_TOOL
from app.core.notes import NOTE
from app.ui import pdf_view
from app.ui.main_window import MainWindow

LEFT, RIGHT, NO_BUTTON = (
    Qt.MouseButton.LeftButton,
    Qt.MouseButton.RightButton,
    Qt.MouseButton.NoButton,
)
PEN, RUBBER = QPointingDevice.PointerType.Pen, QPointingDevice.PointerType.Eraser
_DEVICES = {}


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


@pytest.fixture
def screen():
    if "touch" not in _DEVICES:
        _DEVICES["touch"] = QTest.createTouchDevice()
    return _DEVICES["touch"]


def place(view, page: int, x: float, y: float) -> QPoint:
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def stylus(end=PEN) -> QPointingDevice:
    if end not in _DEVICES:
        _DEVICES[end] = QPointingDevice(
            "pen",
            40 + len(_DEVICES),
            QInputDevice.DeviceType.Stylus,
            end,
            QInputDevice.Capability.Pressure | QInputDevice.Capability.Position,
            1,
            3,
        )
    return _DEVICES[end]


def pen_event(view, kind, spot: QPoint, pressure=0.5, button=LEFT, buttons=LEFT, end=PEN):
    where = QPointF(spot)
    event = QTabletEvent(
        kind,
        stylus(end),
        where,
        QPointF(view.viewport().mapToGlobal(spot)),
        pressure,
        0,
        0,
        0,
        0,
        0,
        Qt.KeyboardModifier.NoModifier,
        button,
        buttons,
    )
    QApplication.sendEvent(view.viewport(), event)
    return event


def pen_stroke(view, page, points, pressures=None, end=PEN, button=LEFT):
    """Press the pen on the first point, go through the others, lift it on the last."""
    spots = [place(view, page, x, y) for x, y in points]
    pressures = pressures or [0.5] * len(spots)
    pen_event(view, QEvent.Type.TabletPress, spots[0], pressures[0], button, button, end)
    for spot, pressure in zip(spots[1:], pressures[1:], strict=True):
        pen_event(view, QEvent.Type.TabletMove, spot, pressure, NO_BUTTON, button, end)
    pen_event(view, QEvent.Type.TabletRelease, spots[-1], 0.0, button, NO_BUTTON, end)


def finger_drag(view, screen, *spots, finger=0):
    port = view.viewport()
    QTest.touchEvent(view, screen).press(finger, spots[0], port)
    for spot in spots[1:]:
        QTest.touchEvent(view, screen).move(finger, spot, port)
    QTest.touchEvent(view, screen).release(finger, spots[-1], port)


WAY = [(100, 100), (140, 120), (180, 100), (220, 160)]


# ---- the pen -----------------------------------------------------------------------


def test_the_pen_draws_thicker_where_it_presses_more(window, opened, wait_until, capsys):
    view, path = opened()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    view.viewport().grab()
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert stroke.kind == INK and len(stroke.strokes[0]) == 4
    assert stroke.pressures == ((0.1, 0.4, 0.9, 0.6),)
    assert view.can_undo and "Traceback" not in capsys.readouterr().err
    assert window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    with pymupdf.open(path) as doc:
        page = doc[0]
        (annotation,) = page.annots()
        assert annotation.type[1] == "Ink", "a standard stroke for every other program"


def test_while_the_pen_draws_the_stroke_is_seen_with_its_thickness(window, opened, capsys):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    view.draw_color, view.draw_width = (0.0, 0.0, 0.0), 8.0
    spots = [place(view, 0, x, 200) for x in (100, 200, 300)]
    pen_event(view, QEvent.Type.TabletPress, spots[0], 0.0)
    pen_event(view, QEvent.Type.TabletMove, spots[1], 0.5, NO_BUTTON)
    pen_event(view, QEvent.Type.TabletMove, spots[2], 1.0, NO_BUTTON)
    picture = view.viewport().grab().toImage()
    scale = picture.devicePixelRatio()

    def thick(spot: QPoint) -> int:
        x = int(spot.x() * scale)
        return sum(
            1
            for y in range(int((spot.y() - 20) * scale), int((spot.y() + 20) * scale))
            if picture.pixelColor(x, y).lightness() < 90
        )

    soft, hard = thick(spots[0] + QPoint(6, 0)), thick(spots[2] - QPoint(6, 0))
    assert 0 < soft < hard
    assert thick(spots[1]) > 0, "no hole where two pieces of the stroke meet"
    assert "Traceback" not in capsys.readouterr().err
    pen_event(view, QEvent.Type.TabletRelease, spots[2], 0.0, LEFT, NO_BUTTON)


def test_two_quick_strokes_from_the_same_place_both_feel_the_pressure(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    pen_stroke(view, 0, WAY, [0.2, 0.5, 0.8, 0.3])
    settle(view, wait_until)
    first, second = view.drawings_of(0)
    assert first.pressures and second.pressures == ((0.2, 0.5, 0.8, 0.3),)


def test_a_pen_that_feels_no_pressure_draws_a_plain_stroke(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [1.0, 1.0, 1.0, 1.0])
    settle(view, wait_until)
    assert view.drawings_of(0)[0].pressures == ()


def test_pressure_can_be_turned_off(window, opened, wait_until):
    view, _ = opened()
    window.settings.set(pen.PRESSURE_SETTING, False)
    window.apply_pen_settings()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    settle(view, wait_until)
    assert view.drawings_of(0)[0].pressures == ()


def test_the_mouse_never_draws_with_pressure(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    spots = [place(view, 0, x, y) for x, y in WAY]
    QTest.mousePress(view.viewport(), LEFT, Qt.KeyboardModifier.NoModifier, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    QTest.mouseRelease(view.viewport(), LEFT, Qt.KeyboardModifier.NoModifier, spots[-1])
    settle(view, wait_until)
    assert view.drawings_of(0)[0].pressures == ()


def test_the_pen_does_everything_the_mouse_does(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(SHAPE_TOOL)
    pen_stroke(view, 0, [(100, 300), (200, 340)])
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1
    window.use_writing_tool(ERASER)
    pen_stroke(view, 0, [(150, 310), (150, 320), (150, 330)])
    settle(view, wait_until)
    assert view.drawings_of(0) == []


@pytest.mark.parametrize("how", ["other end", "button"])
def test_the_other_end_of_the_pen_or_its_button_erase(window, opened, wait_until, how):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1
    across = [(120, 90), (120, 110), (120, 130)]
    if how == "other end":
        pen_stroke(view, 0, across, end=RUBBER)
    else:
        pen_stroke(view, 0, across, button=RIGHT)
    settle(view, wait_until)
    assert view.drawings_of(0) == [], "erased, with the drawing pen still in hand"
    assert view.markup_tool == DRAW and view._sketch is None
    view.undo()
    settle(view, wait_until)
    assert view.drawings_of(0)[0].pressures == ((0.1, 0.4, 0.9, 0.6),)


def test_the_first_time_a_pen_is_used_it_is_remembered(window, opened, settings, wait_until):
    view, _ = opened()
    assert not pen.pen_seen(window.settings) and not view.pen_seen
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY)
    assert pen.pen_seen(window.settings) and view.pen_seen
    settle(view, wait_until)


def test_a_pen_coming_near_does_not_count_as_using_it(window, opened):
    view, _ = opened()
    pen_event(view, QEvent.Type.TabletMove, place(view, 0, 100, 100), 0.0, NO_BUTTON, NO_BUTTON)
    assert not view.pen_seen and view._sketch is None


def test_two_quick_taps_are_a_double_click(window, opened, screen, wait_until):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 3))
    x0, y0, x1, y1 = view._selection_rects(0)[0]
    view.clear_selection()
    spot = place(view, 0, (x0 + x1) / 2, (y0 + y1) / 2)
    finger_drag(view, screen, spot)
    assert not view.has_selection
    finger_drag(view, screen, spot + QPoint(2, 1))
    assert view.has_selection, "the word under the finger"
    view.clear_selection()
    for _ in range(2):
        pen_event(view, QEvent.Type.TabletPress, spot)
        pen_event(view, QEvent.Type.TabletRelease, spot, 0.0, LEFT, NO_BUTTON)
    assert view.has_selection, "and under the pen"


# ---- the fingers -------------------------------------------------------------------


def test_a_finger_moves_the_page(window, opened, screen, capsys):
    view, _ = opened()
    bar = view.verticalScrollBar()
    finger_drag(view, screen, QPoint(200, 300), QPoint(200, 250), QPoint(200, 180))
    view.viewport().grab()
    assert bar.value() == pytest.approx(120, abs=pdf_view.TOUCH_SLOP + 1)
    assert not view.has_selection and "Traceback" not in capsys.readouterr().err


def test_two_fingers_apart_make_the_page_bigger(window, opened, screen, wait_until):
    view, _ = opened()
    port, before = view.viewport(), view.zoom
    QTest.touchEvent(view, screen).press(0, QPoint(200, 200), port)
    QTest.touchEvent(view, screen).stationary(0).press(1, QPoint(260, 200), port)
    QTest.touchEvent(view, screen).move(0, QPoint(170, 200), port).move(1, QPoint(290, 200), port)
    assert view.zoom == pytest.approx(before * 2, rel=0.02)
    QTest.touchEvent(view, screen).move(0, QPoint(185, 200), port).move(1, QPoint(275, 200), port)
    assert view.zoom == pytest.approx(before * 1.5, rel=0.02)
    QTest.touchEvent(view, screen).release(0, QPoint(185, 200), port).release(
        1, QPoint(275, 200), port
    )
    assert view._touch is None


def test_a_tap_is_a_click(window, opened, screen, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    settle(view, wait_until)
    window.use_writing_tool(DRAW)  # put down
    view.set_markup_tool("")
    view._pen_at = float("-inf")
    spot = place(view, 0, 140, 120)
    finger_drag(view, screen, spot)
    assert view.picked_item() is not None


def test_with_no_pen_around_a_finger_uses_the_tool_in_hand(window, opened, screen, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    finger_drag(view, screen, *(place(view, 0, x, y) for x, y in WAY))
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert stroke.pressures == () and len(stroke.strokes[0]) == 4


def test_once_a_pen_is_used_the_fingers_only_move_the_page(window, opened, screen, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    settle(view, wait_until)
    view._pen_at = float("-inf")  # long after the pen went away
    finger_drag(view, screen, QPoint(200, 300), QPoint(200, 250), QPoint(200, 180))
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1
    assert view.verticalScrollBar().value() > 100


@pytest.mark.parametrize("mode, draws", [(pen.DRAWS, True), (pen.MOVES, False)])
def test_what_the_finger_does_can_be_chosen(window, opened, screen, wait_until, mode, draws):
    view, _ = opened()
    window.settings.set(pen.FINGER_SETTING, mode)
    window.settings.set(pen.PEN_SEEN_SETTING, draws)  # the choice wins either way
    window.apply_pen_settings()
    window.use_writing_tool(DRAW)
    finger_drag(view, screen, *(place(view, 0, x, y) for x, y in WAY))
    settle(view, wait_until)
    assert bool(view.drawings_of(0)) is draws


def test_the_hand_that_holds_the_pen_does_nothing(window, opened, screen, wait_until):
    view, _ = opened()
    window.settings.set(pen.FINGER_SETTING, pen.DRAWS)
    window.apply_pen_settings()
    window.use_writing_tool(DRAW)
    spots = [place(view, 0, x, y) for x, y in WAY]
    pen_event(view, QEvent.Type.TabletPress, spots[0], 0.3)
    pen_event(view, QEvent.Type.TabletMove, spots[1], 0.6, NO_BUTTON)
    # The hand lands on the screen while the pen writes, and stays a moment after.
    palm = [QPoint(300, 400), QPoint(310, 440), QPoint(300, 470)]
    QTest.touchEvent(view, screen).press(0, palm[0], view.viewport())
    QTest.touchEvent(view, screen).move(0, palm[1], view.viewport())
    pen_event(view, QEvent.Type.TabletMove, spots[2], 0.9, NO_BUTTON)
    pen_event(view, QEvent.Type.TabletRelease, spots[3], 0.0, LEFT, NO_BUTTON)
    QTest.touchEvent(view, screen).move(0, palm[2], view.viewport())
    QTest.touchEvent(view, screen).release(0, palm[2], view.viewport())
    finger_drag(view, screen, *palm)  # and it touches again right away
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert len(stroke.strokes[0]) == 4, "the stroke of the pen, whole, and nothing else"
    assert view.verticalScrollBar().value() == 0


def test_a_finger_drawing_gives_way_to_the_pen(window, opened, screen, wait_until):
    view, _ = opened()
    window.settings.set(pen.FINGER_SETTING, pen.DRAWS)
    window.apply_pen_settings()
    window.use_writing_tool(DRAW)
    QTest.touchEvent(view, screen).press(0, place(view, 0, 150, 220), view.viewport())
    QTest.touchEvent(view, screen).move(0, place(view, 0, 170, 240), view.viewport())
    assert view._sketch is not None
    pen_stroke(view, 0, WAY, [0.1, 0.4, 0.9, 0.6])
    QTest.touchEvent(view, screen).release(0, place(view, 0, 170, 240), view.viewport())
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert stroke.pressures, "only what the pen drew"


def test_a_second_finger_drops_what_the_first_was_drawing(window, opened, screen, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    port = view.viewport()
    first, second = place(view, 0, 100, 100), place(view, 0, 200, 100)
    QTest.touchEvent(view, screen).press(0, first, port)
    QTest.touchEvent(view, screen).move(0, first + QPoint(15, 15), port)
    assert view._sketch is not None
    QTest.touchEvent(view, screen).stationary(0).press(1, second, port)
    assert view._sketch is None
    QTest.touchEvent(view, screen).release(0, first, port).release(1, second, port)
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and not view.can_undo


def test_a_finger_with_a_marker_marks_the_text(window, opened, screen, wait_until):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.set_markup_tool(HIGHLIGHT)
    line = view._texts[0]
    view.select((0, 0), (0, 12))
    x0, y0, x1, y1 = view._selection_rects(0)[0]
    view.clear_selection()
    middle = (y0 + y1) / 2
    finger_drag(view, screen, place(view, 0, x0 + 1, middle), place(view, 0, x1 - 1, middle))
    settle(view, wait_until)
    assert len(line) and [item.kind for item in view.drawings_of(0)] == [HIGHLIGHT]


def test_resting_a_finger_selects_like_the_mouse(window, opened, screen, wait_until):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 12))
    x0, y0, x1, y1 = view._selection_rects(0)[0]
    view.clear_selection()
    middle = (y0 + y1) / 2
    port = view.viewport()
    start, end = place(view, 0, x0 + 1, middle), place(view, 0, x1 - 1, middle)
    QTest.touchEvent(view, screen).press(0, start, port)
    wait_until(lambda: view._touch["mode"] == "mouse")
    QTest.touchEvent(view, screen).move(0, end, port)
    QTest.touchEvent(view, screen).release(0, end, port)
    assert view.has_selection and view.verticalScrollBar().value() == 0


def test_resting_a_finger_and_lifting_it_is_the_right_button(
    window, opened, screen, wait_until, monkeypatch
):
    view, _ = opened()
    asked = []
    monkeypatch.setattr(
        pdf_view.PdfView, "contextMenuEvent", lambda self, event: asked.append(event.pos())
    )
    spot = QPoint(200, 300)
    QTest.touchEvent(view, screen).press(0, spot, view.viewport())
    wait_until(lambda: view._touch["mode"] == "mouse")
    QTest.touchEvent(view, screen).release(0, spot, view.viewport())
    wait_until(lambda: asked)
    assert asked == [spot]


def test_a_quick_push_leaves_the_page_gliding(window, opened, screen, wait_until):
    view, _ = opened()
    bar, port = view.verticalScrollBar(), view.viewport()
    QTest.touchEvent(view, screen).press(0, QPoint(200, 400), port)
    for y in (360, 300, 240, 180):
        QTest.touchEvent(view, screen).move(0, QPoint(200, y), port)
    QTest.touchEvent(view, screen).release(0, QPoint(200, 180), port)
    lifted_at = bar.value()
    assert view._fling.isActive()
    wait_until(lambda: not view._fling.isActive())
    assert bar.value() > lifted_at + 50
    # A touch stops it at once.
    QTest.touchEvent(view, screen).press(0, QPoint(200, 400), port)
    for y in (360, 300, 240, 180):
        QTest.touchEvent(view, screen).move(0, QPoint(200, y), port)
    QTest.touchEvent(view, screen).release(0, QPoint(200, 180), port)
    QTest.touchEvent(view, screen).press(0, QPoint(200, 300), port)
    assert not view._fling.isActive()
    QTest.touchEvent(view, screen).release(0, QPoint(200, 300), port)


def test_a_tap_with_a_tool_in_hand_that_the_finger_does_not_use_does_nothing(
    window, opened, screen, wait_until
):
    view, _ = opened()
    window.settings.set(pen.FINGER_SETTING, pen.MOVES)
    window.apply_pen_settings()
    window.use_writing_tool(NOTE)
    finger_drag(view, screen, place(view, 0, 200, 200))
    assert view.note_panel is None


# ---- the settings ------------------------------------------------------------------


def test_the_settings_offer_the_pen_and_the_finger(window, opened, wait_until):
    view, _ = opened()
    dialog = window.open_settings()
    assert dialog.pressure_box.isChecked()
    assert dialog.finger_box.currentData() == pen.AUTO
    assert "Todavía no" in dialog.finger_note.text()
    dialog.pressure_box.setChecked(False)
    assert pen.pressure_wanted(window.settings) is False and view.pen_pressure is False
    dialog.finger_box.setCurrentIndex(dialog.finger_box.findData(pen.MOVES))
    dialog.finger_box.activated.emit(dialog.finger_box.currentIndex())
    assert pen.finger_mode(window.settings) == pen.MOVES and view.finger_mode == pen.MOVES
    assert "nunca pinta" in dialog.finger_note.text()
    dialog.close()


def test_what_was_chosen_is_there_the_next_time(window, settings, qt_app):
    window.settings.set(pen.FINGER_SETTING, pen.DRAWS)
    window.settings.set(pen.PRESSURE_SETTING, False)
    again = MainWindow(settings)
    try:
        assert again.pdf_view.finger_mode == pen.DRAWS
        assert again.pdf_view.pen_pressure is False
    finally:
        again.close()
        again.deleteLater()
