"""Tests for drawing by hand, the shapes and the eraser in the window."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.commands import HIGHLIGHT
from app.core.drawing import ARROW, BOX, DRAW, ERASER, INK, LINE, OVAL, SHAPE_TOOL
from app.core.notes import NOTE
from app.ui.features import Mode
from app.ui.main_window import MARKERS_SETTING, MainWindow

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


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
    """Where a point of a page is in the window."""
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def drag(view, page: int, *points) -> None:
    """Press on the first point of the page, go through the others, let go on the last."""
    spots = [place(view, page, x, y) for x, y in points]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spots[-1])


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def save(window, wait_until) -> None:
    assert window.save_document()
    wait_until(lambda: not window.pdf_view.saving and not window.pdf_view.modified)


def in_file(path, page: int = 0) -> list[str]:
    with pymupdf.open(path) as doc:
        sheet = doc[page]
        return [annotation.type[1] for annotation in sheet.annots() or ()]


def near(first, second, by: float = 1.5) -> bool:
    return all(abs(a - b) <= by for a, b in zip(first, second, strict=True))


# ---- the tools in hand -------------------------------------------------------------


@pytest.mark.parametrize(
    ("feature", "tool"), [("draw", DRAW), ("shapes", SHAPE_TOOL), ("eraser", ERASER)]
)
def test_each_tool_stays_in_hand_until_it_is_put_down(window, opened, feature, tool):
    view, _ = opened()
    window.set_mode(Mode.STUDY)
    action = window.feature_actions[feature]
    assert "todavía no disponible" not in action.toolTip()
    action.trigger()
    assert view.markup_tool == tool and action.isChecked()
    assert "Esc" in window.statusBar().currentMessage()
    action.trigger()
    assert view.markup_tool == "" and not action.isChecked()
    action.trigger()
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.markup_tool == ""


def test_taking_one_tool_puts_the_other_down(window, opened):
    view, _ = opened()
    window.feature_actions["draw"].trigger()
    window.feature_actions["eraser"].trigger()
    assert view.markup_tool == ERASER
    assert not window.feature_actions["draw"].isChecked()
    assert window.feature_actions["eraser"].isChecked()


def test_without_a_document_the_tools_say_so(window):
    window.feature_actions["draw"].trigger()
    assert "Abre primero" in window.statusBar().currentMessage()
    assert window.pdf_view.markup_tool == ""


# ---- drawing by hand ---------------------------------------------------------------


def test_dragging_with_the_pen_draws_a_stroke(window, opened, wait_until):
    view, path = opened()
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 100), (140, 120), (180, 100), (220, 160))
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert stroke.kind == INK and stroke.ours
    points = stroke.strokes[0]
    assert near(points[0], (100, 100)) and near(points[-1], (220, 160))
    assert len(points) == 4
    assert view.modified and view.can_undo and view.markup_tool == DRAW
    assert in_file(path) == [], "the file does not change until it is saved"
    save(window, wait_until)
    assert in_file(path) == ["Ink"]


def test_the_stroke_uses_the_colour_thickness_and_opacity_chosen(window, opened, wait_until):
    view, _ = opened()
    window.set_marker_color(DRAW, (0.1, 0.55, 0.25))
    window.set_line_width(DRAW, 8)
    window.set_marker_opacity(DRAW, 0.5)
    assert view.markup_tool == DRAW, "choosing a colour takes the pen"
    drag(view, 0, (100, 100), (200, 150))
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert near(stroke.color, (0.1, 0.55, 0.25), 0.01)
    assert stroke.width == 8 and stroke.opacity == pytest.approx(0.5)


def test_every_stroke_is_one_step_of_undo(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 100), (200, 150))
    drag(view, 0, (100, 200), (200, 250))
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 2
    window.undo()
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1
    window.undo()
    settle(view, wait_until)
    assert view.drawings_of(0) == []
    window.redo()
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1


def test_a_click_without_moving_draws_nothing(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 100))
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and not view.modified


def test_escape_drops_what_was_being_drawn(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, place(view, 0, 100, 100))
    QTest.mouseMove(view.viewport(), place(view, 0, 200, 150))
    QTest.keyClick(view, Qt.Key.Key_Escape)
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, place(view, 0, 200, 150))
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and not view.modified
    assert view.markup_tool == DRAW, "only the stroke is dropped, the pen stays in hand"


def test_a_stroke_does_not_leave_its_page(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    size = view.page_sizes()[0]
    drag(view, 0, (size.width - 40, 100), (size.width + 300, 120))
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    assert stroke.strokes[0][-1][0] == pytest.approx(size.width, abs=0.5)


def test_the_stroke_stays_in_sight_until_the_page_is_drawn_again(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 100), (200, 150))
    assert view._sent_sketches or view._settling, "painted on top while the helper works"
    settle(view, wait_until)
    wait_until(lambda: not view._stale)
    assert not view._sent_sketches and not view._settling


def test_drawing_on_a_turned_view_lands_where_it_was_drawn(window, opened, wait_until):
    view, _ = opened()
    view.rotate_view()
    wait_until(lambda: 0 in view.cached_pages())
    window.use_writing_tool(DRAW)
    size = view.shown_page_size(0)
    # On the turned sheet, from near its top left corner to the right.
    drag(view, 0, (50, 30), (150, 30))
    settle(view, wait_until)
    (stroke,) = view.drawings_of(0)
    (x0, y0), (x1, y1) = stroke.strokes[0][0], stroke.strokes[0][-1]
    assert near((x0, x1), (30, 30)), "a line across the turned sheet goes down the real page"
    assert abs(abs(y1 - y0) - 100) < 2
    assert size.width > 0


def test_with_the_pen_in_hand_text_is_not_selected(window, opened, wait_until):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 150), (300, 150))
    settle(view, wait_until)
    assert not view.has_selection and len(view.drawings_of(0)) == 1


# ---- shapes ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("shape", "standard"), [(ARROW, "Line"), (LINE, "Line"), (BOX, "Square"), (OVAL, "Circle")]
)
def test_dragging_with_the_shapes_puts_the_one_chosen(window, opened, wait_until, shape, standard):
    view, path = opened()
    window.set_shape(shape)
    assert view.markup_tool == SHAPE_TOOL, "choosing a shape takes the tool"
    assert window.shape_actions[shape].isChecked()
    drag(view, 0, (100, 100), (150, 130), (220, 180))
    settle(view, wait_until)
    (found,) = view.drawings_of(0)
    assert found.kind == shape
    (start, end) = found.strokes[0]
    assert near(start, (100, 100)) and near(end, (220, 180))
    save(window, wait_until)
    assert in_file(path) == [standard]


def test_the_shape_uses_its_own_colour_and_thickness(window, opened, wait_until):
    view, _ = opened()
    window.set_marker_color(SHAPE_TOOL, (0.13, 0.39, 0.85))
    window.set_line_width(SHAPE_TOOL, 4)
    window.set_line_width(DRAW, 1)
    window.use_writing_tool(SHAPE_TOOL)
    drag(view, 0, (100, 100), (220, 180))
    settle(view, wait_until)
    (found,) = view.drawings_of(0)
    assert found.width == 4 and near(found.color, (0.13, 0.39, 0.85), 0.01)


def test_a_tiny_shape_is_a_slip_of_the_hand(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(SHAPE_TOOL)
    drag(view, 0, (100, 100), (101, 100))
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and not view.modified


def test_the_style_of_pen_and_shapes_is_remembered(window, settings, qt_app):
    window.set_marker_color(DRAW, (0.1, 0.55, 0.25))
    window.set_line_width(DRAW, 8)
    window.set_shape(OVAL)
    assert settings.get(MARKERS_SETTING)["shape"] == OVAL
    again = MainWindow(settings)
    try:
        assert again.marker_styles.width_of(DRAW) == 8
        assert again.marker_styles.shape == OVAL
        assert again.width_actions[DRAW][8.0].isChecked()
        assert again.shape_actions[OVAL].isChecked()
        assert near(again.pdf_view.draw_color, (0.1, 0.55, 0.25), 0.01)
        assert again.pdf_view.draw_width == 8 and again.pdf_view.shape_kind == OVAL
    finally:
        again.close()
        again.deleteLater()


def test_the_menus_offer_thickness_and_opacity(window):
    for kind in (DRAW, SHAPE_TOOL):
        menu = window.color_menus[kind]
        assert not menu.opacity_slider.isHidden()
        assert len(window.width_actions[kind]) == 4
    assert window.color_menus[NOTE].opacity_slider.isHidden()
    assert [a.text() for a in window.shape_actions.values()] == [
        "Flecha",
        "Flecha doble",
        "Flecha en codo",
        "Línea",
        "Recuadro",
        "Óvalo",
        "Triángulo",
        "Rombo",
        "Llave { }",
    ]


# ---- the eraser ----------------------------------------------------------------------


def test_the_eraser_takes_away_what_it_touches(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 100), (200, 100))
    drag(view, 0, (100, 200), (200, 200))
    settle(view, wait_until)
    window.use_writing_tool(ERASER)
    drag(view, 0, (150, 100))
    settle(view, wait_until)
    (left,) = view.drawings_of(0)
    assert near(left.strokes[0][0], (100, 200))
    window.undo()
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 2, "undo brings back what was erased"


def test_passing_the_eraser_over_several_takes_them_all(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(SHAPE_TOOL)
    window.set_shape(LINE)
    for x in (100, 150, 200):
        drag(view, 0, (x, 100), (x, 200))
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 3
    window.use_writing_tool(ERASER)
    drag(view, 0, (80, 150), (100, 150), (125, 150), (150, 150), (175, 150), (200, 150), (230, 150))
    settle(view, wait_until)
    assert view.drawings_of(0) == []
    for _ in range(3):  # each one is its own step
        assert view.can_undo
        window.undo()
        settle(view, wait_until)
    assert len(view.drawings_of(0)) == 3


def test_the_eraser_next_to_a_line_leaves_it(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(SHAPE_TOOL)
    window.set_shape(BOX)
    drag(view, 0, (100, 100), (300, 300))
    settle(view, wait_until)
    window.use_writing_tool(ERASER)
    drag(view, 0, (200, 200))  # in its hollow
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1
    drag(view, 0, (100, 200))  # on its edge
    settle(view, wait_until)
    assert view.drawings_of(0) == []


def test_the_eraser_takes_marks_and_notes_too(window, opened, wait_until):
    view, _ = opened()
    wait_until(lambda: 0 in view._texts)
    text = view._texts[0]
    view.select((0, 0), (0, 12))
    view.mark_selection(HIGHLIGHT)
    assert view.put_note(0, 300, 400, "fuera")
    settle(view, wait_until)
    (mark,) = view.drawings_of(0)
    assert mark.kind == HIGHLIGHT and len(view.notes_of(0)) == 1 and len(text)
    x0, y0, x1, y1 = mark.rects[0]
    window.use_writing_tool(ERASER)
    drag(view, 0, ((x0 + x1) / 2, (y0 + y1) / 2))
    drag(view, 0, (300, 400))
    settle(view, wait_until)
    assert view.drawings_of(0) == [] and view.notes_of(0) == []
    assert view.note_panel is None, "the eraser does not open the note"


def test_the_eraser_leaves_what_another_program_drew(window, sample, tmp_path, wait_until):
    path = tmp_path / "ajeno.pdf"
    with pymupdf.open(sample("boe.pdf")) as doc:
        page = doc[0]
        page.add_line_annot((100, 100), (200, 100))
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    window.use_writing_tool(ERASER)
    drag(view, 0, (150, 100))
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1 and not view.modified


def test_what_is_drawn_is_written_in_the_journal_at_once(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 100), (200, 150))
    settle(view, wait_until)
    assert view.journal is not None and view.journal.count == 1
