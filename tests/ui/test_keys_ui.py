"""Tests for choosing the key of every function ("like the controls of a game")."""

import shutil

import pytest
import shiboken6
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from app.core import shortcuts
from app.core.drawing import DRAW
from app.ui.features import FEATURES
from app.ui.keys_tab import KeyCaptureDialog


@pytest.fixture
def opened(window, sample, tmp_path, wait_until, qt_app):
    window.show_problem_dialogs = False
    path = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    window.activateWindow()
    view.setFocus()
    qt_app.processEvents()
    return view


@pytest.fixture
def keys(window):
    dialog = window.open_settings()
    tab = dialog.keys_tab
    yield tab
    if shiboken6.isValid(dialog):  # pressing a key on the page closes it first
        dialog.close()


def press(view, key: str) -> None:
    """Press a key on the page, with the settings window already closed."""
    for widget in view.window().findChildren(QDialog):
        widget.close()
    view.window().activateWindow()
    view.setFocus()
    QTest.keySequence(view, QKeySequence(key))


def test_every_working_function_can_have_a_key(window):
    working = {feature.id for feature in FEATURES if feature.id in window.feature_handlers}
    assert working <= set(window.key_commands)
    for command_id in ("close_tab", "settings", "mode_2", "favourite_1", "finder", "paste"):
        assert command_id in window.key_commands
    assert shortcuts.clashes(window.settings, window.key_commands) == {}


def test_the_usual_keys_are_on_their_actions(window):
    assert window.save_action.shortcut().toString() == "Ctrl+S"
    assert [k.toString() for k in window.redo_action.shortcuts()] == ["Ctrl+Y", "Ctrl+Shift+Z"]
    zoom_in = window.key_commands["zoom_in"].action
    assert [k.toString() for k in zoom_in.shortcuts()] == ["Ctrl++", "Ctrl+="]


def test_the_keys_tab_lists_every_function_in_groups(window, keys):
    assert keys.tree.topLevelItemCount() >= 6
    assert len(keys._items) == len(window.key_commands)
    item = keys._items["underline"]
    assert item.text(1) == "S"
    assert keys._items["redo"].text(2) != ""


def test_changing_the_key_of_a_tool(window, opened, keys):
    view = opened
    assert keys.assign("underline", "U")
    assert keys._items["underline"].text(1) == "U"
    assert keys._items["underline"].font(0).italic()  # changed by hand
    press(view, "U")
    assert view.markup_tool == "underline"
    view.set_markup_tool("")
    press(view, "S")
    assert view.markup_tool == ""  # the old key is free now
    assert "(tecla U)" in window.feature_actions["underline"].toolTip()
    assert shortcuts.keys_of(window.settings, "underline") == ("U",)


def test_a_key_of_another_function_is_taken_from_it(window, opened, keys):
    view = opened
    assert "Resaltar" in keys.verdict("draw", "R")
    assert keys.assign("draw", "R")
    assert "Se ha quitado de «Resaltar»" in keys.message.text()
    assert shortcuts.keys_of(window.settings, "highlight") == ()
    assert keys._items["highlight"].text(1) == ""
    press(view, "R")
    assert view.markup_tool == DRAW  # not ambiguous: only one has it


def test_the_keys_that_move_through_the_document_cannot_be_given(window, keys):
    assert not keys.assign("summary", "Space")
    assert "moverse" in keys.message.text()
    assert shortcuts.keys_of(window.settings, "summary") == ()


def test_any_function_with_a_combination(window, opened, keys, qt_app):
    view = opened
    assert keys.assign("hide_annotations", "Ctrl+Shift+H")
    press(view, "Ctrl+Shift+H")
    assert not view.annotations_shown
    # A combination answers also with the keyboard somewhere else.
    window.search_box.setFocus()
    qt_app.processEvents()
    QTest.keySequence(window.search_box, QKeySequence("Ctrl+Shift+H"))
    assert view.annotations_shown


def test_a_plain_key_for_a_window_function_only_counts_on_the_document(
    window, opened, keys, qt_app
):
    view = opened
    assert keys.assign("side_panel", "P")
    press(view, "P")
    assert window.current_document.side_panel.isVisible()
    window.search_box.setFocus()
    qt_app.processEvents()
    QTest.keyClicks(window.search_box, "p")
    assert window.search_box.text() == "p"


def test_a_second_key(window, opened, keys):
    view = opened
    assert keys.assign("draw", "L", slot=1)
    assert shortcuts.keys_of(window.settings, "draw") == ("D", "L")
    press(view, "L")
    assert view.markup_tool == DRAW


def test_remove_and_reset(window, keys):
    keys.clear("save")
    assert window.save_action.shortcut().isEmpty()
    keys.select("save")
    assert keys.reset_button.isEnabled()
    keys.reset("save")
    assert window.save_action.shortcut().toString() == "Ctrl+S"
    keys.assign("underline", "U")
    keys.assign("highlight", "Ctrl+S")  # taken from Guardar
    keys.reset()
    assert shortcuts.keys_of(window.settings, "underline") == ("S",)
    assert window.save_action.shortcut().toString() == "Ctrl+S"
    assert shortcuts.clashes(window.settings, window.key_commands) == {}


def test_resetting_one_takes_its_usual_key_back(window, keys):
    keys.assign("summary", "S")  # taken from Subrayar
    keys.reset("underline")
    assert shortcuts.keys_of(window.settings, "underline") == ("S",)
    assert shortcuts.keys_of(window.settings, "summary") == ()


def test_the_list_can_be_searched_by_name_or_key(keys):
    keys.filter.setText("subray")
    assert not keys._items["underline"].isHidden()
    assert keys._items["save"].isHidden()
    keys.filter.setText("ctrl+s")
    assert not keys._items["save"].isHidden()
    keys.filter.setText("")
    assert not keys._items["save"].isHidden()


def test_the_change_button_asks_for_a_key(window, keys):
    keys.select("summary")
    keys.capture_answer = "F8"
    keys.change_button.click()
    assert shortcuts.keys_of(window.settings, "summary") == ("F8",)


def test_the_capture_window_says_at_once_whether_a_key_is_free(window, keys):
    dialog = KeyCaptureDialog(keys, "summary")
    dialog.edit.setKeySequence(QKeySequence("R"))
    assert "Resaltar" in dialog.note.text()
    dialog.edit.setKeySequence(QKeySequence("Space"))
    assert "moverse" in dialog.note.text()
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()
    dialog.edit.setKeySequence(QKeySequence("F8"))
    assert dialog.key == "F8" and "Libre" in dialog.note.text()
    assert ok.isEnabled()
    dialog.deleteLater()


def test_the_keys_are_kept_for_the_next_time(window, settings, keys):
    keys.assign("underline", "U")
    from app.ui.main_window import MainWindow

    other = MainWindow(settings)
    try:
        assert [k.toString() for k in other.tool_key_actions["underline"].shortcuts()] == ["U"]
    finally:
        other.unsaved_answer = "discard"
        other.close()
        other.deleteLater()
