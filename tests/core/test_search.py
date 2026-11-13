"""Tests for the document search (task 0.7)."""

import pymupdf
import pytest

from app.core.search import (
    DEFAULT_OPTIONS,
    SearchOptions,
    find_in_page,
    prepare_query,
    read_page_text,
    search_document,
)

WHOLE = SearchOptions(whole_word=True)
EXACT = SearchOptions(exact=True)


@pytest.fixture(scope="module")
def split_page():
    """The sample with words split at line ends, "año" and "ano"."""
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "texto-partido.pdf") as doc:
        yield read_page_text(doc[0])


@pytest.fixture(scope="module")
def boe():
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "boe.pdf") as doc:
        yield doc


def matches(text, query, options=DEFAULT_OPTIONS):
    return [hit.match for hit in find_in_page(text, query, options)]


def make_page(lines: list[str]):
    """A page with exactly these lines of text."""
    doc = pymupdf.open()
    page = doc.new_page()
    for number, line in enumerate(lines):
        page.insert_text((72, 100 + 20 * number), line, fontsize=11)
    return read_page_text(page)


# ---- the three promises of the task ----------------------------------------


def test_accents_and_capitals_do_not_matter(split_page):
    assert matches(split_page, "camion") == ["camión"]
    assert matches(split_page, "CAMIÓN") == ["camión"]
    assert matches(split_page, "administracion") == ["Administración"]


def test_a_word_split_at_the_end_of_a_line_is_found(split_page):
    hits = find_in_page(split_page, "articulo")
    # The result is shown as the whole word, without the line-end hyphen.
    assert [hit.match for hit in hits] == ["Artículo", "Artículo"]
    split = hits[1]
    assert len(split.rects) == 2, "one mark on each of the two lines"
    assert split.rects[0][1] < split.rects[1][1], "first piece above the second"
    assert split.before.endswith("Lo dispuesto en este ")
    assert split.after.startswith(" se aplicará durante")


def test_n_with_tilde_is_not_n(split_page):
    assert "ano" not in [hit.match.lower() for hit in find_in_page(split_page, "año", WHOLE)]
    assert matches(split_page, "año", WHOLE) == ["año", "año", "año"]
    assert matches(split_page, "ano") == ["ano"], '"ano" must not find "año"'
    assert matches(split_page, "espanoles") == []
    assert matches(split_page, "españoles") == ["españoles"]


# ---- phrases ----------------------------------------------------------------


def test_a_phrase_that_continues_on_the_next_line_is_found(split_page):
    hits = find_in_page(split_page, "extranjero. la administracion velara")
    assert len(hits) == 1
    assert len(hits[0].rects) == 3


def test_a_phrase_across_a_split_word(split_page):
    assert matches(split_page, "vehiculos pesados") == ["vehículos pesados"]
    assert matches(split_page, "prevalecer discriminacion alguna") != []


def test_real_boe_text(boe):
    found = [hit for _page, hits in search_document(boe, "derecho a la educacion") for hit in hits]
    assert [hit.page for hit in found] == [7]
    assert found[0].match == "derecho a la educación"
    # Split across lines in the real document.
    phrase = "sin que pueda prevalecer discriminacion alguna por razon de nacimiento"
    assert sum(len(hits) for _page, hits in search_document(boe, phrase)) == 1


def test_extra_spaces_in_the_query_do_not_matter(split_page):
    assert len(matches(split_page, "  igualdad   ante la  ley ")) == 1


def test_typing_the_hyphen_of_a_split_word_also_works(split_page):
    assert matches(split_page, "articu-lo") == ["Artícu-lo"]


# ---- hyphens that are part of the word --------------------------------------


def test_a_real_hyphen_inside_a_line_is_kept():
    page = make_page(["Estudio físico-químico del agua."])
    assert matches(page, "fisico-quimico") == ["físico-químico"]
    assert matches(page, "fisicoquimico") == []


def test_a_compound_word_split_at_its_own_hyphen_is_found_both_ways():
    page = make_page(["Un estudio muy completo de tipo físico-", "químico sobre el agua."])
    assert matches(page, "fisico-quimico") == ["físico-químico"]
    # Without the hyphen it is found too: nobody can tell whether the hyphen
    # at the end of the line belongs to the word or only splits it.
    assert matches(page, "fisicoquimico") == ["físicoquímico"]


def test_a_hyphen_before_a_capital_or_a_number_does_not_join():
    page = make_page(["Véase la Ley 39-", "2015 y el convenio Madrid-", "Barcelona."])
    assert matches(page, "392015") == []
    assert matches(page, "madridbarcelona") == []
    assert matches(page, "ley 39-") == ["Ley 39-"]


def test_soft_hyphens_are_invisible():
    """Some PDFs carry an invisible "may be split here" mark inside words."""
    from app.core.search import PageText

    letters = "La adminis\u00adtración pública."
    page = PageText(
        chars=list(letters),
        boxes=[(10.0 * n, 0.0, 10.0 * n + 10, 12.0) for n in range(len(letters))],
        lines=[0] * len(letters),
    )
    assert matches(page, "administracion") == ["administración"]
    assert prepare_query("adminis\u00adtracion") == "administracion"


# ---- options ------------------------------------------------------------------


def test_whole_word():
    page = make_page(["La ley y las leyes. Leyenda: ley.", "El articulo 14 y el 140."])
    assert len(matches(page, "ley")) == 4
    assert len(matches(page, "ley", WHOLE)) == 2
    assert len(matches(page, "14")) == 2
    assert len(matches(page, "14", WHOLE)) == 1
    assert len(matches(page, "articulo 14", WHOLE)) == 1


def test_exact_match_counts_accents_and_capitals(split_page):
    assert matches(split_page, "Administración", EXACT) == ["Administración"]
    assert matches(split_page, "administración", EXACT) == []
    assert matches(split_page, "Administracion", EXACT) == []
    assert matches(split_page, "camión", EXACT) == ["camión"]


def test_empty_queries_find_nothing(split_page):
    assert matches(split_page, "") == []
    assert matches(split_page, "   ") == []
    assert prepare_query("  Artículo ­ 14 ") == "articulo 14"


# ---- where the results are ----------------------------------------------------


def test_the_mark_covers_the_word_on_the_page(boe):
    page = boe[4]
    hit = find_in_page(read_page_text(page), "articulo 14", WHOLE, 4)[0]
    assert hit.page == 4
    x0, y0, x1, y1 = hit.rects[0]
    inside = page.get_text("text", clip=pymupdf.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)).strip()
    assert inside.rstrip(".") == "Artículo 14"


def test_results_come_in_reading_order(boe):
    pages = [hit.page for _page, hits in search_document(boe, "constitucion") for hit in hits]
    assert pages == sorted(pages)
    assert len(pages) > 50


def test_pages_without_text_have_no_results(sample):
    with pymupdf.open(sample("escaneado.pdf")) as doc:
        assert all(hits == [] for _page, hits in search_document(doc, "a"))


def test_bad_ocr_text_is_searched_as_it_is(sample):
    """The fuzzy search for OCR mistakes belongs to phase 2B, not to this task."""
    with pymupdf.open(sample("ocr-malo.pdf")) as doc:
        text = read_page_text(doc[0])
    assert matches(text, "articu1o") != []


def test_a_520_page_document_is_searched_in_a_few_seconds(sample):
    import time

    started = time.perf_counter()
    with pymupdf.open(sample("largo.pdf")) as doc:
        total = sum(len(hits) for _page, hits in search_document(doc, "articulo"))
    assert total > 1000
    assert time.perf_counter() - started < 15  # measured: under 1 second


# ---- awkward text: joined letters, accents in two pieces, page breaks ------------


@pytest.fixture(scope="module")
def tricky():
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "texto-dificil.pdf") as doc:
        yield [read_page_text(page) for page in doc]


def test_the_sample_really_is_awkward():
    """The file must keep its traps, or the tests below prove nothing."""
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "texto-dificil.pdf") as doc:
        raw = doc[0].get_text("text", flags=pymupdf.TEXT_PRESERVE_LIGATURES)
    assert "oﬁcina" in raw and "conﬂicto" in raw  # one glyph for "fi" and "fl"
    assert "año" in raw  # "n" followed by a separate tilde


def test_joined_letters_are_found(tricky):
    assert matches(tricky[0], "oficina") == ["oficina"]
    assert matches(tricky[0], "conflicto") == ["conflicto"]
    assert matches(tricky[0], "eficacia", WHOLE) == ["eficacia"]
    assert matches(tricky[0], "oficina", EXACT) == ["oficina"]
    hit = find_in_page(tricky[0], "fi")[0]
    assert hit.rects[0][2] > hit.rects[0][0], "the mark has some width"


def test_accents_written_in_two_pieces(tricky):
    assert matches(tricky[0], "año", WHOLE) == ["año"]
    assert matches(tricky[0], "ano") == [], '"ano" must not find "año"'
    assert matches(tricky[0], "camion") == ["camión"]
    assert matches(tricky[0], "camión", EXACT) == ["camión"]
    assert matches(tricky[0], "cañada") == ["cañada"]
    assert matches(tricky[0], "canada") == []


def test_a_phrase_that_goes_on_to_the_next_page(tricky):
    from app.core.search import find_across_pages

    first, second = tricky
    # Not on either page alone: the footer and the header are in between.
    assert matches(first, "presentar alegaciones") == []
    assert matches(second, "presentar alegaciones") == []
    hits = find_across_pages(first, second, "presentar alegaciones", page=0)
    assert [hit.match for hit in hits] == ["presentar alegaciones"]
    hit = hits[0]
    assert hit.page == 0
    assert len(hit.rects) == 1 and len(hit.next_rects) == 1
    assert hit.rects[0][1] > 600, "first piece at the bottom of the first page"
    assert hit.next_rects[0][1] < 150, "second piece at the top of the next page"
    assert hit.before.endswith("los interesados podrán ")
    assert hit.after.startswith(" en el plazo")


def test_a_word_split_between_two_pages(tricky):
    from app.core.search import find_across_pages

    hits = find_across_pages(tricky[0], tricky[1], "alegaciones", WHOLE, page=0)
    assert [hit.match for hit in hits] == ["alegaciones"]


def test_results_inside_one_page_are_not_repeated(tricky):
    from app.core.search import find_across_pages

    assert find_across_pages(tricky[0], tricky[1], "interesados") == []
    assert find_across_pages(tricky[0], tricky[1], "plazo") == []
    assert find_across_pages(tricky[0], tricky[1], "temario de prueba") == []
    assert find_across_pages(tricky[0], tricky[1], "") == []


def test_headers_and_footers_do_not_join_pages(tricky):
    from app.core.search import find_across_pages

    # "alega- / Página 1 / Temario de prueba / ciones": none of this is a phrase.
    assert find_across_pages(tricky[0], tricky[1], "pagina 1 temario") == []
    assert find_across_pages(tricky[0], tricky[1], "prueba ciones") == []


def test_whole_document_search_includes_page_breaks():
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "texto-dificil.pdf") as doc:
        found = dict(search_document(doc, "presentar alegaciones en el plazo"))
    assert [hit.match for hit in found[0]] == ["presentar alegaciones en el plazo"]
    assert found[1] == []


def test_real_law_phrase_across_pages(boe):
    """In the BOE sample, article 20 runs from one page to the next."""
    from app.core.search import _reading_lines, find_across_pages

    crossing = 0
    for number in range(boe.page_count - 1):
        first, second = read_page_text(boe[number]), read_page_text(boe[number + 1])
        # The last reading line of a page and the first of the next, joined:
        last = _reading_lines(first, [(second, 1)])[-1]
        start = _reading_lines(second, [(first, -1)])[0]
        words_before = first.chars[last[0] : last[1]].split()[-2:]
        words_after = second.chars[start[0] : start[1]].split()[:2]
        assert "BOLETÍN" not in words_after and "LEGISLACIÓN" not in words_after
        assert not (words_before and words_before[0] == "Página")
        phrase = " ".join(words_before + words_after)
        if find_across_pages(first, second, phrase, page=number):
            crossing += 1
    assert crossing >= 30, "most page breaks of the law can be searched across"


def test_page_text_is_compact():
    page = make_page(["Una línea de prueba con bastantes letras para medir."] * 40)
    assert isinstance(page.chars, str)
    assert page.size_in_bytes() < 60 * len(page)  # it used to be about 230 per letter
    assert len(page.boxes) == 4 * len(page)


# ---- a phrase copied from the document and pasted into the search box ----


def _copied_across(doc, number, tail_letters=260, head_letters=200):
    """What copying the end of a page and the start of the next one gives."""
    from app.core.selection import selected_text

    first, second = read_page_text(doc[number]), read_page_text(doc[number + 1])
    end = selected_text(first, max(0, len(first) - tail_letters), len(first))
    start = selected_text(second, 0, head_letters)
    return first, second, end + "\n" + start


def test_a_phrase_copied_with_the_footer_in_the_middle_is_found(boe):
    from app.core.search import find_across_pages

    for number in range(1, boe.page_count - 1):
        before = read_page_text(boe[number - 1])
        first, second, copied = _copied_across(boe, number)
        hits = find_across_pages(first, second, copied, page=number, before=before)
        assert len(hits) == 1, f"page {number + 1}"
        assert hits[0].rects and hits[0].next_rects


def test_a_title_at_the_same_height_on_two_pages_is_not_a_header(boe):
    # Pages 7, 8 and 9 of the sample all open with "Artículo N." at the same height.
    phrase = "organizaciones profesionales. Artículo 27. 1. Todos tienen"
    found = [hit for _page, hits in search_document(boe, phrase) for hit in hits]
    assert len(found) == 1 and found[0].next_rects


def test_a_long_phrase_reaches_further_than_a_few_lines(boe):
    from app.core.search import find_across_pages

    first, second, copied = _copied_across(boe, 5, tail_letters=1500, head_letters=1500)
    assert len(copied) > 2500
    before = read_page_text(boe[4])
    assert len(find_across_pages(first, second, copied, page=5, before=before)) == 1


def test_a_pasted_word_split_at_a_line_end_is_found_joined():
    page = make_page(["El procedimiento administrativo común", "se regula por ley."])
    assert len(find_in_page(page, "procedi- miento administrativo")) == 1
    assert len(find_in_page(page, "procedi-\nmiento")) == 1
    assert find_in_page(page, "procedi- xx") == []
