"""Tests for selecting text with the mouse and copying it."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from app.core.document import PdfDocument
from app.ui.pdf_view import END_OF_PAGE


@pytest.fixture
def opened(window, sample, wait_until):
    """The window with a sample open and the letters of its first page ready."""
    window.show_problem_dialogs = False

    def open_it(name="texto-partido.pdf"):
        assert window.open_document(sample(name))
        view = window.pdf_view
        wait_until(lambda: 0 in view._texts)
        return view

    return open_it


def place_of(view, page: int, letter: int, side: float = 0.5) -> QPoint:
    """Where a letter of a page is in the window (``side``: 0 its left edge, 1 its right)."""
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


def copied(view, wait_until) -> str:
    QGuiApplication.clipboard().clear()
    done = []
    view.text_copied.connect(done.append)
    view.copy_selection()
    wait_until(lambda: done)
    view.text_copied.disconnect(done.append)
    return QGuiApplication.clipboard().text()


def test_dragging_over_words_selects_them(opened, wait_until):
    view = opened()
    text = view._texts[0]
    start = text.chars.index("españoles")
    stop = start + len("españoles son")
    drag(view, place_of(view, 0, start, 0.1), place_of(view, 0, stop - 1, 0.9))
    assert view.selection() == ((0, start), (0, stop))
    assert copied(view, wait_until) == "españoles son"


def test_dragging_backwards_selects_the_same(opened, wait_until):
    view = opened()
    start = view._texts[0].chars.index("españoles")
    stop = start + len("españoles")
    drag(view, place_of(view, 0, stop - 1, 0.9), place_of(view, 0, start, 0.1))
    assert view.selection() == ((0, start), (0, stop))


def test_a_selection_over_several_lines_copies_running_text(opened, wait_until):
    view = opened()
    text = view._texts[0]
    start = text.chars.index("Los españoles")
    stop = text.chars.index("ción alguna") + len("ción alguna")
    drag(view, place_of(view, 0, start, 0.1), place_of(view, 0, stop - 1, 0.9))
    assert copied(view, wait_until).endswith("pueda prevalecer discriminación alguna")


def test_the_selection_is_painted(opened, qt_app):
    view = opened()
    before = view.viewport().grab().toImage()
    view.select((0, 0), (0, 40))
    qt_app.processEvents()
    assert view.viewport().grab().toImage() != before


def test_double_click_selects_a_word(opened, wait_until):
    view = opened()
    start = view._texts[0].chars.index("españoles")
    QTest.mouseDClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        place_of(view, 0, start + 3),
    )
    assert copied(view, wait_until) == "españoles"


def test_shift_click_extends_the_selection(opened, wait_until):
    view = opened()
    text = view._texts[0]
    start = text.chars.index("españoles")
    viewport = view.viewport()
    QTest.mouseClick(
        viewport,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        place_of(view, 0, start, 0.1),
    )
    assert not view.has_selection
    stop = start + len("españoles son iguales")
    QTest.mouseClick(
        viewport,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        place_of(view, 0, stop - 1, 0.9),
    )
    assert copied(view, wait_until) == "españoles son iguales"


def test_a_click_or_escape_removes_the_selection(opened):
    view = opened()
    seen = []
    view.selection_changed.connect(seen.append)
    view.select((0, 0), (0, 10))
    assert view.has_selection and seen == [True]
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert not view.has_selection and seen == [True, False]
    view.select((0, 0), (0, 10))
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        place_of(view, 0, 30),
    )
    assert not view.has_selection


def test_select_all_and_copy_takes_every_page(opened, wait_until):
    view = opened("texto-dificil.pdf")
    view.select_all()
    assert view.selection() == ((0, 0), (1, END_OF_PAGE))
    text = copied(view, wait_until)
    assert text.startswith("Temario de prueba")
    assert "La oficina resolverá el conflicto con eficacia." in text
    assert text.rstrip().endswith("Página 2")


def test_ctrl_c_and_ctrl_a_work_on_the_document(window, opened, wait_until):
    view = opened()
    view.setFocus()
    done = []
    view.text_copied.connect(done.append)
    window.select_all_action.trigger()
    assert view.has_selection
    QGuiApplication.clipboard().clear()
    window.copy_action.trigger()
    wait_until(lambda: done)
    assert "Los españoles son iguales" in QGuiApplication.clipboard().text()
    assert "Texto copiado" in window.statusBar().currentMessage()


def test_copy_without_selection_explains_what_to_do(window, opened, wait_until):
    opened()
    window.feature_actions["copy"].trigger()
    assert "Selecciona antes el texto" in window.statusBar().currentMessage()


def test_copy_without_document(window):
    window.feature_actions["copy"].trigger()
    assert "Abre primero" in window.statusBar().currentMessage()


def test_ctrl_c_in_the_search_box_is_left_alone(window, opened):
    opened()
    assert window.copy_action.shortcutContext() == Qt.ShortcutContext.WidgetShortcut
    assert window.copy_action in window.pdf_view.actions()


def test_a_scanned_page_says_there_is_no_text(window, opened):
    view = opened("escaneado.pdf")
    QTest.mousePress(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(300, 200),
    )
    assert not view.has_selection
    assert "no tiene texto que seleccionar" in window.statusBar().currentMessage()


def test_selection_follows_the_turned_page(opened, wait_until):
    view = opened()
    view.rotate_view()
    wait_until(lambda: 0 in view._texts)
    start = view._texts[0].chars.index("españoles")
    stop = start + len("españoles")
    # Turned a quarter, the line runs from top to bottom: aim at the letters themselves.
    drag(view, place_of(view, 0, start), place_of(view, 0, stop))
    chosen = view.selection()
    assert chosen is not None
    assert abs(chosen[0][1] - start) <= 1 and abs(chosen[1][1] - stop) <= 1


def test_the_pointer_changes_over_text(opened):
    view = opened()
    start = view._texts[0].chars.index("españoles")
    view._update_pointer(place_of(view, 0, start))
    assert view.viewport().cursor().shape() == Qt.CursorShape.IBeamCursor
    view._update_pointer(QPoint(5, 5))
    assert view.viewport().cursor().shape() == Qt.CursorShape.ArrowCursor


def test_opening_another_document_forgets_the_selection(window, opened, sample):
    view = opened()
    view.select((0, 0), (0, 10))
    view.set_document(PdfDocument(sample("boe.pdf")))
    assert not view.has_selection


def test_dragging_below_the_window_moves_the_document(opened, wait_until, qt_app):
    view = opened("boe.pdf")
    viewport = view.viewport()
    start = place_of(view, 0, 5)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    below = QPoint(start.x(), viewport.height() + 80)
    QTest.mouseMove(viewport, below)
    wait_until(lambda: view.verticalScrollBar().value() > 300)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, below)
    assert not view._autoscroll.isActive()
    assert view.has_selection
