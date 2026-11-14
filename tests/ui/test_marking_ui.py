"""Tests for highlighting, underlining and striking out text in the window."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from app.ui.features import Mode


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    """The window with a copy of a sample open and the letters of its first page ready."""
    window.show_problem_dialogs = False

    def open_it(name="texto-partido.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view._texts and 0 in view.cached_pages())
        return view, path

    return open_it


def place_of(view, page: int, letter: int, side: float = 0.5) -> QPoint:
    x0, y0, x1, y1 = view._shown_rect(page, view._texts[page].box(letter))
    zoom = view._render_zoom()
    x = view._page_left(page) + (x0 + (x1 - x0) * side) * zoom
    y = view._tops[page] - view._scroll_y() + (y0 + y1) / 2 * zoom
    return QPoint(view._to_units(x), view._to_units(y))


def drag(view, start: QPoint, stop: QPoint) -> None:
    viewport = view.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(viewport, stop)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, stop)


def select_words(view, words: str) -> None:
    start = view._texts[0].chars.index(words)
    view.select((0, start), (0, start + len(words)))


def picture(view, page: int = 0) -> bytes:
    image = view._cache[page][1]
    return bytes(image.constBits())


def marks_in_file(path, page: int = 0):
    with pymupdf.open(path) as doc:
        sheet = doc[page]
        return [annotation.type[1] for annotation in sheet.annots() or ()]


def settle(view, wait_until, changes: int) -> None:
    """Wait until ``changes`` changes are done and the pages are drawn again."""
    wait_until(lambda: view._changes >= changes and not view._changing and not view._stale)


def test_the_tools_are_in_the_study_mode_and_save_is_at_hand(window):
    from app.ui.features import features_of

    names = [feature.id for feature in features_of(Mode.STUDY)]
    assert names[:5] == ["undo", "redo", "highlight", "underline", "strikeout"]
    toolbar = window.mode_toolbars[Mode.STUDY]
    assert toolbar.actions()[0] is window.feature_actions["save"]
    for mode in (Mode.FILL_SIGN, Mode.ORGANIZE):
        assert window.mode_toolbars[mode].actions()[0] is window.feature_actions["save"]
    for name in ("highlight", "underline", "strikeout", "undo", "redo"):
        assert name in window.feature_handlers  # no longer "not available yet"


def test_highlighting_the_selection_shows_at_once_and_waits_to_be_saved(window, opened, wait_until):
    view, path = opened()
    on_disk = path.read_bytes()
    clean = picture(view)
    select_words(view, "españoles son")
    window.feature_actions["highlight"].trigger()
    settle(view, wait_until, 1)
    assert picture(view) != clean, "the mark is on the page"
    assert not view.has_selection
    assert view.modified and window.save_action.isEnabled()
    assert path.read_bytes() == on_disk, "the PDF is not touched until it is saved"
    assert not window.feature_actions["highlight"].isChecked(), "it was a one-off"

    window.save_document()
    wait_until(lambda: not view.saving)
    assert marks_in_file(path) == ["Highlight"]
    assert not view.modified and not window.save_action.isEnabled()


@pytest.mark.parametrize(
    ("tool", "pdf_type"), [("underline", "Underline"), ("strikeout", "StrikeOut")]
)
def test_underline_and_strike_out(window, opened, wait_until, tool, pdf_type):
    view, path = opened()
    select_words(view, "españoles son")
    window.feature_actions[tool].trigger()
    settle(view, wait_until, 1)
    window.save_document()
    wait_until(lambda: not view.saving)
    assert marks_in_file(path) == [pdf_type]


def test_with_nothing_selected_the_marker_stays_in_hand(window, opened, wait_until):
    view, path = opened()
    action = window.feature_actions["highlight"]
    action.trigger()
    assert view.markup_tool == "highlight" and action.isChecked()
    assert "selecciona texto" in window.statusBar().currentMessage()
    assert view._changes == 0

    text = view._texts[0]
    start = text.chars.index("españoles")
    drag(view, place_of(view, 0, start, 0.1), place_of(view, 0, start + 8, 0.9))
    settle(view, wait_until, 1)
    assert not view.has_selection and view.markup_tool == "highlight", "still in hand"
    other = text.chars.index("iguales")
    drag(view, place_of(view, 0, other, 0.1), place_of(view, 0, other + 6, 0.9))
    settle(view, wait_until, 2)

    action.trigger()  # pressed again: put down
    assert view.markup_tool == "" and not action.isChecked()
    drag(view, place_of(view, 0, start, 0.1), place_of(view, 0, start + 8, 0.9))
    assert view.has_selection and view._changes == 2, "now it only selects"
    window.save_document()
    wait_until(lambda: not view.saving)
    assert marks_in_file(path) == ["Highlight", "Highlight"]


def test_taking_another_marker_swaps_it_and_escape_puts_it_down(window, opened):
    view, _path = opened()
    window.feature_actions["highlight"].trigger()
    window.feature_actions["underline"].trigger()
    assert view.markup_tool == "underline"
    assert window.feature_actions["underline"].isChecked()
    assert not window.feature_actions["highlight"].isChecked()
    view.setFocus()
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.markup_tool == "" and not window.feature_actions["underline"].isChecked()


def test_a_double_click_with_the_marker_marks_the_word(window, opened, wait_until):
    view, _path = opened()
    window.feature_actions["highlight"].trigger()
    start = view._texts[0].chars.index("españoles")
    QTest.mouseDClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        place_of(view, 0, start + 3),
    )
    settle(view, wait_until, 1)
    assert view.can_undo


def test_undo_and_redo(window, opened, wait_until):
    view, path = opened()
    assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()
    assert not window.feature_actions["undo"].isEnabled()
    clean = picture(view)
    select_words(view, "españoles son")
    window.feature_actions["highlight"].trigger()
    settle(view, wait_until, 1)
    marked = picture(view)
    assert window.undo_action.isEnabled() and window.feature_actions["undo"].isEnabled()

    window.undo_action.trigger()
    settle(view, wait_until, 2)
    assert picture(view) == clean
    assert not window.undo_action.isEnabled() and window.redo_action.isEnabled()

    window.redo_action.trigger()
    settle(view, wait_until, 3)
    assert picture(view) == marked
    assert window.undo_action.isEnabled() and not window.redo_action.isEnabled()

    window.undo_action.trigger()
    settle(view, wait_until, 4)
    window.save_document()
    wait_until(lambda: not view.saving)
    assert marks_in_file(path) == []


def test_a_new_mark_forgets_what_was_undone(window, opened, wait_until):
    view, _path = opened()
    select_words(view, "españoles son")
    view.mark_selection("highlight")
    settle(view, wait_until, 1)
    view.undo()
    settle(view, wait_until, 2)
    assert view.can_redo
    select_words(view, "iguales")
    view.mark_selection("underline")
    settle(view, wait_until, 3)
    assert not view.can_redo and view.can_undo


def test_undo_with_nothing_done_says_so(window, opened):
    opened()
    window.undo()
    assert "No hay nada que deshacer" in window.statusBar().currentMessage()
    window.redo()
    assert "No hay nada que rehacer" in window.statusBar().currentMessage()


def test_the_usual_shortcuts_for_undo_and_redo(window):
    assert window.undo_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Undo)
    assert QKeySequence("Ctrl+Y") in window.redo_action.shortcuts()
    assert QKeySequence("Ctrl+Shift+Z") in window.redo_action.shortcuts()


def test_ctrl_z_in_the_document_undoes_and_in_the_search_box_does_not(window, opened, wait_until):
    view, _path = opened()
    select_words(view, "españoles son")
    view.mark_selection("highlight")
    settle(view, wait_until, 1)
    window.search_box.setFocus()
    QTest.keyClicks(window.search_box, "ley")
    QTest.keyClick(window.search_box, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert view.can_undo, "the mark is still there: Ctrl+Z undid the typing"
    view.setFocus()
    QTest.keyClick(view, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    settle(view, wait_until, 2)
    assert not view.can_undo


def test_each_tab_has_its_own_marker_and_history(window, opened, wait_until):
    first, _ = opened("texto-partido.pdf")
    select_words(first, "españoles son")
    first.mark_selection("highlight")
    settle(first, wait_until, 1)
    window.feature_actions["underline"].trigger()
    second, _ = opened("boe.pdf")
    assert not window.undo_action.isEnabled()
    assert not window.feature_actions["underline"].isChecked()
    window.document_tabs.setCurrentIndex(0)
    assert window.undo_action.isEnabled()
    assert window.feature_actions["underline"].isChecked()


def test_closing_and_opening_again_shows_only_what_was_saved(window, opened, wait_until):
    view, path = opened()
    select_words(view, "españoles son")
    view.mark_selection("highlight")
    settle(view, wait_until, 1)
    window.save_document()
    wait_until(lambda: not view.saving)
    select_words(view, "iguales")
    view.mark_selection("strikeout")  # not saved
    settle(view, wait_until, 2)
    window.close_document()
    assert marks_in_file(path) == ["Highlight"]


def test_the_thumbnail_is_drawn_again_after_a_mark(window, opened, wait_until):
    from app.ui.side_panel import Tab

    view, _path = opened()
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    wait_until(lambda: 0 in thumbnails.drawn_pages())
    select_words(view, "españoles son")
    view.mark_selection("highlight")
    wait_until(lambda: 0 not in thumbnails.drawn_pages() or view._changes == 1)
    settle(view, wait_until, 1)
    wait_until(lambda: 0 in thumbnails.drawn_pages())


def test_marking_without_a_document_asks_to_open_one(window):
    window.feature_actions["highlight"].trigger()
    assert "Abre primero" in window.statusBar().currentMessage()
    assert not window.feature_actions["highlight"].isChecked()


def test_the_right_click_menu_marks_through_the_same_path(window, opened, wait_until):
    view, _path = opened()
    assert view.mark_selection("highlight") is False, "nothing selected"
    select_words(view, "españoles son")
    assert view.mark_selection("glitter") is False
    assert view.mark_selection("underline") is True
    settle(view, wait_until, 1)
