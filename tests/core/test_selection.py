"""Tests for selecting and copying the text of a page."""

import pymupdf
import pytest

from app.core.search import PageText, read_page_text
from app.core.selection import caret_at, is_on_text, selected_text, selection_rects, word_at


@pytest.fixture(scope="module")
def split_page():
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "texto-partido.pdf") as doc:
        yield read_page_text(doc[0])


def make_page(paragraphs: list[list[str]]) -> PageText:
    """A page with these paragraphs, each a list of lines."""
    doc = pymupdf.open()
    page = doc.new_page()
    top = 100
    for lines in paragraphs:
        for line in lines:
            page.insert_text((72, top), line, fontsize=11)
            top += 14
        top += 30
    return read_page_text(page)


def carets_of(text: PageText, words: str) -> tuple[int, int]:
    start = text.chars.index(words)
    return start, start + len(words)


def test_the_caret_lands_between_the_letters_nearest_to_the_pointer():
    page = make_page([["Hola mundo"]])
    x0, y0, x1, y1 = page.box(0)  # the "H"
    middle = (y0 + y1) / 2
    assert caret_at(page, x0 + 0.5, middle) == 0  # left half of the letter: before it
    assert caret_at(page, x1 - 0.5, middle) == 1  # right half: after it
    assert caret_at(page, 5, middle) == 0  # far to the left of the line
    assert caret_at(page, 590, middle) == len(page)  # far to the right
    assert caret_at(page, x0 + 0.5, 700) == 0  # below every line: the nearest line


def test_the_line_at_the_height_of_the_pointer_wins():
    page = make_page([["Primera línea corta", "Segunda línea bastante más larga que la otra"]])
    second = page.chars.index("Segunda")
    top = page.box(0)[1]
    # Right of the short first line, at its height: its end, not the long line below.
    assert caret_at(page, 400, top + 3) == second  # the caret after "corta"


def test_a_page_without_text_has_no_caret():
    assert caret_at(PageText(), 10, 10) is None
    assert selected_text(PageText(), 0, 10) == ""
    assert selection_rects(PageText(), 0, 10) == ()
    assert word_at(PageText(), 3) == (0, 0)


def test_pointer_on_text_or_on_blank_paper():
    page = make_page([["Hola mundo"]])
    x0, y0, x1, y1 = page.box(2)
    assert is_on_text(page, x0, (y0 + y1) / 2)
    assert not is_on_text(page, x0, y1 + 60)
    assert not is_on_text(page, 500, (y0 + y1) / 2)


def test_double_click_selects_the_word():
    page = make_page([["La Administración pública, sirve."]])
    start, stop = carets_of(page, "Administración")
    assert word_at(page, start + 4) == (start, stop)
    assert word_at(page, stop) == (start, stop)  # just after the last letter
    comma = page.chars.index(",")
    assert word_at(page, comma + 1) == (comma + 1, comma + 2)  # the space, alone


def test_copied_text_of_one_line():
    page = make_page([["Los españoles son iguales ante la ley."]])
    start, stop = carets_of(page, "españoles son")
    assert selected_text(page, start, stop) == "españoles son"
    assert selected_text(page, 0, 10_000) == "Los españoles son iguales ante la ley."


def test_lines_of_a_paragraph_are_copied_as_running_text(split_page):
    start = split_page.chars.index("Los españoles")
    stop = split_page.chars.index("jero.") + len("jero.")
    copied = selected_text(split_page, start, stop)
    # Words split at line ends are whole again, and there are no line breaks inside.
    assert "discriminación alguna" in copied
    assert "cualquier otra condición" in copied
    assert "este Artículo se aplicará" in copied
    assert "extranjero." in copied
    assert "-" not in copied


def test_paragraphs_start_on_a_new_line():
    page = make_page([["Artículo 1.", "Primera frase"], ["Artículo 2.", "Segunda frase"]])
    assert selected_text(page, 0, len(page)) == (
        "Artículo 1. Primera frase\nArtículo 2. Segunda frase"
    )


def test_real_hyphens_are_kept():
    page = make_page([["El convenio Madrid-Barcelona y la Ley 39-", "2015."]])
    assert selected_text(page, 0, len(page)) == "El convenio Madrid-Barcelona y la Ley 39- 2015."


def test_selection_marks_one_rectangle_per_line(split_page):
    start = split_page.chars.index("Los españoles")
    stop = split_page.chars.index("ción alguna") + 4
    rects = selection_rects(split_page, start, stop)
    assert len(rects) == 2
    assert rects[0][1] < rects[1][1]
    assert selection_rects(split_page, start, start) == ()


def test_real_law_copies_an_article(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        for page in doc:
            text = read_page_text(page)
            if "Artículo 14." in text.chars:
                break
    start = text.chars.index("Los españoles son iguales")
    stop = text.chars.index("personal o social.") + len("personal o social.")
    assert selected_text(text, start, stop) == (
        "Los españoles son iguales ante la ley, sin que pueda prevalecer discriminación "
        "alguna por razón de nacimiento, raza, sexo, religión, opinión o cualquier otra "
        "condición o circunstancia personal o social."
    )
