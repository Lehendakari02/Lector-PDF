"""Tests for searching inside a document from the window."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest


@pytest.fixture
def opened(window, sample, wait_until):
    """The main window with the split-words sample open and the search panel."""
    window.show_problem_dialogs = False

    def open_and_search(name="texto-partido.pdf"):
        assert window.open_document(sample(name))
        wait_until(lambda: 0 in window.pdf_view.cached_pages())
        window.show_search()
        return window.search_panel

    return open_and_search


def search(panel, text, wait_until):
    panel.box.setText(text)
    panel.search_now()
    wait_until(lambda: not panel._searching)


def test_search_needs_a_document(window):
    window.show_search()
    assert window.search_dock.isHidden()
    assert "Abre un documento" in window.statusBar().currentMessage()


def test_ctrl_f_and_the_button_open_the_search(window, opened, qt_app):
    panel = opened()
    window.close_search()
    assert window.search_dock.isHidden()
    assert window.search_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Find)
    window.search_action.trigger()
    assert not window.search_dock.isHidden()
    window.close_search()
    window.feature_actions["search"].trigger()
    assert not window.search_dock.isHidden()
    assert panel.box.accessibleName()


def test_the_three_promises_in_the_window(opened, wait_until):
    panel = opened()
    search(panel, "articulo", wait_until)
    assert panel.status.text() == "Resultado 1 de 2"
    assert panel.results.count() == 2
    assert "[Artículo]" in panel.results.item(1).text()

    panel.whole_word.setChecked(True)
    search(panel, "año", wait_until)
    assert panel.results.count() == 3
    assert all("[año]" in panel.results.item(row).text() for row in range(3))

    search(panel, "ano", wait_until)
    assert panel.results.count() == 1
    assert "[ano]" in panel.results.item(0).text()


def test_typing_searches_after_a_short_pause(opened, wait_until):
    panel = opened()
    QTest.keyClicks(panel.box, "camion")
    assert panel.results.count() == 0
    wait_until(lambda: panel.results.count() == 1)


def test_results_are_marked_on_the_page(window, opened, wait_until):
    panel = opened()
    search(panel, "articulo", wait_until)
    marks = window.pdf_view.search_marks()
    assert len(marks[0]) == 2
    assert window.pdf_view._current_mark is panel.hits[0]
    # The marks are really painted: the page is no longer the plain one.
    plain = window.pdf_view._cache[0][1]
    shown = window.pdf_view.viewport().grab().toImage()
    zoom = window.pdf_view._render_zoom()
    x0, y0, x1, y1 = panel.hits[0].rects[0]
    x = window.pdf_view._page_left(0) + round((x0 + x1) / 2 * zoom)
    y = window.pdf_view._tops[0] + round((y0 + y1) / 2 * zoom)
    page_x, page_y = round((x0 + x1) / 2 * zoom), round((y0 + y1) / 2 * zoom)
    assert shown.pixelColor(x, y) != plain.pixelColor(page_x, page_y)
    margin = shown.pixelColor(window.pdf_view._page_left(0) + 5, window.pdf_view._tops[0] + 5)
    assert margin == plain.pixelColor(5, 5)


def test_up_and_down_arrows_walk_through_the_results(window, opened, wait_until):
    panel = opened("boe.pdf")
    search(panel, "articulo 27", wait_until)
    assert panel.current == 0
    QTest.keyClick(panel.box, Qt.Key.Key_Down)
    assert panel.current == 1
    QTest.keyClick(panel.box, Qt.Key.Key_Up)
    assert panel.current == 0
    # Left and right still move through the letters of the word.
    panel.box.setCursorPosition(3)
    QTest.keyClick(panel.box, Qt.Key.Key_Left)
    assert panel.box.cursorPosition() == 2 and panel.current == 0


def test_enter_and_shift_enter_walk_through_the_results(window, opened, wait_until):
    panel = opened("boe.pdf")
    search(panel, "articulo 27", wait_until)
    assert panel.status.text() == "Resultado 1 de 2"
    assert window.pdf_view.current_page == 7

    QTest.keyClick(panel.box, Qt.Key.Key_Return)
    assert panel.status.text() == "Resultado 2 de 2"
    assert window.pdf_view.current_page == 31
    assert panel.results.currentRow() == 1

    QTest.keyClick(panel.box, Qt.Key.Key_Return)  # goes round to the first
    assert panel.current == 0
    QTest.keyClick(panel.box, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert panel.current == 1
    panel.previous_button.click()
    assert panel.current == 0
    panel.next_button.click()
    assert panel.current == 1


def test_search_starts_from_the_page_being_read(window, opened, wait_until):
    panel = opened("boe.pdf")
    window.pdf_view.scroll_to_page(20)
    search(panel, "articulo 27", wait_until)
    assert panel.status.text() == "Resultado 2 de 2", "the first result after page 21"
    assert window.pdf_view.current_page == 31


def test_clicking_a_result_goes_there(window, opened, wait_until):
    panel = opened("boe.pdf")
    search(panel, "articulo 27", wait_until)
    panel.results.setCurrentRow(1)
    assert panel.current == 1
    assert window.pdf_view.current_page == 31


def test_nothing_found(opened, wait_until):
    panel = opened()
    search(panel, "xilofono", wait_until)
    assert panel.status.text() == "Sin resultados"
    assert not panel.next_button.isEnabled()
    QTest.keyClick(panel.box, Qt.Key.Key_Return)  # must not fail
    search(panel, "", wait_until)
    assert panel.status.text() == ""


def test_too_many_results_are_cut_and_said(opened, wait_until):
    panel = opened("largo.pdf")
    search(panel, "a", wait_until)
    assert panel.results.count() == 5000
    assert "Hay más" in panel.status.text()


def test_escape_closes_the_search_and_removes_the_marks(window, opened, wait_until):
    panel = opened()
    search(panel, "articulo", wait_until)
    QTest.keyClick(panel.box, Qt.Key.Key_Escape)
    assert window.search_dock.isHidden()
    assert window.pdf_view.search_marks() == {}
    # Opening it again keeps what was typed, ready to be replaced.
    window.show_search()
    assert panel.box.text() == "articulo"


def test_opening_another_document_searches_it_again(window, opened, sample, wait_until):
    panel = opened()
    search(panel, "articulo 27", wait_until)
    assert panel.results.count() == 0
    window.open_document(sample("boe.pdf"))
    wait_until(lambda: not panel._searching)
    assert panel.results.count() == 2
