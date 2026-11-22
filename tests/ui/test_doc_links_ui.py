"""Tests for links from some words to a place of another document."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.doc_links import AddDocLink, page_doc_links
from app.core.library import FOLDER_SETTING


@pytest.fixture
def folders(tmp_path, sample):
    (tmp_path / "Temas").mkdir()
    (tmp_path / "Leyes").mkdir()
    shutil.copy(sample("boe.pdf"), tmp_path / "Temas" / "Tema 5.pdf")
    shutil.copy(sample("largo.pdf"), tmp_path / "Leyes" / "Constitución.pdf")
    return tmp_path / "Temas" / "Tema 5.pdf", tmp_path / "Leyes" / "Constitución.pdf"


def make_link(window, wait_until, tema, ley, where="3"):
    window.show_problem_dialogs = False
    assert window.open_document(tema)
    source = window.current_document
    wait_until(lambda: 0 in source.view._texts)
    source.view.select((0, 0), (0, 12))
    window.link_answer = (ley, where)
    assert window.link_selection()
    target = window.beside_page
    assert target is not None and target.path == ley.absolute()
    assert window.pages.currentWidget() is source, "the one with the link stays in front"
    assert window.beside.link_bar.isVisibleTo(window.beside)
    return source, target


def test_a_link_is_made_at_the_place_shown_beside(window, folders, wait_until):
    tema, ley = folders
    source, target = make_link(window, wait_until, tema, ley)
    wait_until(lambda: target.view.current_page == 2)
    assert window.finish_link()
    assert not window.beside.link_bar.isVisibleTo(window.beside)
    wait_until(lambda: source.view.doc_links_of(0))
    made = source.view.doc_links_of(0)[0]
    assert made.file == "../Leyes/Constitución.pdf" and made.page == 2
    assert window.current_document is source and source.view.modified
    assert source.view.save()
    wait_until(lambda: not source.view.modified)
    with pymupdf.open(tema) as saved:
        assert [link.file for link in page_doc_links(saved, 0)] == ["../Leyes/Constitución.pdf"]


def test_cancelling_makes_no_link(window, folders, wait_until):
    tema, ley = folders
    source, _target = make_link(window, wait_until, tema, ley)
    window.beside.link_cancelled.emit()
    assert window._pending_link is None and not window.finish_link()
    assert not source.view.modified


def test_without_words_selected_it_says_what_to_do(window, folders):
    tema, _ley = folders
    window.show_problem_dialogs = False
    assert window.open_document(tema)
    assert not window.link_selection()
    assert "Selecciona primero" in window.statusBar().currentMessage()


def test_the_menu_of_the_right_button_offers_it(window, folders, wait_until):
    tema, _ley = folders
    window.show_problem_dialogs = False
    assert window.open_document(tema)
    view = window.pdf_view
    wait_until(lambda: 0 in view._texts)
    names = {action.text(): action for action in view.context_menu(view.rect().center()).actions()}
    assert not names["Enlazar a…"].isEnabled()
    view.select((0, 0), (0, 12))
    names = {action.text(): action for action in view.context_menu(view.rect().center()).actions()}
    assert names["Enlazar a…"].isEnabled()


def linked(window, wait_until, tema, ley):
    """The topic with a link to page 3 of the law, saved and opened alone."""
    source, target = make_link(window, wait_until, tema, ley)
    wait_until(lambda: target.view.current_page == 2)
    assert window.finish_link()
    wait_until(lambda: source.view.doc_links_of(0))
    window.close_document(window.documents.index(target))
    assert window.beside_page is None
    return source, source.view.doc_links_of(0)[0]


def test_a_click_on_the_link_opens_the_other_one_beside(window, folders, wait_until):
    tema, ley = folders
    source, link = linked(window, wait_until, tema, ley)
    source.view.scroll_to_page(0)
    assert window.follow_doc_link(source, link)
    target = window.beside_page
    assert target is not None and target.path == ley.absolute()
    assert window.pages.currentWidget() is source
    wait_until(lambda: target.view.current_page == 2)


def test_a_link_to_a_document_moved_is_found_in_the_library(window, folders, wait_until, tmp_path):
    tema, ley = folders
    source, link = linked(window, wait_until, tema, ley)
    (tmp_path / "Temario").mkdir()
    moved = tmp_path / "Temario" / "Constitución.pdf"
    shutil.move(ley, moved)
    window.settings.set(FOLDER_SETTING, str(tmp_path / "Temario"))
    assert window.follow_doc_link(source, link)
    assert window.beside_page.path == moved.absolute()
    wait_until(lambda: source.view.doc_links_of(0)[0].file == "../Temario/Constitución.pdf")
    assert source.view.undo()
    wait_until(lambda: source.view.doc_links_of(0)[0].file == "../Leyes/Constitución.pdf")


def test_a_document_not_found_is_said_and_can_be_pointed_at(window, folders, wait_until, tmp_path):
    tema, ley = folders
    source, link = linked(window, wait_until, tema, ley)
    hidden = tmp_path / "Otro sitio" / "Ley nueva.pdf"
    hidden.parent.mkdir()
    shutil.move(ley, hidden)
    window.where_is_answer = ""
    assert not window.follow_doc_link(source, link)
    assert "no encontrado" in window.statusBar().currentMessage()
    assert window.beside_page is None
    window.where_is_answer = hidden
    assert window.follow_doc_link(source, link)
    assert window.beside_page.path == hidden.absolute()
    wait_until(lambda: source.view.doc_links_of(0)[0].file == "../Otro sitio/Ley nueva.pdf")


def place(view, page: int, x: float, y: float) -> QPoint:
    """Where a point of a page is in the window."""
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def test_a_click_on_a_link_of_another_program_opens_it(window, folders, wait_until):
    tema, ley = folders
    order = AddDocLink(0, ((60.0, 60.0, 300.0, 90.0),), "../Leyes/Constitución.pdf", 4, None, "x")
    with pymupdf.open(tema) as doc:
        order.apply(doc)
        doc.save(tema.with_name("Con enlace.pdf"))
    window.show_problem_dialogs = False
    assert window.open_document(tema.with_name("Con enlace.pdf"))
    view = window.pdf_view
    wait_until(lambda: view.doc_links_of(0))
    link = view.doc_links_of(0)[0]
    assert link.page == 4 and link.top is None
    spot = place(view, 0, 150, 75)
    assert view.doc_link_under(spot) == link
    QTest.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot
    )
    wait_until(lambda: window.beside_page is not None)
    assert window.beside_page.path == ley.absolute()
    wait_until(lambda: window.beside_page.view.current_page == 4)
    view.set_annotations_shown(False)
    assert view.doc_link_under(spot) is None, "hidden with the annotations"
