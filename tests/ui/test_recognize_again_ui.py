"""Tests for recognising again scanned pages that already have a poor text:
all of them or the ones chosen, with the old text back on Deshacer."""

import shutil

import pymupdf
import pytest

from app.core.search import find_in_page, read_page_text
from app.ui.recognize_again_dialog import RecognizeAgainDialog

READING_SECONDS = 120


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="ocr-malo.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages() and view.scanned_known, seconds=30)
        return view, path

    return open_it


def finished(window, wait_until) -> None:
    page = window.current_document
    wait_until(lambda: page.text_recognition is None, seconds=READING_SECONDS)
    wait_until(lambda: not page.view._changing)


def saved_text(window, view, path, wait_until) -> list[str]:
    assert window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


def test_a_document_with_a_poor_text_is_known_and_offered_nothing(window, opened):
    view, _ = opened()
    assert view.scanned_pages == [] and view.recognised_pages == [0, 1]
    assert not window.current_document.ocr_banner.isVisibleTo(window)


def test_reconocer_texto_asks_and_recognises_all_again(window, opened, wait_until):
    view, path = opened()
    window.recognize_again_answer = [0, 1]
    assert window.recognize_text()  # nothing without text: it asks which pages
    finished(window, wait_until)
    assert "Texto reconocido de nuevo en 2 páginas" in window.statusBar().currentMessage()
    texts = saved_text(window, view, path, wait_until)
    assert all("Articu1o" not in text for text in texts)
    with pymupdf.open(path) as doc:
        assert find_in_page(read_page_text(doc[0]), "camion"), "found well now"


def test_only_the_pages_chosen_and_deshacer_brings_the_old_text_back(window, opened, wait_until):
    view, path = opened()
    window.recognize_again_answer = [1]
    assert window.feature_actions["ocr_again"].isEnabled()
    window.recognize_again()
    finished(window, wait_until)
    with pymupdf.open(path) as doc:
        old = [page.get_text() for page in doc]
    assert view.undo()
    wait_until(lambda: not view._changing)
    assert view.redo()
    wait_until(lambda: not view._changing)
    texts = saved_text(window, view, path, wait_until)
    assert texts[0] == old[0], "page 1 was not touched"
    assert "Articu1o" not in texts[1] and "Artículo 6" in texts[1]
    assert view.undo()
    wait_until(lambda: not view._changing)
    texts = saved_text(window, view, path, wait_until)
    assert texts == old


def test_a_document_without_scans_has_nothing_to_recognise_again(window, opened):
    opened("boe.pdf")
    assert not window.recognize_again()
    assert "no tiene páginas escaneadas" in window.statusBar().currentMessage()


def test_the_dialog_takes_only_scanned_pages(qt_app):
    dialog = RecognizeAgainDialog([2, 3, 4], current=0, page_count=6)
    assert dialog.chosen() == [2, 3, 4]
    assert not dialog.current_button.isEnabled(), "page 1 is not scanned"
    dialog.some_pages.setText("1-3, 5")
    dialog.some_button.setChecked(True)
    assert dialog.chosen() == [2, 4]
    dialog.some_pages.setText("1")
    with pytest.raises(ValueError, match="no están escaneadas"):
        dialog.chosen()
    dialog.some_pages.setText("tres")
    with pytest.raises(ValueError, match="No entiendo"):
        dialog.chosen()
    dialog.accept()
    assert dialog.pages is None and dialog.problem.isVisibleTo(dialog)
    dialog.some_pages.setText("3")
    dialog.accept()
    assert dialog.pages == [2]
