"""Tests for the reading cursor (F7): the text of the page for NVDA and the keyboard."""

import shutil

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from app.core import reading


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


def turn_on(window, view, wait_until):
    QTest.keySequence(view, QKeySequence("F7"))
    reader = view.reader
    wait_until(lambda: reader.reading.letters)
    return reader


def test_f7_turns_the_reading_cursor_on_and_off(window, opened, wait_until, qt_app):
    view = opened
    reader = turn_on(window, view, wait_until)
    assert view.reading_cursor and reader.isVisible()
    assert window.reading_cursor_action.isChecked()
    assert reader.hasFocus()
    assert reader.accessibleName() == "Página 1 de 39"
    assert reader.toPlainText().startswith("Constitución Española.")
    assert window.settings.get(reading.CURSOR_SETTING) is True  # remembered
    QTest.keySequence(reader, QKeySequence("F7"))
    qt_app.processEvents()
    assert not view.reading_cursor and not reader.isVisible()
    assert view.hasFocus()
    assert window.settings.get(reading.CURSOR_SETTING) is False


def test_moving_and_selecting_with_the_keys_selects_on_the_page(window, opened, wait_until):
    view = opened
    reader = turn_on(window, view, wait_until)
    QTest.keyClick(reader, Qt.Key.Key_Right)
    assert view._reading_caret == (0, 1)
    for _ in range(12):
        QTest.keyClick(reader, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    chosen = view.selection()
    assert chosen is not None and chosen[0] == (0, 1) and chosen[1][0] == 0
    QTest.keyClick(reader, Qt.Key.Key_Right)  # moving without Mayús lets it go
    assert view.selection() is None


def test_r_highlights_what_the_keyboard_selected(window, opened, wait_until):
    view = opened
    reader = turn_on(window, view, wait_until)
    for _ in range(11):
        QTest.keyClick(reader, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert view.has_selection
    QTest.keyClick(reader, Qt.Key.Key_R)
    wait_until(lambda: view.modified)
    assert reader.hasFocus()  # still reading


def test_moving_past_the_last_line_goes_to_the_next_page(window, opened, wait_until):
    view = opened
    reader = turn_on(window, view, wait_until)
    QTest.keyClick(reader, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(reader, Qt.Key.Key_Down)
    wait_until(lambda: reader.page == 1 and reader.reading.letters)
    assert reader.accessibleName() == "Página 2 de 39"
    assert reader.textCursor().position() == 0
    assert 1 in view._visible_pages()
    QTest.keyClick(reader, Qt.Key.Key_Up)  # and back up: at the last line
    wait_until(lambda: reader.page == 0 and reader.reading.letters)
    assert reader.textCursor().block().next().isValid() is False


def test_page_down_and_up_change_page(window, opened, wait_until):
    view = opened
    reader = turn_on(window, view, wait_until)
    QTest.keyClick(reader, Qt.Key.Key_PageDown)
    QTest.keyClick(reader, Qt.Key.Key_PageDown)
    wait_until(lambda: reader.page == 2 and reader.reading.letters)
    assert 2 in view._visible_pages()
    QTest.keyClick(reader, Qt.Key.Key_PageUp)
    wait_until(lambda: reader.page == 1)


def test_a_click_puts_the_reading_cursor_there(window, opened, wait_until, qt_app):
    view = opened
    reader = turn_on(window, view, wait_until)
    QTest.keyClick(reader, Qt.Key.Key_Down)
    QTest.keyClick(reader, Qt.Key.Key_Down)
    before = view._reading_caret
    place = QPoint(view.viewport().width() // 2, 30)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=place)
    qt_app.processEvents()
    assert view._reading_caret != before
    assert reader.hasFocus()


def test_a_scanned_page_says_it_has_no_text(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False
    path = tmp_path / "escaneado.pdf"
    shutil.copy(sample("escaneado.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages())
    view.set_reading_cursor(True)
    wait_until(lambda: "no tiene texto" in view.reader.toPlainText())


def test_it_comes_on_by_itself_with_a_screen_reader(window, opened, monkeypatch):
    view = opened
    monkeypatch.setattr("app.ui.main_window.QAccessible.isActive", lambda: True)
    window.apply_pen_settings()
    assert view.reading_cursor and window.reading_cursor_action.isChecked()
    window.choose_reading_cursor(False)  # turned off by hand: it stays off
    assert not view.reading_cursor
    assert window.settings.get(reading.WITH_SCREEN_READER_SETTING) is False
    window.apply_pen_settings()
    assert not view.reading_cursor


def test_the_settings_have_it(window):
    dialog = window.open_settings()
    try:
        assert not dialog.reading_cursor_box.isChecked()
        assert dialog.screen_reader_box.isChecked()
        dialog.reading_cursor_box.setChecked(True)
        assert window.pdf_view.reading_cursor
        assert window.reading_cursor_action.isChecked()
    finally:
        dialog.close()


def test_f7_is_a_key_that_can_be_changed(window):
    assert "reading_cursor" in window.key_commands
    assert window.reading_cursor_action.shortcut().toString() == "F7"
