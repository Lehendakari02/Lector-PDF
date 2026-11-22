"""Tests for the user's bookmarks: put one, go back to it, rename or remove it."""

import shutil

import pymupdf
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ui.side_panel import Tab


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


def bookmarks_of(view):
    return [(e.title, e.page) for e in view.outline if e.bookmark]


def shows_bookmarks(tree) -> bool:
    return tree.topLevelItemCount() > 0 and tree.topLevelItem(0).text(0) == "Mis marcadores"


def test_ctrl_m_bookmarks_the_heading_in_sight(window, sample, tmp_path, wait_until):
    view, path = open_copy(window, sample, tmp_path, wait_until)
    view.go_to_place("art. 14")
    wait_until(lambda: view.current_page == 4 and 4 in view._texts)
    window.bookmark_action.trigger()
    settle(view, wait_until)
    wait_until(lambda: bookmarks_of(view))
    ((title, page),) = bookmarks_of(view)
    assert page == 4 and title.startswith("Artículo 14.")
    assert "Marcador «Artículo 14." in window.statusBar().currentMessage()
    assert view.modified, "it is a change like any other, saved with Guardar"
    window.save_document()
    wait_until(lambda: not view.saving)
    with pymupdf.open(path) as doc:
        toc = doc.get_toc()
    assert toc[0] == [1, "Mis marcadores", -1] and toc[1][1].startswith("Artículo 14.")
    assert view.undo()
    settle(view, wait_until)
    wait_until(lambda: not bookmarks_of(view))


def test_without_a_heading_it_is_named_after_the_page(window, sample, tmp_path, wait_until):
    view, _path = open_copy(window, sample, tmp_path, wait_until)
    assert view.add_bookmark() == "Página 1"  # the first page of the sample has no heading
    settle(view, wait_until)
    wait_until(lambda: bookmarks_of(view))
    assert bookmarks_of(view)[0][1] == 0


def test_the_index_shows_them_first_and_a_click_goes_back(window, sample, tmp_path, wait_until):
    view, _path = open_copy(window, sample, tmp_path, wait_until)
    view.scroll_to_page(20)
    wait_until(lambda: view.current_page == 20)
    assert view.add_bookmark("Repasar esto")
    settle(view, wait_until)
    window.show_side_panel(Tab.OUTLINE)
    tree = window.side_panel.outline
    wait_until(lambda: shows_bookmarks(tree))
    group = tree.topLevelItem(0)
    assert group.text(0) == "Mis marcadores" and group.isExpanded()
    assert tree.topLevelItem(1).isExpanded(), "the law's own index opens as before"
    view.scroll_to_page(0)
    tree.itemClicked.emit(group.child(0), 0)
    assert view.current_page == 20


def test_rename_and_remove_from_the_index(window, sample, tmp_path, wait_until):
    view, _path = open_copy(window, sample, tmp_path, wait_until)
    assert view.add_bookmark("Uno")
    settle(view, wait_until)
    window.show_side_panel(Tab.OUTLINE)
    tree = window.side_panel.outline
    wait_until(lambda: shows_bookmarks(tree))
    tree.ask_title = lambda current: "Importante"
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    QTest.keyClick(tree, Qt.Key.Key_F2)
    settle(view, wait_until)
    wait_until(lambda: bookmarks_of(view) == [("Importante", 0)])
    wait_until(lambda: tree.topLevelItem(0).child(0).text(0) == "Importante")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    QTest.keyClick(tree, Qt.Key.Key_Delete)
    settle(view, wait_until)
    wait_until(lambda: not bookmarks_of(view))
    assert tree.topLevelItem(0).text(0) == "Constitución Española."
