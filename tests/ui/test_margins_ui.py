"""Tests for adding blank margins from the window."""

import shutil

import pymupdf
import pytest

from app.core.margins import cm
from app.ui.margin_dialog import BELOW, BOTH, LEFT, RIGHT, MarginChoice, MarginDialog, remembered


def open_copy(window, sample, tmp_path, wait_until, name="boe.pdf"):
    window.show_problem_dialogs = False
    path = tmp_path / name
    shutil.copy(sample(name), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages())
    return view, path


def settle(view, wait_until):
    wait_until(lambda: not view._changing)


def test_a_margin_on_the_right_of_the_page_being_read(window, sample, tmp_path, wait_until):
    view, path = open_copy(window, sample, tmp_path, wait_until)
    view.scroll_to_page(4)
    width = view.page_sizes()[4].width
    window.margin_answer = MarginChoice(RIGHT, 5.0, False)
    window.feature_actions["margins"].trigger()
    settle(view, wait_until)
    assert view.page_sizes()[4].width == pytest.approx(width + cm(5))
    assert view.page_sizes()[3].width == pytest.approx(width), "only that page"
    assert view.current_page == 4, "the place being read stays"
    wait_until(lambda: 4 in view.cached_pages() and 4 not in view._stale)
    window.save_document()
    wait_until(lambda: not view.saving)
    with pymupdf.open(path) as doc:
        assert doc[4].rect.width == pytest.approx(width + cm(5), abs=0.01)
    assert view.undo()
    settle(view, wait_until)
    assert view.page_sizes()[4].width == pytest.approx(width)


def test_on_the_left_the_letters_move_with_the_page(window, sample, tmp_path, wait_until):
    view, _path = open_copy(window, sample, tmp_path, wait_until)
    wait_until(lambda: 0 in view._texts)
    first = view._texts[0].box(0)[0]
    window.margin_answer = MarginChoice(LEFT, 3.0, False)
    assert window.add_margin()
    settle(view, wait_until)
    view._want_text(0)
    wait_until(lambda: 0 in view._texts)
    assert view._texts[0].box(0)[0] == pytest.approx(first + cm(3), abs=0.1)


def test_every_page_both_sides(window, sample, tmp_path, wait_until):
    view, _path = open_copy(window, sample, tmp_path, wait_until)
    widths = [view.page_sizes()[page].width for page in range(view.page_count)]
    window.margin_answer = MarginChoice(BOTH, 3.0, True)
    assert window.add_margin()
    settle(view, wait_until)
    assert [view.page_sizes()[page].width for page in range(view.page_count)] == pytest.approx(
        [width + 2 * cm(3) for width in widths]
    )


def test_the_dialog_remembers_the_last_choice(window, sample, tmp_path, wait_until):
    view, _path = open_copy(window, sample, tmp_path, wait_until)
    assert remembered(window.settings) == MarginChoice(RIGHT, 5.0, False), "5 cm on the right"
    window.margin_answer = MarginChoice(BELOW, 8.0, False)
    window.add_margin()
    settle(view, wait_until)
    assert remembered(window.settings) == MarginChoice(BELOW, 8.0, False)
    dialog = MarginDialog(remembered(window.settings), 0, window)
    assert dialog.current() == MarginChoice(BELOW, 8.0, False)
    dialog.every_page.setChecked(True)
    dialog.accept()
    assert dialog.choice == MarginChoice(BELOW, 8.0, True)
    dialog.deleteLater()
