"""Tests for Reconocer texto on a whole scanned document: in the background,
with progress and Cancelar, written as invisible text that is searched,
saved, taken back with Deshacer and not lost in a power cut."""

import shutil
from contextlib import contextmanager

import pymupdf
import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from app.core.search import find_in_page, read_page_text
from app.core.settings import Settings
from app.core.text_layer import has_layer
from app.ui.main_window import MainWindow
from app.ui.unsaved_dialog import DISCARD

READING_SECONDS = 120  # three pages; test machines are slow and shared


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="escaneado.pdf"):
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
    view = page.view
    wait_until(lambda: not view._changing)


def found_in_file(path, word: str) -> list[int]:
    with pymupdf.open(path) as doc:
        return [n for n in range(doc.page_count) if find_in_page(read_page_text(doc[n]), word)]


def layers_in_file(path) -> list[int]:
    with pymupdf.open(path) as doc:
        return [n for n in range(doc.page_count) if has_layer(doc, n)]


def test_the_text_can_be_searched_and_saved(window, opened, wait_until):
    view, path = opened()
    assert window.recognize_text()
    finished(window, wait_until)
    window.show_search()
    panel = window.search_panel
    panel.box.setText("camion")
    panel.search_now()
    wait_until(lambda: not panel._searching)
    assert panel.hits, "the recognised words are found"
    assert found_in_file(path, "articulo") == [], "the PDF only changes when saved"
    assert window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    assert found_in_file(path, "articulo") == [0, 1, 2]


def test_deshacer_takes_all_of_it_away_at_once(window, opened, wait_until):
    view, _ = opened()
    window.recognize_text()
    finished(window, wait_until)
    assert view.can_undo
    assert view.undo()
    wait_until(lambda: not view._changing)
    assert not view.can_undo


def test_the_pages_can_be_read_meanwhile(window, opened, wait_until):
    view, _ = opened()
    window.recognize_text()
    view.scroll_to_page(2)
    wait_until(lambda: 2 in view.cached_pages())
    assert window.current_document.text_recognition is not None, "still reading"
    finished(window, wait_until)


def test_cancelar_keeps_the_pages_already_read(window, opened, wait_until):
    view, path = opened()
    window.recognize_text()
    run = window.current_document.text_recognition
    wait_until(lambda: run.count_done >= 1, seconds=READING_SECONDS)
    read = len(run.done)
    window.current_document.ocr_banner.cancel_button.click()
    finished(window, wait_until)
    assert "cancelado" in window.statusBar().currentMessage()
    window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    assert len(layers_in_file(path)) == read


def test_a_sheet_put_in_meanwhile_does_not_move_the_text(window, opened, wait_until):
    view, path = opened()
    window.recognize_text()
    assert view.insert_sheet(after=0)  # the second and third pages move down
    finished(window, wait_until)
    window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    assert layers_in_file(path) == [0, 2, 3]
    with pymupdf.open(path) as doc:
        assert "Artículo 6" in doc[2].get_text()


def test_closing_the_document_stops_reading(window, opened, wait_until):
    opened()
    window.recognize_text()
    run = window.current_document.text_recognition
    process = run._recognizer._process
    window.close_document(ask=False)
    wait_until(lambda: not process.is_alive())
    assert not run.running


def test_a_document_with_text_has_nothing_to_recognise(window, opened):
    opened("boe.pdf")
    assert not window.recognize_text()
    assert "ya tiene texto" in window.statusBar().currentMessage()


@contextmanager
def started_again(settings, qt_app):
    window = MainWindow(Settings(settings.path))
    window.show_problem_dialogs = False
    window.show()
    qt_app.processEvents()
    try:
        yield window
    finally:
        window.unsaved_answer = DISCARD
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_power_cut_does_not_lose_the_text(window, opened, settings, qt_app, wait_until):
    _view, path = opened()
    window.recognize_text()
    finished(window, wait_until)
    window.shutdown_documents()
    for page in window.documents:
        page.view.journal = None

    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = True
        assert again.offer_recovery() == 1
        view = again.pdf_view
        wait_until(lambda: view._changes == 1 and not view._changing)
        again.save_document()
        wait_until(lambda: not view.saving and not view.modified)
        assert layers_in_file(path) == [0, 1, 2]


def test_a_power_cut_in_the_middle_keeps_the_pages_read(
    window, opened, settings, qt_app, wait_until, monkeypatch
):
    """Half way through a long document the power goes: running it again
    does not read again the pages already read."""
    _view, path = opened()
    window.recognize_text()
    run = window.current_document.text_recognition
    wait_until(lambda: len(run.done) >= 1, seconds=READING_SECONDS)
    read_before = set(run.done)
    run.stop()  # the power goes: nothing reaches the document
    window.shutdown_documents()
    for page in window.documents:
        page.view.journal = None
    assert any(window.ocr_cache.folder.glob("*.json"))

    from app.core.ocr import Recognizer

    given: list[int] = []
    read = Recognizer.read
    monkeypatch.setattr(
        Recognizer, "read", lambda self, page, *rest: (given.append(page), read(self, page, *rest))
    )
    with started_again(settings, qt_app) as again:
        again.restore_session()
        wait_until(lambda: again.pdf_view.scanned_known, seconds=30)
        assert again.recognize_text()
        rerun = again.current_document.text_recognition
        wait_until(lambda: read_before <= set(rerun.done), seconds=READING_SECONDS)
        finished(again, wait_until)
        assert not read_before & set(given), "the pages read before are not read again"
        view = again.pdf_view
        again.save_document()
        wait_until(lambda: not view.saving and not view.modified)
        assert layers_in_file(path) == [0, 1, 2]
        assert not any(again.ocr_cache.folder.glob("*.json")), "kept only until it is written"
