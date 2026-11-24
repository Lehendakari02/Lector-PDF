"""Tests for following the drawing orders of a page, to put new text in its
place among them (task 6.1)."""

import pymupdf
import pytest

from app.core import pdf_content
from app.core.pdf_content import ContentError, insertion_point, splice, tokens


def ops(data: bytes) -> list[bytes]:
    return [value for _s, _e, kind, value in tokens(data) if kind == "op"]


def test_strings_arrays_and_pictures_are_read_whole():
    data = (
        b"BT /F1 12 Tf (un (par) \\) de) Tj [(a) -20 <0041>] TJ ET "
        b"BI /W 2 /H 1 /BPC 8 /CS /G ID \x00EI\xff EI Q % a note\n q"
    )
    assert ops(data) == [b"BT", b"Tf", b"Tj", b"TJ", b"ET", b"BI", b"Q", b"q"]


def test_damaged_content_says_so():
    with pytest.raises(ContentError):
        list(tokens(b"BT (sin final Tj ET"))


def test_the_place_is_before_the_next_line_of_the_same_text_object():
    data = b"q 1 0 0 1 10 20 cm BT /F1 10 Tf 50 700 Td (uno) Tj 0 -12 Td (dos) Tj ET Q"
    place = insertion_point(data, (60.0, 720.0))  # "uno" starts at 50+10, 700+20
    assert place.in_text
    assert data[place.at :].startswith(b"0 -12 Td")
    assert place.ctm == (1, 0, 0, 1, 10, 20)
    assert place.line_matrix == (1, 0, 0, 1, 50, 700)


def test_without_a_next_line_it_goes_after_the_text_object():
    data = b"BT /F1 10 Tf 50 700 Td (uno) Tj ET 0 g"
    place = insertion_point(data, (50.0, 700.0))
    assert not place.in_text
    assert data[: place.at].endswith(b"ET")


def test_text_not_in_the_page_content_is_not_found():
    with pytest.raises(ContentError):
        insertion_point(b"BT /F1 10 Tf 50 700 Td (uno) Tj ET", (300.0, 100.0))


def test_spliced_content_draws_the_rest_the_same():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), "primera", fontsize=12)
    page.insert_text((50, 120), "segunda", fontsize=12)
    page.clean_contents()  # one content stream
    before = page.get_text()
    data = page.read_contents()
    place = insertion_point(data, (50.0, page.mediabox.y1 - 100))
    font = "helv"
    new = f"BT /{font} 12 Tf 1 0 0 1 300 600 Tm (nueva) Tj ET\n".encode()
    joined = splice(data, place, new)
    xref = page.get_contents()[0]
    doc.update_stream(xref, joined)
    words = [word[4] for word in doc[0].get_text("words", sort=False)]
    assert words == ["primera", "nueva", "segunda"], "read right after the text before"
    assert "primera" in before


def test_matrices():
    matrix = (2.0, 0.0, 0.0, -1.0, 10.0, 800.0)
    assert pdf_content.multiply(matrix, pdf_content.inverse(matrix)) == pytest.approx(
        pdf_content.IDENTITY
    )
