"""Tests for recognising the text of scanned pages (task 0.9)."""

import hashlib
import time

import pymupdf
import pytest

from app.core import ocr
from app.core.ocr import OcrError, OcrJob, add_text_layer, looks_scanned, recognize_page
from app.core.search import find_in_page, read_page_text

WAIT_SECONDS = 120  # generous: test machines are slow and shared


@pytest.fixture(scope="module")
def recognised():
    """The first scanned sample page, recognised once for all the tests."""
    from tests.conftest import SAMPLES_DIR

    with pymupdf.open(SAMPLES_DIR / "escaneado.pdf") as doc:
        yield recognize_page(doc[0])


def wait_for(job: OcrJob):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        result = job.poll()
        if result is not None:
            return result
        time.sleep(0.05)
    job.cancel()
    raise AssertionError("timed out")


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


def test_after_adding_the_text_layer_the_search_works(sample, recognised, tmp_path):
    """The whole point: a scanned page becomes a page you can search."""
    with pymupdf.open(sample("escaneado.pdf")) as doc:
        page = doc[0]
        assert find_in_page(read_page_text(page), "articulo") == []
        before = page.get_pixmap(dpi=50).samples
        add_text_layer(page, recognised)
        assert page.get_pixmap(dpi=50).samples == before, "the page must look the same"
        doc.save(tmp_path / "con-texto.pdf")

    with pymupdf.open(tmp_path / "con-texto.pdf") as doc:
        text = read_page_text(doc[0])
        assert len(find_in_page(text, "articulo")) == 5
        assert len(find_in_page(text, "administracion publica")) == 1
        hit = find_in_page(text, "camion")[0]
        assert hit.match == "camión"
        # The mark falls on the word in the picture.
        word = next(w for w in recognised.words if w.text.startswith("camión"))
        assert abs(hit.rects[0][0] - word.rect[0]) < 3
        assert word.rect[1] - 3 <= hit.rects[0][1] <= word.rect[3]
        assert not looks_scanned(doc[0])


def test_job_recognises_in_another_process(sample):
    job = OcrJob(sample("escaneado.pdf"), 1)
    assert job.poll() is None or job.poll().page == 1  # not blocking
    result = wait_for(job)
    assert result.page == 1
    assert "Artículo 6" in result.text
    assert job.poll() is result, "asking again gives the same result"


def test_job_reports_problems(sample, tmp_path):
    for path, page in ((sample("escaneado.pdf"), 99), (tmp_path / "nada.pdf", 0)):
        job = OcrJob(path, page)
        with pytest.raises(OcrError):
            wait_for(job)
    with pytest.raises(OcrError):
        wait_for(OcrJob(sample("con-contrasena.pdf"), 0))


def test_job_can_be_cancelled(sample):
    job = OcrJob(sample("escaneado.pdf"), 0)
    job.cancel()
    assert not job._process.is_alive()
    with pytest.raises(OcrError):
        job.poll()


def test_missing_language_file_is_a_clear_error(sample, monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "tessdata_dir", lambda: tmp_path)
    assert not ocr.is_available()
    with pymupdf.open(sample("escaneado.pdf")) as doc, pytest.raises(OcrError):
        recognize_page(doc[0])
