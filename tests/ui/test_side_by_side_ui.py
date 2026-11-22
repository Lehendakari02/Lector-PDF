"""Tests for seeing two documents at once, side by side."""

from app.core.commands import HIGHLIGHT


def open_samples(window, sample, *names):
    window.show_problem_dialogs = False
    for name in names:
        assert window.open_document(sample(name))


def test_with_two_open_the_button_puts_the_other_beside(window, sample, wait_until):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    tema, ley = window.documents
    assert window.current_document is ley
    window.toggle_beside()
    assert window.beside_page is tema
    assert window.beside.isVisible() and window.pages.currentWidget() is ley
    assert ley.isVisible() and tema.isVisible(), "both at once"
    assert "boe.pdf" in window.beside.title.text()
    assert window.document_tabs.count() == 2, "it keeps its tab"
    window.toggle_beside()
    assert window.beside_page is None and not window.beside.isVisible()
    assert window.current_document is ley


def test_the_tools_act_on_the_half_clicked(window, sample, wait_until):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    tema, ley = window.documents
    assert window.show_beside(tema)
    tema.view.setFocus()
    wait_until(lambda: window.current_document is tema)
    assert window.pdf_view is tema.view and window.pages.currentWidget() is ley
    assert window.beside.property("active")
    wait_until(lambda: 0 in tema.view._texts)
    tema.view.select((0, 0), (0, 10))
    assert tema.view.mark_selection(HIGHLIGHT)
    wait_until(lambda: tema.view.modified)
    assert not ley.view.modified
    ley.view.setFocus()
    wait_until(lambda: window.current_document is ley)
    assert not window.beside.property("active")
    assert tema.view.modified


def test_choosing_the_tab_of_the_one_beside_works_on_it(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    tema, ley, form = window.documents
    window.show_beside(tema)
    assert window.pages.currentWidget() is form
    window.document_tabs.setCurrentIndex(0)
    assert window.current_document is tema and window.pages.currentWidget() is form
    window.document_tabs.setCurrentIndex(1)
    assert window.pages.currentWidget() is ley and window.beside_page is tema


def test_putting_the_one_in_front_beside_brings_another_in_front(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    tema, ley = window.documents
    window._beside_from_tab(1)  # right click on its own tab
    assert window.beside_page is ley and window.pages.currentWidget() is tema
    window._beside_from_tab(1)
    assert window.beside_page is None


def test_closing_either_half_goes_back_to_one(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    tema, ley = window.documents
    window.show_beside(tema)
    window.close_document(0)
    assert window.beside_page is None and not window.beside.isVisible()
    assert window.documents == [ley] and window.pages.currentWidget() is ley
    open_samples(window, sample, "boe.pdf")
    ley, tema = window.documents
    window.show_beside(tema)
    window.close_document(0)  # the one on the left
    assert window.documents == [tema] and window.beside_page is None
    assert window.pages.currentWidget() is tema and tema.isVisible()


def test_with_one_open_it_asks_for_the_other(window, sample, monkeypatch):
    open_samples(window, sample, "boe.pdf")
    monkeypatch.setattr(
        window, "choose_and_open", lambda: window.open_document(sample("largo.pdf"))
    )
    window.toggle_beside()
    tema, ley = window.documents
    assert window.beside_page is ley and window.current_document is tema


def test_with_three_open_it_offers_the_others(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    window.toggle_beside()
    names = [action.text() for action in window.beside_menu.actions()]
    assert names == ["boe.pdf", "largo.pdf"]
    window.beside_menu.actions()[1].trigger()
    window.beside_menu.close()
    assert window.beside_page is window.documents[1]
