"""Tests for «Corregir texto» in the window: select a word, write another,
undo it, save it."""

import shutil

import pymupdf
import pytest

from app.ui.main_window import Mode

WORD = "Generales"


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages())
        wait_until(lambda: 0 in view._texts)
        return view, path

    return open_it


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view.saving)


def select_word(view, word: str, page: int = 0) -> None:
    text = view._texts[page]
    start = "".join(text.chars).index(word)
    view.select((page, start), (page, start + len(word)))


def test_a_word_is_corrected_undone_and_saved(window, opened, wait_until):
    view, path = opened()
    window.set_mode(Mode.ORGANIZE)
    select_word(view, WORD)
    window.correct_text_answer = "Españolas"
    window.feature_actions["edit_text"].trigger()
    settle(view, wait_until)
    assert "Texto cambiado" in window.statusBar().currentMessage()
    assert view.modified and view.can_undo
    assert view.breaks_signatures, "changing the text breaks a signature"
    assert not view.has_selection
    wait_until(lambda: 0 in view._texts)
    assert "Cortes Españolas" in "".join(view._texts[0].chars)
    assert view.undo()
    settle(view, wait_until)
    wait_until(lambda: 0 in view._texts)
    assert "Cortes Generales" in "".join(view._texts[0].chars)
    assert view.redo()
    settle(view, wait_until)
    assert window.save_document()
    settle(view, wait_until)
    with pymupdf.open(path) as doc:
        assert "Cortes Españolas" in doc[0].get_text()


def test_without_a_selection_it_says_what_to_do(window, opened):
    view, _path = opened()
    assert not window.correct_text("algo")
    assert "Selecciona primero" in window.statusBar().currentMessage()
    assert not view.modified


def test_more_than_one_line_is_refused(window, opened):
    view, _path = opened()
    text = view._texts[0]
    chars = "".join(text.chars)
    start = chars.index("Cortes")
    view.select((0, start), (0, chars.index("Referencia")))
    assert not window.correct_text("algo")
    assert "una sola línea" in window.statusBar().currentMessage()


def test_a_text_too_long_says_so_and_changes_nothing(window, opened, wait_until):
    view, _path = opened()
    select_word(view, WORD)
    window.correct_text("y además un texto larguísimo " * 6)
    settle(view, wait_until)
    assert "no cabe" in window.statusBar().currentMessage()
    assert not view.modified


def test_the_menu_of_the_right_button_offers_it(window, opened):
    view, _path = opened()
    select_word(view, WORD)
    menu = view.context_menu(view.viewport().rect().center())
    names = [action.text() for action in menu.actions()]
    assert "Corregir texto…" in names
    action = next(action for action in menu.actions() if action.text() == "Corregir texto…")
    assert action.isEnabled()
