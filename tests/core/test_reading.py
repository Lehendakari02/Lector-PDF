"""Tests for the text of a page as a screen reader reads it."""

import pymupdf
import pytest

from app.core import reading
from app.core.reading import ReadingText, reading_text
from app.core.search import PageText, read_page_text
from app.core.selection import selected_text


@pytest.fixture(scope="module")
def split_page():
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "texto-partido.pdf") as doc:
        yield read_page_text(doc[0])


def make_page(paragraphs: list[list[str]]) -> PageText:
    doc = pymupdf.open()
    page = doc.new_page()
    top = 100
    for lines in paragraphs:
        for line in lines:
            page.insert_text((72, top), line, fontsize=11)
            top += 14
        top += 30
    return read_page_text(page)


def test_paragraphs_are_lines_and_their_lines_are_joined():
    page = make_page([["Artículo 1.", "Primera frase"], ["Artículo 2.", "Segunda frase"]])
    reading = reading_text(page)
    assert reading.text == "Artículo 1. Primera frase\nArtículo 2. Segunda frase"
    assert reading.text == selected_text(page, 0, len(page))  # the same as "Copiar"


def test_words_split_at_line_ends_are_read_whole(split_page):
    reading = reading_text(split_page)
    assert "discriminación alguna" in reading.text
    assert "extranjero." in reading.text


def test_every_character_knows_its_letter_on_the_page(split_page):
    reading = reading_text(split_page)
    assert len(reading.letters) == len(reading.text)
    assert list(reading.letters) == sorted(reading.letters)
    for offset, char in enumerate(reading.text):
        if char not in " \n":
            assert split_page.chars[reading.letter_at(offset)] == char
    start = reading.text.index("Los españoles")
    letter = reading.letter_at(start)
    assert split_page.chars[letter : letter + 13] == "Los españoles"
    assert reading.offset_of(letter) == start


def test_the_places_at_the_edges():
    page = make_page([["Hola mundo"]])
    reading = reading_text(page)
    assert reading.letter_at(0) == 0
    assert reading.letter_at(len(reading.text)) == len(page)  # after the last letter
    assert reading.offset_of(0) == 0
    assert reading.offset_of(len(page)) == len(reading.text)
    empty = ReadingText()
    assert empty.letter_at(5) == 0 and empty.offset_of(3) == 0


def test_a_page_without_text_reads_nothing():
    assert reading_text(PageText()).text == ""


def test_a_real_law_reads_as_running_text(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        for page in doc:
            text = read_page_text(page)
            if "Artículo 14." in text.chars:
                break
    reading = reading_text(text)
    assert (
        "Los españoles son iguales ante la ley, sin que pueda prevalecer discriminación "
        "alguna por razón de nacimiento"
    ) in reading.text


def test_the_reading_cursor_comes_on_with_a_screen_reader_unless_told_not_to():
    settings = {}

    class Kept:
        def get(self, key, default=None):
            return settings.get(key, default)

    kept = Kept()
    assert not reading.cursor_wanted(kept, screen_reader=False)
    assert reading.cursor_wanted(kept, screen_reader=True)
    settings[reading.WITH_SCREEN_READER_SETTING] = False
    assert not reading.cursor_wanted(kept, screen_reader=True)
    settings[reading.CURSOR_SETTING] = True
    assert reading.cursor_wanted(kept, screen_reader=False)
