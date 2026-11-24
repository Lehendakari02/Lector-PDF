"""Tests for «Comparar» in the window: both versions side by side and the list."""

import pytest

from app.core.document import PdfDocument
from app.ui.compare_window import change_text, summary_text
from app.ui.main_window import Mode
from tests.core.test_compare import LAW, make


@pytest.fixture
def versions(window, tmp_path, wait_until):
    window.show_problem_dialogs = False
    old = make(tmp_path / "ley 2020.pdf", LAW, "Disposición final.")
    new_text = LAW.replace("treinta", "cuarenta").replace("cabe recurso de alzada.", "")
    new = make(tmp_path / "ley 2024.pdf", new_text, "Disposición final. Entra en vigor.")
    assert window.open_document(new)
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
    return old, new


def test_comparing_shows_both_and_the_changes(window, versions):
    old, new = versions
    window.compare_answer = str(old)
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["compare"].trigger()
    assert window.last_file_work[0] == "compared"
    shown = window.compare_window
    assert shown.isVisible()
    assert shown.list.count() == 3
    assert "3 diferencias" in shown.summary.text()
    assert window.current_document.path == new.absolute()
    assert window.beside.page.path == old.absolute()
    # The first change is marked on both versions.
    first = shown.list.item(0).text()
    assert "«treinta» por «cuarenta»" in first
    assert window.current_document.view.search_marks()[0]
    assert window.beside.page.view.search_marks()[0]
    shown.step(1)
    assert shown.list.currentRow() == 1
    assert "Quitado" in shown.list.currentItem().text()
    # Closing the list takes the marks away.
    shown.close()
    assert not window.current_document.view.search_marks()
    assert not window.beside.page.view.search_marks()


def test_swapping_compares_the_other_way(window, versions):
    old, _new = versions
    window.compare_answer = str(old)
    assert window.compare_versions()
    window.compare_window.swap_asked.emit()
    assert window.current_document.path == old.absolute()
    assert "Añadido" in window.compare_window.list.item(1).text()


def test_the_same_file_or_one_without_text(window, versions, tmp_path):
    _old, new = versions
    assert not window.compare_versions(new)
    import pymupdf

    empty = pymupdf.open()
    empty.new_page()
    empty.save(tmp_path / "escaneada.pdf")
    assert not window.compare_versions(tmp_path / "escaneada.pdf")
    assert window.last_file_work == ("no_text", str(tmp_path / "escaneada.pdf"))


def test_an_earlier_version_with_a_password(window, versions, tmp_path):
    locked = make(tmp_path / "protegida.pdf", LAW, password="clave")
    window.ask_password = lambda where: PdfDocument(where, "clave")
    assert window.compare_versions(locked)
    assert window.compare_window.list.count() >= 2


def test_the_texts_of_the_list():
    from app.core.compare import Comparison, compare_words
    from tests.core.test_compare import words

    tr = str
    (change,) = compare_words(words(LAW), words(LAW.replace("tres", "seis")))
    assert change_text(change, tr).startswith("Página 1 · Cambiado: «tres» por «seis»")
    one = Comparison([change], 1, 1, 10, 10)
    assert summary_text(one, tr) == "1 diferencia."
    assert summary_text(Comparison([], 1, 1, 1, 1), tr).startswith("No hay")
