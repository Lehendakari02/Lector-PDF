"""Tests for the syllabus library window."""

import shutil

from app.core.library import FOLDER_SETTING


def temario(tmp_path, sample):
    root = tmp_path / "temario"
    root.mkdir()
    shutil.copy(sample("boe.pdf"), root / "Tema 2.pdf")
    shutil.copy(sample("texto-partido.pdf"), root / "Tema 10.pdf")
    shutil.copy(sample("con-contrasena.pdf"), root / "Tema 3.pdf")
    return root


def library_of(window, root, wait_until):
    window.show_problem_dialogs = False
    window.library_asks_folder = False
    library = window.show_library()
    library.ask_folder = lambda _parent, _start: str(root)
    assert library.choose_folder()
    wait_until(lambda: not library.busy, seconds=60)
    return library


def texts(tree, column):
    return [tree.topLevelItem(i).text(column) for i in range(tree.topLevelItemCount())]


def test_the_folder_is_chosen_once_and_its_topics_listed(window, sample, tmp_path, wait_until):
    root = temario(tmp_path, sample)
    library = library_of(window, root, wait_until)
    assert window.settings.get(FOLDER_SETTING) == str(root)
    assert texts(library.topic_list, 0) == ["Tema 2.pdf", "Tema 3.pdf", "Tema 10.pdf"]
    assert texts(library.topic_list, 1) == ["0 %", "Con contraseña", "0 %"]
    assert texts(library.topic_list, 3) == ["Todavía no"] * 3
    library.close()
    again = window.show_library()
    assert again is library and texts(again.topic_list, 0)[0] == "Tema 2.pdf"


def test_progress_follows_reading_and_review(window, sample, tmp_path, wait_until):
    root = temario(tmp_path, sample)
    library = library_of(window, root, wait_until)
    item = library.topic_list.topLevelItem(0)
    library.topic_list.itemActivated.emit(item, 0)
    view = window.pdf_view
    assert view.document_path == root / "Tema 2.pdf"
    pages = view.page_count
    window.history.remember_place(view.document_path, pages - 1)
    window.toggle_review()
    assert view.review
    library.refresh_progress()
    assert texts(library.topic_list, 1)[0] == "100 %"
    assert texts(library.topic_list, 3)[0] != "Todavía no"


def test_searching_every_topic_and_opening_a_result(window, sample, tmp_path, wait_until):
    root = temario(tmp_path, sample)
    library = library_of(window, root, wait_until)
    library.search_box.setText("constitucion")
    assert library.search()
    wait_until(lambda: not library.busy, seconds=60)
    assert library.hits and {hit.path.name for hit in library.hits} == {"Tema 2.pdf"}
    assert "resultados en 1 temas" in library.status.text()
    hit = library.hits[-1]
    library.hit_list.itemActivated.emit(library.hit_list.item(len(library.hits) - 1))
    view = window.pdf_view
    assert view.document_path == root / "Tema 2.pdf"
    wait_until(lambda: view.current_page == hit.page)
    assert window.search_panel.box.text() == "constitucion"
    library.show_topics()
    library.search_box.setText("no aparece en ninguno zzz")
    library.search()
    wait_until(lambda: not library.busy, seconds=60)
    assert library.status.text() == "No se ha encontrado en ningún tema."


def test_whole_word_and_intro_do_not_ask_for_the_folder(window, sample, tmp_path, wait_until):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    root = temario(tmp_path, sample)
    library = library_of(window, root, wait_until)
    asked = []
    library.ask_folder = lambda _parent, _start: asked.append(1) or ""
    library.search_box.setText("artículo 14")
    QTest.keyClick(library.search_box, Qt.Key.Key_Return)
    wait_until(lambda: not library.busy, seconds=60)
    every = len(library.hits)
    assert asked == [] and every
    library.whole_word.setChecked(True)
    library.search()
    wait_until(lambda: not library.busy, seconds=60)
    assert 0 < len(library.hits) < every
    assert all(not hit.after[:1].isdigit() for hit in library.hits)


def test_a_search_can_be_stopped(window, sample, tmp_path, wait_until):
    root = temario(tmp_path, sample)
    library = library_of(window, root, wait_until)
    library.search_box.setText("a")
    library.search()
    library.stop()
    assert not library.busy and library.status.text() == "Parado."


def test_an_empty_folder_says_so(window, tmp_path, wait_until):
    empty = tmp_path / "vacia"
    empty.mkdir()
    library = library_of(window, empty, wait_until)
    assert library.status.text() == "No hay ningún PDF en esta carpeta."
    assert not library.search()
