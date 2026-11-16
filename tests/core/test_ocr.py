"""Tests for recognising the text of scanned pages: straightening the
picture, reading it and the process that reads one page after another."""

import hashlib
import time

import pymupdf
import pytest

from app.core import ocr
from app.core.ocr import OcrError, OcrFailure, Recognizer, looks_scanned, recognize_page

WAIT_SECONDS = 120  # generous: test machines are slow and shared


@pytest.fixture(scope="module")
def recognised():
    """The first scanned sample page, recognised once for all the tests."""
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "escaneado.pdf") as doc:
        yield recognize_page(doc[0])


def wait_for(recognizer: Recognizer, count: int = 1) -> list:
    deadline = time.monotonic() + WAIT_SECONDS
    found = []
    while time.monotonic() < deadline:
        found += recognizer.results()
        if len(found) >= count:
            return found
        time.sleep(0.05)
    recognizer.close()
    raise AssertionError("timed out")


def tilted_page(degrees: float, rotation: int = 0):
    """A page of known text, scanned slanted by ``degrees``, shown turned ``rotation``."""
    from tests.ejemplos import generar

    source = pymupdf.open()
    page = source.new_page(width=595, height=842)
    top = 72.0
    for number in range(1, 4):
        top = generar.write_article(page, top, number, generar.ARTICLE_TEXTS[number])
    matrix = pymupdf.Matrix(150 / 72, 150 / 72).prerotate(degrees)
    picture = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False)
    scanned = pymupdf.open()
    new = scanned.new_page(width=595, height=842)
    new.insert_image(new.rect, pixmap=picture)
    new.set_rotation(rotation)
    return scanned


def test_the_spanish_language_file_is_the_published_one():
    assert ocr.is_available()
    data = (ocr.tessdata_dir() / "spa.traineddata").read_bytes()
    expected = "6f2e04d02774a18f01bed44b1111f2cd7f3ba7ac9dc4373cd3f898a40ea6b464"
    assert hashlib.sha256(data).hexdigest() == expected
    assert expected in (ocr.tessdata_dir() / "LEEME.md").read_text(encoding="utf-8")


def test_scanned_pages_are_told_apart_from_pages_with_text(sample):
    def scanned(name):
        with pymupdf.open(sample(name)) as doc:
            return [looks_scanned(page) for page in list(doc)[:3]]

    assert scanned("escaneado.pdf") == [True, True, True]
    assert scanned("boe.pdf") == [False, False, False]
    assert scanned("formulario.pdf") == [False]
    assert scanned("ocr-malo.pdf") == [False, False], "it already has text, even if bad"


def test_spanish_text_is_read_with_accents_and_n_with_tilde(recognised):
    text = recognised.text
    for expected in ("Artículo 1", "solicitud", "año", "Administración pública", "jerarquía"):
        assert expected in text, f"{expected!r} was not read"
    assert "ano," not in text


def test_most_words_of_the_page_are_right(recognised, sample):
    """Compare with what the page really says (the sample is made from known text)."""
    from tests.ejemplos import generar

    truth = set()
    for number in range(1, 6):
        truth.update(generar.ARTICLE_TEXTS[number % len(generar.ARTICLE_TEXTS)].split())
    read = {word.text for word in recognised.words}
    found = sum(1 for word in truth if word in read)
    assert found / len(truth) > 0.9, f"only {found} of {len(truth)} words were read"


def test_words_come_with_their_place_on_the_page(recognised, sample):
    assert len(recognised.words) > 100
    for word in recognised.words:
        x0, y0, x1, y1 = word.rect
        assert 0 <= x0 < x1 <= 595 and 0 <= y0 < y1 <= 842
    first = recognised.words[0]
    assert first.text == "Artículo"
    assert first.rect[1] < 150, "the first word is at the top of the page"


def test_the_scan_is_recognised_at_its_own_resolution(recognised, sample):
    assert 150 <= recognised.dpi <= 160  # the sample was scanned at about 150
    with pymupdf.open(sample("boe.pdf")) as doc:
        assert ocr.best_dpi(doc[0]) == ocr.MAX_DPI  # no picture: the upper limit


@pytest.mark.parametrize("degrees", [3.0, -1.3, 0.6, 0.0])
def test_the_slant_of_the_lines_is_measured(degrees):
    with tilted_page(degrees) as doc:
        picture, _ = ocr.page_picture(doc[0])
    slant, across = ocr.measure_slant(picture)
    assert not across
    assert slant == pytest.approx(degrees, abs=0.15)


def test_a_slanted_scan_is_straightened_before_reading(recognised):
    assert recognised.turned == pytest.approx(-1.3, abs=0.15)  # the sample's first page
    # The words are on the straightened picture; on the page they are where
    # the picture shows them.
    word = recognised.words[0]
    x0, y0, x1, y1 = recognised.shown_rect(word)
    assert 60 < x0 < 80 and 70 < y0 < 90


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_a_page_upside_down_or_on_its_side_is_read_the_right_way(rotation):
    with tilted_page(0.0, rotation) as doc:
        result = recognize_page(doc[0])
    assert "Artículo 1." in result.text
    assert ocr.quality(word.text for word in result.words) > ocr.GOOD_WORDS


def test_quality_tells_words_from_rubbish():
    assert ocr.quality(["El", "camión", "de", "reparto,", "cada", "año."]) > 0.5
    assert ocr.quality(["“¡e19os", "¡euosiad", "ap", "sejp", "ononuy"]) == 0.0
    assert ocr.quality([]) == 0.0


def test_the_reader_reads_in_another_process(sample):
    with pymupdf.open(sample("escaneado.pdf")) as doc:
        picture, dpi = ocr.page_picture(doc[1])
    recognizer = Recognizer()
    try:
        recognizer.read(7, picture.width, picture.height, dpi, picture.samples)
        recognizer.read(8, 10, 10, dpi, b"too short")  # a picture that makes no sense
        first, second = wait_for(recognizer, 2)
    finally:
        recognizer.close()
    assert first.page == 7 and "Artículo 6" in first.text
    assert isinstance(second, OcrFailure) and second.page == 8


def test_the_reader_stops_at_once():
    recognizer = Recognizer()
    recognizer.close()
    assert not recognizer._process.is_alive()
    assert recognizer.results() == []
    with pytest.raises(OcrError):
        recognizer.read(0, 1, 1, 150, b"\0")


def test_missing_language_file_is_a_clear_error(sample, monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "tessdata_dir", lambda: tmp_path)
    assert not ocr.is_available()
    with pymupdf.open(sample("escaneado.pdf")) as doc, pytest.raises(OcrError):
        recognize_page(doc[0])
