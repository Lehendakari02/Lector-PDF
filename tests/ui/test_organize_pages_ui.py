"""Tests for Organizar: turning, moving and taking away pages from the
miniatures and the tool bar, with Deshacer, saving and the recovery journal."""

import shutil
from contextlib import contextmanager

import pymupdf
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest

from app.core.settings import Settings
from app.ui.main_window import MainWindow, Mode, pages_text
from app.ui.side_panel import Tab
from app.ui.unsaved_dialog import DISCARD


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages())
        return view, path

    return open_it


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view.saving)


def page_texts(path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text()[:200] for page in doc]


def rotations(path) -> list[int]:
    with pymupdf.open(path) as doc:
        return [page.rotation for page in doc]


def test_pages_text_says_the_pages_as_people_count_them():
    assert pages_text([2]) == "Página 3"
    assert pages_text([1, 2, 3, 6]) == "Páginas 2-4 y 7"
    assert pages_text([0, 4, 9]) == "Páginas 1, 5 y 10"


def test_ordenar_paginas_shows_the_miniatures(window, opened, wait_until):
    opened()
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["pages"].trigger()
    assert window.side_dock.isVisible()
    assert window.side_panel.tab is Tab.THUMBNAILS
    assert "Arrastra" in window.statusBar().currentMessage()


def test_moving_pages_in_the_miniatures(window, opened, wait_until):
    view, path = opened()
    before = page_texts(path)
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    thumbnails.move_pages([3, 4], 0)
    settle(view, wait_until)
    assert thumbnails.picked_pages() == [0, 1], "the pages moved stay picked"
    assert view.page_count == len(before)
    assert view.breaks_signatures
    assert window.save_document()
    settle(view, wait_until)
    after = page_texts(path)
    assert after[:5] == [before[3], before[4], before[0], before[1], before[2]]
    assert after[5:] == before[5:]


def test_alt_and_the_arrows_move_the_pages_picked(window, opened, wait_until):
    view, path = opened()
    before = page_texts(path)
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    thumbnails.pick_pages([2])
    QTest.keyClick(thumbnails, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    settle(view, wait_until)
    assert thumbnails.picked_pages() == [3]
    QTest.keyClick(thumbnails, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    settle(view, wait_until)
    QTest.keyClick(thumbnails, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    after = page_texts(path)
    assert after[:3] == [before[0], before[2], before[1]]


def test_where_a_dragged_page_lands(window, opened, wait_until):
    opened()
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    wait_until(lambda: thumbnails.visualRect(thumbnails.model().index(1, 0)).isValid())
    box = thumbnails.visualRect(thumbnails.model().index(1, 0))
    middle = box.center().y()
    assert thumbnails.drop_place(QPoint(box.left() + 2, middle)) == 1
    assert thumbnails.drop_place(QPoint(box.right() - 2, middle)) == 2


def test_undo_puts_moved_pages_back(window, opened, wait_until):
    view, path = opened()
    before = page_texts(path)
    failed = []
    view.edit_failed.connect(failed.append)
    assert view.move_pages([0], view.page_count)
    settle(view, wait_until)
    assert view.undo()
    settle(view, wait_until)
    assert not failed, "taking the move back did not work"
    assert view.redo()
    settle(view, wait_until)
    assert view.undo()
    settle(view, wait_until)
    assert view.move_pages([1], 0)
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    assert not failed
    after = page_texts(path)
    assert after[:2] == [before[1], before[0]] and after[2:] == before[2:], (
        f"restarts of the helper: {view.service.restarts}"
    )


def test_rotar_turns_the_page_being_read(window, opened, wait_until):
    view, path = opened()
    view.scroll_to_page(2)
    wait_until(lambda: view.current_page == 2)
    width, height = view._sizes[2].width, view._sizes[2].height
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["rotate"].trigger()
    settle(view, wait_until)
    assert (view._sizes[2].width, view._sizes[2].height) == (height, width)
    assert "Página 3 girada" in window.statusBar().currentMessage()
    assert window.rotate_pages(-90)
    settle(view, wait_until)
    assert window.rotate_pages(-90)
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    assert rotations(path)[2] == 270
    assert rotations(path)[:2] == [0, 0]


def test_rotar_turns_the_pages_picked_and_every_page(window, opened, wait_until):
    view, path = opened()
    window.show_side_panel(Tab.THUMBNAILS)
    window.side_panel.thumbnails.pick_pages([1, 4])
    assert window.rotate_pages(180)
    settle(view, wait_until)
    assert window.side_panel.thumbnails.picked_pages() == [1, 4]
    assert window.rotate_pages(90, every=True)
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    turned = rotations(path)
    assert turned[1] == turned[4] == 270
    assert turned[0] == turned[2] == 90


def test_eliminar_asks_and_takes_the_pages_away(window, opened, wait_until):
    view, path = opened()
    before = page_texts(path)
    asked = []
    window.ask_delete_pages = lambda pages: asked.append(pages) or True
    window.show_side_panel(Tab.THUMBNAILS)
    window.side_panel.thumbnails.pick_pages([1, 2])
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["delete_pages"].trigger()
    settle(view, wait_until)
    assert asked == [[1, 2]]
    assert view.page_count == len(before) - 2
    assert window.side_panel.thumbnails.count() == len(before) - 2
    assert "Páginas 2-3 eliminadas" in window.statusBar().currentMessage()
    assert view.breaks_signatures
    window.save_document()
    settle(view, wait_until)
    assert page_texts(path) == [before[0], *before[3:]]


def test_eliminar_does_nothing_if_the_answer_is_no(window, opened, wait_until):
    view, _path = opened()
    count = view.page_count
    window.ask_delete_pages = lambda pages: False
    assert not window.delete_pages([0])
    settle(view, wait_until)
    assert view.page_count == count


def test_every_page_cannot_be_taken_away(window, opened, wait_until):
    view, _path = opened()
    window.ask_delete_pages = lambda pages: pytest.fail("not asked")
    assert not window.delete_pages(list(range(view.page_count)))
    assert "todas las páginas" in window.statusBar().currentMessage()


def test_supr_in_the_miniatures_asks_to_take_them_away(window, opened, wait_until):
    view, _path = opened()
    asked = []
    window.ask_delete_pages = lambda pages: asked.append(pages) or False
    window.show_side_panel(Tab.THUMBNAILS)
    thumbnails = window.side_panel.thumbnails
    thumbnails.pick_pages([5])
    QTest.keyClick(thumbnails, Qt.Key.Key_Delete)
    assert asked == [[5]]


def test_pages_taken_away_come_back_even_after_saving(window, opened, wait_until):
    view, path = opened()
    before = page_texts(path)
    window.ask_delete_pages = lambda pages: True
    with pymupdf.open(path) as doc:
        outline = doc.get_toc()
    assert window.delete_pages([0, 1])
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    assert len(page_texts(path)) == len(before) - 2
    assert view.undo()
    settle(view, wait_until)
    assert view.page_count == len(before)
    window.save_document()
    settle(view, wait_until)
    assert page_texts(path) == before
    with pymupdf.open(path) as doc:
        assert doc.get_toc() == outline


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


def test_a_power_cut_does_not_lose_the_new_order(window, opened, settings, qt_app, wait_until):
    view, path = opened()
    before = page_texts(path)
    window.ask_delete_pages = lambda pages: True
    assert view.move_pages([2], 0)
    settle(view, wait_until)
    assert window.delete_pages([5])
    settle(view, wait_until)
    assert view.undo()
    settle(view, wait_until)
    assert view.rotate_pages([1], 90)
    settle(view, wait_until)
    window.shutdown_documents()
    for page in window.documents:
        page.view.journal = None
    assert page_texts(path) == before, "nothing had been saved"

    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = True
        assert again.offer_recovery() >= 1
        view = again.pdf_view
        wait_until(lambda: view._changes == 2 and not view._changing)
        assert view.page_count == len(before)
        again.save_document()
        settle(view, wait_until)
        after = page_texts(path)
        assert after[:3] == [before[2], before[0], before[1]]
        assert after[3:] == before[3:]
        assert rotations(path)[1] == 90


def test_insertar_paginas_from_a_pdf_and_a_picture(window, opened, sample, tmp_path, wait_until):
    view, path = opened()
    before = page_texts(path)
    picture = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 200), False)
    picture.clear_with(120)
    photo = tmp_path / "foto.png"
    picture.save(photo)
    other = tmp_path / "partido.pdf"
    shutil.copy(sample("texto-partido.pdf"), other)
    with pymupdf.open(other) as doc:
        other_texts = [page.get_text()[:200] for page in doc]
    window.insert_files_answer = [other, photo]
    window.insert_where_answer = 1
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["insert_pages"].trigger()
    settle(view, wait_until)
    added = len(other_texts) + 1
    assert view.page_count == len(before) + added
    assert window.side_panel.thumbnails.count() == len(before) + added
    assert "insertadas" in window.statusBar().currentMessage()
    assert view.breaks_signatures
    window.save_document()
    settle(view, wait_until)
    after = page_texts(path)
    assert after[0] == before[0]
    assert after[1 : 1 + len(other_texts)] == other_texts
    assert after[1 + added :] == before[1:]
    assert view.undo()
    settle(view, wait_until)
    assert view.page_count == len(before)


def test_insertar_asks_the_password_of_a_locked_pdf(window, opened, sample, wait_until):
    view, _path = opened()
    count = view.page_count
    asked = []
    from app.core.document import PdfDocument

    window.ask_password = lambda path: asked.append(path) or PdfDocument(path, "lector")
    assert window.insert_pages([sample("con-contrasena.pdf")], at=0)
    settle(view, wait_until)
    assert asked and view.page_count > count


def test_insertar_from_the_miniatures_goes_after_the_page(window, opened, sample, wait_until):
    view, path = opened()
    before = page_texts(path)
    window.insert_files_answer = [sample("texto-partido.pdf")]
    window.show_side_panel(Tab.THUMBNAILS)
    window.side_panel.thumbnails.insert_wanted.emit(3)
    settle(view, wait_until)
    window.save_document()
    settle(view, wait_until)
    assert page_texts(path)[:3] == before[:3]
    assert page_texts(path)[-5:] == before[-5:]
