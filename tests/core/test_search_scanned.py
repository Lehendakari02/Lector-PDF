"""The search and the marks on scanned pages, with the text really read by
the text recognition (not a clean PDF), and the approximate search for text
badly read by another program."""

import pymupdf
import pytest

from app.core import ocr
from app.core.commands import HIGHLIGHT, markup_for_selection
from app.core.search import (
    DEFAULT_OPTIONS,
    SearchOptions,
    approximate_text,
    find_across_pages,
    find_in_page,
    read_page_text,
)
from app.core.text_layer import AddTextLayer, PageLayer

APPROXIMATE = SearchOptions(approximate=True)
WHOLE = SearchOptions(whole_word=True)


@pytest.fixture(scope="module")
def recognised(tmp_path_factory):
    """The scanned sample, its three pages read and written as in the program, saved."""
    from tests.conftest import SAMPLES_DIR

    path = tmp_path_factory.mktemp("ocr") / "reconocido.pdf"
    with pymupdf.open(SAMPLES_DIR / "escaneado.pdf") as doc:
        layers = tuple(PageLayer.of(ocr.recognize_page(doc[n], n)) for n in range(3))
        AddTextLayer(layers).apply(doc)
        doc.save(path, garbage=0, deflate=True)
    doc = pymupdf.open(path)
    yield doc, [read_page_text(doc[n]) for n in range(3)]
    doc.close()


def hits(texts, query, options=DEFAULT_OPTIONS):
    return [hit for n, text in enumerate(texts) for hit in find_in_page(text, query, options, n)]


def test_words_with_accents_and_capitals_are_found_without_them(recognised):
    _, texts = recognised
    assert len(hits(texts, "articulo")) == 15  # five articles on each page
    assert [hit.match for hit in hits(texts, "CAMION")] == ["camión"] * 3
    assert hits(texts, "administracion publica")


def test_n_with_tilde_is_not_an_n(recognised):
    _, texts = recognised
    assert hits(texts, "año")
    assert not hits(texts, "ano", WHOLE), "año is not ano"


def test_phrases_that_go_on_to_the_next_line(recognised):
    _, texts = recognised
    # "…contado desde el día siguiente al de la / publicación de la convocatoria"
    found = hits(texts, "al de la publicacion de la convocatoria")
    assert found and len(found[0].rects) == 2, "two lines marked"


def test_whole_words(recognised):
    _, texts = recognised
    assert hits(texts, "ley", WHOLE)
    assert not hits(texts, "le", WHOLE) or all(
        hit.match.lower() == "le" for hit in hits(texts, "le", WHOLE)
    )


def test_the_mark_falls_on_the_words_of_the_picture(recognised):
    doc, texts = recognised
    hit = hits(texts, "camion")[0]
    page = hit.page
    word = next(
        w
        for w in ocr.recognize_page(pymupdf.open(doc.name)[page], page).words
        if w.text.startswith("camión")
    )
    order = None
    text = texts[page]
    start = text.chars.index("camión")
    order = markup_for_selection(HIGHLIGHT, (page, start), (page, start + 6), lambda n: texts[n])
    assert order is not None
    (mark,) = order.marks
    x0, y0, x1, y1 = mark.rects[0]
    wx0, wy0, wx1, wy1 = ocr.recognize_page(doc[page], page).shown_rect(word)
    assert abs(x0 - wx0) < 4 and abs(x1 - wx1) < 4
    assert y0 < (wy0 + wy1) / 2 < y1


def test_approximate_text_makes_look_alikes_the_same():
    assert approximate_text("Artículo 1") == approximate_text("Articu1o l")
    assert approximate_text("camión") == approximate_text("carnion")
    assert approximate_text("año") == approximate_text("ano")
    assert approximate_text("declaración") == approximate_text("dedaracion")
    assert approximate_text("eficacia") == approximate_text("ef icacia")


def test_approximate_search_finds_a_poor_text(sample):
    with pymupdf.open(sample("ocr-malo.pdf")) as doc:
        texts = [read_page_text(doc[n]) for n in range(doc.page_count)]
    assert not hits(texts, "artículo")
    found = hits(texts, "artículo", APPROXIMATE)
    assert len(found) == 10
    assert found[0].match == "Articu1o"
    phrase = hits(texts, "la Administración pública", APPROXIMATE)
    assert phrase and phrase[0].match == "La Adrninistracion pub1ica"
    assert hits(texts, "eficacia", APPROXIMATE)[0].match == "ef icacia"
    assert "Articu1o 3. E1" in hits(texts, "camión", APPROXIMATE)[0].before


def test_approximate_search_leaves_whole_words_and_exact_aside(sample):
    with pymupdf.open(sample("ocr-malo.pdf")) as doc:
        texts = [read_page_text(doc[n]) for n in range(doc.page_count)]
    both = SearchOptions(whole_word=True, exact=True, approximate=True)
    assert len(hits(texts, "articulo", both)) == 10


def test_approximate_search_goes_on_to_the_next_page(sample):
    with pymupdf.open(sample("largo.pdf")) as doc:
        first, second = read_page_text(doc[0]), read_page_text(doc[1])
    tail = first.chars[-40:].split()
    head = second.chars[:60].split()
    phrase = " ".join(tail[-2:] + head[:2])
    exact = find_across_pages(first, second, phrase)
    approximate = find_across_pages(first, second, phrase, APPROXIMATE)
    assert len(approximate) >= len(exact)
