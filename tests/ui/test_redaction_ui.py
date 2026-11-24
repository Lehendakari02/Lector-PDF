"""Tests for «Tapar datos» in the window: dragging a box, the selected text and
«Buscar y tapar», with Deshacer, saving and the warning."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.ui.main_window import COVER_WARNING_SETTING, Mode
from app.ui.pdf_view import REDACT_TOOL

WORD = "Constitución"


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False
    window.cover_warning_answer = True

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages())
        return view, path

    return open_it


def place(view, page: int, x: float, y: float) -> QPoint:
    """Where a point of a page is in the window."""
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view.saving)


def saved_text(path, page=0) -> str:
    with pymupdf.open(path) as doc:
        return doc[page].get_text()


def word_box(path, page=0):
    with pymupdf.open(path) as doc:
        rect = doc[page].search_for(WORD)[0]
        return (rect.x0, rect.y0, rect.x1, rect.y1)


def test_dragging_a_box_covers_what_is_under_it(window, opened, wait_until):
    view, path = opened()
    x0, y0, x1, y1 = word_box(path)
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["redact"].trigger()
    assert view.markup_tool == REDACT_TOOL
    assert window.feature_actions["redact"].isChecked()
    start = place(view, 0, x0 - 2, y0 - 2)
    end = place(view, 0, x1 + 2, y1 + 2)
    viewport = view.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(viewport, (start + end) / 2)
    QTest.mouseMove(viewport, end)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    settle(view, wait_until)
    assert view.breaks_signatures
    assert window.save_document()
    settle(view, wait_until)
    assert WORD not in saved_text(path)
    assert view.markup_tool == REDACT_TOOL, "it stays in hand for the next box"


def test_a_click_covers_nothing(window, opened, wait_until):
    view, path = opened()
    window.cover_data()
    point = place(view, 0, 100, 100)
    QTest.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )
    settle(view, wait_until)
    assert not view.can_undo


def test_the_selected_text_and_undoing_it(window, opened, wait_until):
    view, path = opened()
    wait_until(lambda: 0 in view._texts)
    text = view._texts[0]
    start = "".join(text.chars).index(WORD)
    view.select((0, start), (0, start + len(WORD)))
    assert window.cover_data()
    settle(view, wait_until)
    assert not view.has_selection
    assert view.undo()
    settle(view, wait_until)
    assert view.redo()
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    assert WORD not in saved_text(path)


def test_buscar_y_tapar_covers_it_everywhere(window, opened, wait_until):
    view, path = opened()
    window.cover_text_answer = "BOE-A-1978-31229"
    assert window.cover_found_text()
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    with pymupdf.open(path) as doc:
        assert not any("BOE-A-1978-31229" in page.get_text() for page in doc)
    assert view.can_undo


def test_a_text_that_is_not_there_says_so(window, opened, wait_until):
    view, _path = opened()
    window.cover_found_text("palabra que no está en el BOE")
    settle(view, wait_until)
    assert "no está en el documento" in window.statusBar().currentMessage()
    assert not view.modified


def test_the_warning_comes_once_and_can_be_cancelled(window, opened):
    view, _path = opened()
    window.cover_warning_answer = False
    assert not window.cover_data()
    assert view.markup_tool != REDACT_TOOL
    window.cover_warning_answer = True
    assert window.cover_data()
    view.set_markup_tool("")
    window.cover_warning_answer = False  # not asked again in this document
    assert window.cover_data()


def test_the_warning_can_be_left_off(window, opened):
    view, _path = opened()
    window.settings.set(COVER_WARNING_SETTING, False)
    window.cover_warning_answer = False  # would cancel if it were asked
    assert window.cover_data()
    assert view.markup_tool == REDACT_TOOL


def test_pressing_the_button_again_leaves_the_box(window, opened):
    view, _path = opened()
    window.cover_data()
    window.feature_actions["redact"].trigger()
    assert view.markup_tool == ""
    assert not window.feature_actions["redact"].isChecked()
