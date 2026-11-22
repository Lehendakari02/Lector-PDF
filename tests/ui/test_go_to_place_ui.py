"""Tests for going to an article or a section by writing it in the page box."""

import pymupdf


def open_boe(window, sample, wait_until):
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
    return window.pdf_view, window.page_box


def write(box, text):
    box.edit.setText(text)
    box.edit.returnPressed.emit()


def test_writing_an_article_goes_to_its_heading(window, sample, wait_until):
    view, box = open_boe(window, sample, wait_until)
    answers = []
    view.place_answered.connect(answers.append)
    window.go_to_page_action.trigger()
    write(box, "art. 14")
    wait_until(lambda: answers)
    assert answers == [True]
    assert view.current_page == 4
    assert box.edit.text() == "5", "the box shows the page again"
    assert view.hasFocus(), "the document has the keyboard back"
    # The heading is near the top of the window, not just somewhere in it.
    with pymupdf.open(sample("boe.pdf")) as doc:
        heading = doc[4].search_for("Artículo 14.")[0]
    zoom = view._render_zoom()
    top = view._tops[4] + heading.y0 * zoom - view._scroll_y()
    assert 0 <= top < view._to_pixels(view.viewport().height()) / 4


def test_the_same_part_again_goes_to_the_next_one(window, sample, wait_until):
    view, box = open_boe(window, sample, wait_until)
    answers = []
    view.place_answered.connect(answers.append)
    write(box, "capítulo primero")
    wait_until(lambda: len(answers) == 1)
    first = view.current_page
    write(box, "Capítulo I")  # written another way: the same place
    wait_until(lambda: len(answers) == 2)
    assert view.current_page > first


def test_what_is_not_there_is_said(window, sample, wait_until):
    view, box = open_boe(window, sample, wait_until)
    page = view.current_page
    write(box, "art. 900")
    wait_until(lambda: "No encuentro «art. 900»" in window.statusBar().currentMessage())
    assert view.current_page == page
    write(box, "hola")
    assert "Escribe un número de página" in window.statusBar().currentMessage()


def test_a_number_alone_is_still_a_page(window, sample, wait_until):
    view, box = open_boe(window, sample, wait_until)
    write(box, "14")
    assert view.current_page == 13


def test_ir_a_articulo_of_the_study_mode_leaves_the_box_ready(window, sample, wait_until):
    view, box = open_boe(window, sample, wait_until)
    window.feature_actions["go_to_article"].trigger()
    assert box.edit.hasFocus() and box.edit.text() == ""
    assert box.edit.placeholderText() == "art. 14"
