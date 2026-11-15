"""Tests for the keys of the tools: changing tools without the mouse."""

import shutil

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from app.core.commands import HIGHLIGHT
from app.core.drawing import DRAW, ERASER
from app.core.tool_keys import FAVOURITE_KEYS, TOOL_KEYS, TOOL_KEYS_SETTING
from app.ui.features import FEATURES, Mode


@pytest.fixture
def opened(window, sample, tmp_path, wait_until, qt_app):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
        window.activateWindow()
        view.setFocus()
        qt_app.processEvents()
        return view

    return open_it


def press(view, key: str) -> None:
    """Press a key on the page, as the keyboard does (shortcuts included)."""
    QTest.keySequence(view, QKeySequence(key))


def test_every_key_belongs_to_a_tool_that_exists(window):
    known = {feature.id for feature in FEATURES}
    assert set(TOOL_KEYS) <= known
    assert set(TOOL_KEYS) <= set(window.feature_handlers)


def test_a_key_takes_its_tool_and_the_same_key_puts_it_down(window, opened):
    view = opened()
    press(view, "D")
    assert view.markup_tool == DRAW
    assert window.mode is Mode.STUDY, "the tools come to sight"
    assert window.feature_actions["draw"].isChecked()
    press(view, "B")
    assert view.markup_tool == ERASER
    press(view, "B")
    assert view.markup_tool == ""


def test_the_key_of_a_marker_marks_what_is_selected(window, opened, wait_until):
    view = opened()
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 12))
    press(view, "R")
    wait_until(lambda: not view._changing and not view._asked_notes)
    assert [item.kind for item in view.drawings_of(0)] == [HIGHLIGHT]


def test_the_o_key_hides_and_shows_the_annotations(window, opened):
    view = opened()
    press(view, "O")
    assert not view.annotations_shown
    press(view, "O")
    assert view.annotations_shown


def test_escape_still_puts_the_tool_down(window, opened):
    view = opened()
    press(view, "N")
    assert view.markup_tool == "note"
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.markup_tool == ""


def test_the_digits_take_the_favourite_tools(window, opened):
    view = opened()
    window.set_marker_color(DRAW, (0.1, 0.2, 0.9))
    view.set_markup_tool("")
    window.add_favourite(DRAW)
    window.set_marker_color(DRAW, (0.0, 0.0, 0.0))
    view.set_markup_tool("")
    press(view, "1")
    assert view.markup_tool == DRAW
    assert view.draw_color == pytest.approx((0.1, 0.2, 0.9), abs=0.01)
    view.set_markup_tool("")
    press(view, "2")  # there is no second favourite
    assert view.markup_tool == ""


def test_in_the_search_box_a_letter_is_a_letter(window, opened, qt_app):
    view = opened()
    window.search_box.setFocus()
    qt_app.processEvents()
    QTest.keyClicks(window.search_box, "dr")
    assert window.search_box.text() == "dr" and view.markup_tool == ""


def test_the_keys_are_said_where_the_tools_are(window):
    assert "(tecla R)" in window.feature_actions["highlight"].toolTip()
    assert "(tecla O)" in window.feature_actions["hide_annotations"].toolTip()


def test_the_keys_can_be_turned_off(window, opened):
    view = opened()
    dialog = window.open_settings()
    assert dialog.tool_keys_box.isChecked()
    dialog.tool_keys_box.setChecked(False)
    dialog.close()
    assert window.settings.get(TOOL_KEYS_SETTING) is False
    view.setFocus()
    press(view, "D")
    press(view, "1")
    assert view.markup_tool == ""
    assert "tecla" not in window.feature_actions["draw"].toolTip()
    assert all(action.shortcut().isEmpty() for action in window.tool_key_actions.values())
    window.settings.set(TOOL_KEYS_SETTING, True)
    window.apply_tool_keys()
    press(view, "D")
    assert view.markup_tool == DRAW


def test_every_open_document_answers_to_the_keys(window, opened):
    opened("boe.pdf")
    second = opened("largo.pdf")
    press(second, "S")
    assert second.markup_tool == "underline"
    assert len(window.favourite_key_actions) == len(FAVOURITE_KEYS)
