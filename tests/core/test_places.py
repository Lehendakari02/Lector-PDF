"""Tests for finding an article, a section or a part by its number."""

import pymupdf
import pytest

from app.core.places import (
    ARTICLE,
    CONTENTS,
    HEADING,
    MENTION,
    PART,
    SECTION,
    PlaceSearch,
    Wanted,
    line_matches,
    parse_wanted,
    rank_of,
)
from app.core.search import read_page_text


@pytest.mark.parametrize(
    ("typed", "wanted"),
    [
        ("art. 14", Wanted(ARTICLE, "14")),
        ("Art 14", Wanted(ARTICLE, "14")),
        ("artículo 14", Wanted(ARTICLE, "14")),
        ("ARTICULO 14 BIS", Wanted(ARTICLE, "14 bis")),
        ("art. 149.1", Wanted(ARTICLE, "149")),
        ("artículo único", Wanted(ARTICLE, "unico")),
        ("3.2", Wanted(SECTION, "3.2")),
        ("3.2.1.", Wanted(SECTION, "3.2.1")),
        ("apartado 3", Wanted(SECTION, "3")),
        ("capítulo II", Wanted(PART, "2", "capitulo")),
        ("capitulo 2", Wanted(PART, "2", "capitulo")),
        ("Capítulo segundo", Wanted(PART, "2", "capitulo")),
        ("cap. 2", Wanted(PART, "2", "capitulo")),
        ("título preliminar", Wanted(PART, "preliminar", "titulo")),
        ("Título X", Wanted(PART, "10", "titulo")),
        ("disposición adicional primera", Wanted(PART, "1", "disposicion adicional")),
        ("DA 1", Wanted(PART, "1", "disposicion adicional")),
        ("disposición derogatoria", Wanted(PART, "", "disposicion derogatoria")),
        ("sección 2.ª", Wanted(PART, "2", "seccion")),
        ("tema 5", Wanted(PART, "5", "tema")),
        ("anexo B", Wanted(PART, "b", "anexo")),
    ],
)
def test_places_are_understood_as_people_write_them(typed, wanted):
    assert parse_wanted(typed) == wanted


@pytest.mark.parametrize("typed", ["", "14", "hola", "art.", "capítulo zeta", "la ley"])
def test_what_is_not_a_place(typed):
    assert parse_wanted(typed) is None


def test_a_heading_starts_the_line_and_has_the_same_number():
    article = parse_wanted("art 14")
    assert line_matches("Artículo 14.  ", article)
    assert line_matches("Art. 14.- Igualdad", article)
    assert not line_matches("Artículo 149.", article)
    assert not line_matches("Artículo 1.", article)
    assert not line_matches("Según el artículo 14", article)
    assert not line_matches("Artículo 14 bis.", article)
    assert line_matches("Artículo 14 bis.", parse_wanted("art 14 bis"))
    chapter = parse_wanted("capitulo 2")
    assert line_matches("CAPÍTULO SEGUNDO", chapter)
    assert line_matches("Capítulo II. Derechos", chapter)
    assert not line_matches("CAPÍTULO TERCERO", chapter)
    additional = parse_wanted("disposicion adicional 1")
    assert line_matches("Disposición adicional primera.  ", additional)
    assert not line_matches("Disposiciones adicionales . . . . . 39", parse_wanted("disposicion"))
    section = parse_wanted("3.2")
    assert line_matches("3.2. Los derechos", section)
    assert line_matches("3.2 Los derechos", section)
    assert not line_matches("3.21. Otro", section)
    assert not line_matches("13.2. Otro", section)


def test_lines_of_a_table_of_contents_and_sentences_count_less():
    assert rank_of("CAPÍTULO SEGUNDO") == HEADING
    assert rank_of("TÍTULO I. De los derechos . . . . . . . . . 5") == CONTENTS
    assert rank_of("3.2 Los derechos      12") == CONTENTS
    assert rank_of("artículo 14 de la Constitución") == MENTION


def find(doc, typed, after=None):
    looking = PlaceSearch(parse_wanted(typed), doc.page_count, after)
    while not looking.done:
        looking.take(read_page_text(doc[looking.next_page()]))
    return looking.answer


def test_in_the_constitution_the_heading_not_the_index(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        found = find(doc, "art. 14")
        assert found is not None and found.rank == HEADING
        assert found.page == 4
        line = read_page_text(doc[4]).chars[found.letter : found.letter + 12]
        assert line == "Artículo 14."
        title = find(doc, "título I")
        assert title.page == 3, "TÍTULO I of page 1 is the index"
        assert find(doc, "capítulo segundo").page == 4
        assert find(doc, "disposición transitoria quinta").page == 37
        assert find(doc, "art. 500") is None


def test_the_same_place_again_goes_on_to_the_next_one(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        first = find(doc, "capítulo primero")
        second = find(doc, "capítulo primero", (first.page, first.letter))
        third = find(doc, "capítulo primero", (second.page, second.letter))
        assert first.page < second.page < third.page
        # Round the document: after the last one, the first one again.
        again = find(doc, "capítulo primero", (third.page, third.letter))
        assert (again.page, again.letter) == (first.page, first.letter)


def test_only_one_comes_back_to_itself():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Artículo 3. Uno.", fontsize=12)
    found = find(doc, "art 3")
    assert found is not None
    assert find(doc, "art 3", (found.page, found.letter)) == found


def test_a_heading_wins_over_a_mention_found_before_it():
    doc = pymupdf.open()
    first = doc.new_page()
    first.insert_text((72, 100), "como dice el", fontsize=12)
    first.insert_text((72, 120), "artículo 7 de la ley", fontsize=12)
    doc.new_page().insert_text((72, 100), "Artículo 7. Del plazo.", fontsize=12)
    assert find(doc, "art 7").page == 1
    assert find(doc, "art 8") is None


def test_on_a_page_kept_turned_the_line_is_where_it_is_seen():
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((150, 300), "Artículo 5.", fontsize=14)
    page.set_rotation(90)
    found = find(doc, "art 5")
    x0, y0, x1, y1 = found.rect
    assert x1 - x0 < y1 - y0, "the line runs down the turned page"
