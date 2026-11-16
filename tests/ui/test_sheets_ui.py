"""Tests for Insertar hoja in the window: the sheet goes after the page being
read, the view and the thumbnails follow, and Deshacer, saving and the
recovery journal work with it."""

import shutil
from contextlib import contextmanager

import pymupdf
import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from app.core.drawing import BOX
from app.core.settings import Settings
from app.core.sheets import PLAIN, RULED, SQUARED, is_sheet
from app.ui.main_window import SHEET_SETTING, MainWindow, Mode
from app.ui.unsaved_dialog import DISCARD


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="largo.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages())
        return view, path

    return open_it


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view.saving)


def sheets_in(path) -> list[int]:
    with pymupdf.open(path) as doc:
        return [number for number in range(doc.page_count) if is_sheet(doc, number)]


def test_insertar_hoja_puts_a_sheet_after_the_page_being_read(window, opened, wait_until):
    view, _path = opened()
    count = view.page_count
    view.scroll_to_page(2)
    wait_until(lambda: view.current_page == 2)
    window.set_mode(Mode.STUDY)
    window.feature_actions["insert_sheet"].trigger()
    settle(view, wait_until)
    assert view.page_count == count + 1
    assert view.current_page == 3, "the new sheet is shown"
    assert "después de la página 3" in window.statusBar().currentMessage()
    thumbnails = window.side_panel.thumbnails
    assert thumbnails.count() == count + 1
    assert window.page_box.total.text().endswith(str(count + 1))
    wait_until(lambda: 3 in view.cached_pages() and 3 not in view._stale)


def test_undo_takes_it_away_and_redo_puts_it_back(window, opened, wait_until):
    view, _path = opened()
    count = view.page_count
    assert window.insert_sheet()
    settle(view, wait_until)
    assert view.undo()
    settle(view, wait_until)
    assert view.page_count == count
    assert window.side_panel.thumbnails.count() == count
    assert view.redo()
    settle(view, wait_until)
    assert view.page_count == count + 1


def test_pictures_already_drawn_move_with_their_pages(window, opened, wait_until):
    view, _path = opened()
    view.scroll_to_page(3)
    wait_until(lambda: 3 in view.cached_pages() and 4 in view.cached_pages())
    # Pictures may still arrive until the change is done: compare the cache
    # just before the view follows the new pages with just after.
    before, after = {}, {}
    reshape = view._reshape

    def watched(*args):
        before.update({page: kept[1] for page, kept in view._cache.items()})
        reshape(*args)

    view._reshape = watched
    view.pages_reshaped.connect(
        lambda: after.update({page: kept[1] for page, kept in view._cache.items()})
    )
    assert view.insert_sheet(PLAIN, after=3)
    settle(view, wait_until)
    assert after, "the view was told"
    for page, image in before.items():
        new = page if page <= 3 else page + 1
        assert after[new] is image, f"page {page + 1} keeps its picture"
    assert 4 not in after, "the new sheet has no picture yet"


def test_the_kind_chosen_is_remembered(window, opened, wait_until, settings):
    view, _path = opened()
    assert window.sheet_kind == PLAIN, "a plain sheet unless another is chosen"
    window.sheet_actions[SQUARED].trigger()
    settle(view, wait_until)
    assert settings.get(SHEET_SETTING) == SQUARED
    assert window.sheet_actions[SQUARED].isChecked()
    window.feature_actions["insert_sheet"].trigger()
    settle(view, wait_until)
    assert view.page_count >= 2
    assert window.sheet_kind == SQUARED


def test_saving_writes_the_sheets_in_the_pdf(window, opened, wait_until):
    view, path = opened()
    count = view.page_count
    window.sheet_actions[RULED].trigger()
    settle(view, wait_until)
    view.scroll_to_page(view.page_count - 1)
    wait_until(lambda: view.current_page == view.page_count - 1)
    window.insert_sheet()
    settle(view, wait_until)
    assert window.save_document()
    settle(view, wait_until)
    with pymupdf.open(path) as doc:
        assert doc.page_count == count + 2
    assert sheets_in(path) == [1, count + 1]


def test_something_drawn_on_the_sheet_stays_on_it(window, opened, wait_until):
    view, path = opened()
    window.insert_sheet()
    settle(view, wait_until)
    assert view.draw_shape(BOX, 1, (100, 100), (200, 200))
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    with pymupdf.open(path) as doc:
        assert [annot.type[1] for annot in doc[1].annots()] == ["Square"]
        assert list(doc[2].annots()) == []


def test_a_new_document_starts_with_its_own_pages(window, opened, sample, wait_until):
    view, _path = opened()
    window.insert_sheet()
    settle(view, wait_until)
    view2, _ = opened("boe.pdf")
    with pymupdf.open(sample("boe.pdf")) as doc:
        assert view2.page_count == doc.page_count


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


def test_a_power_cut_does_not_lose_the_sheet(window, opened, settings, qt_app, wait_until):
    view, path = opened()
    count = view.page_count
    window.insert_sheet()
    settle(view, wait_until)
    window.shutdown_documents()
    for page in window.documents:
        page.view.journal = None
    assert sheets_in(path) == [], "nothing had been saved"

    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = True
        assert again.offer_recovery() == 1
        view = again.pdf_view
        wait_until(lambda: view._changes == 1 and not view._changing)
        assert view.page_count == count + 1
        assert again.side_panel.thumbnails.count() == count + 1
        again.save_document()
        settle(view, wait_until)
        assert sheets_in(path) == [1]
