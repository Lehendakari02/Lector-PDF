"""Tests for taking pages out as pictures and the text out as a text file."""

import pymupdf
import pytest

from app.core.combine import NeedsPassword, Source
from app.core.export import (
    JPEG,
    PNG,
    ExportError,
    export_images,
    export_text,
    image_names,
    page_heading,
)


@pytest.fixture
def document(tmp_path):
    doc = pymupdf.open()
    for number in range(3):
        page = doc.new_page(width=200, height=300)
        page.insert_text((20, 40), f"Página de prueba {number + 1}")
    page = doc[1]
    page.insert_text((20, 80), "Una palabra par-")
    page.insert_text((20, 95), "tida al final.")
    note = page.add_rect_annot(pymupdf.Rect(10, 150, 190, 290))
    note.set_colors(fill=(1, 0, 0))
    note.update()
    doc.new_page(width=200, height=300)  # a page with no text: a scan not read yet
    path = tmp_path / "apuntes.pdf"
    doc.save(path)
    doc.close()
    return path


def test_names_of_the_pictures_sort_in_order():
    assert image_names("Tema 5", [0, 9], 12, PNG) == [
        "Tema 5 - página 01.png",
        "Tema 5 - página 10.png",
    ]
    assert image_names('a:b"c', [2], 3, JPEG) == ["a b c - página 3.jpg"]


def test_pages_as_png_at_the_resolution_asked(document, tmp_path):
    targets = [tmp_path / name for name in image_names("apuntes", [0, 1], 4, PNG)]
    written = export_images(Source(document), [0, 1], targets, PNG, 144)
    assert written == targets
    picture = pymupdf.Pixmap(written[0])
    assert (picture.width, picture.height) == (400, 600), "twice 72 ppp"
    assert picture.xres == 144


def test_with_and_without_the_notes(document, tmp_path):
    with_notes = export_images(Source(document), [1], [tmp_path / "con.png"])[0]
    without = export_images(Source(document), [1], [tmp_path / "sin.png"], annotations=False)[0]
    inside = (round(100 * 150 / 72), round(220 * 150 / 72))  # in the box, at 150 ppp
    red = pymupdf.Pixmap(with_notes).pixel(*inside)
    plain = pymupdf.Pixmap(without).pixel(*inside)
    assert red[0] > 200 and red[1] < 80, "the red box is drawn"
    assert plain == (255, 255, 255)


def test_jpeg_pictures(document, tmp_path):
    written = export_images(Source(document), [2], [tmp_path / "p.jpg"], JPEG)
    assert written[0].read_bytes()[:2] == b"\xff\xd8"


def test_nothing_is_written_over(document, tmp_path):
    taken = tmp_path / "p.png"
    taken.write_text("mío")
    written = export_images(Source(document), [0], [taken])
    assert written == [tmp_path / "p (2).png"]
    assert taken.read_text() == "mío"
    assert not list(tmp_path.glob(".*.tmp"))


def test_stopping_halfway(document, tmp_path):
    targets = [tmp_path / f"{n}.png" for n in range(3)]
    with pytest.raises(ExportError):
        export_images(Source(document), [0, 1, 2], targets, progress=lambda done, total: done < 1)
    assert [path.exists() for path in targets] == [True, False, False]


def test_the_text_of_the_document(document, tmp_path):
    target, empty = export_text(Source(document), [0, 1, 2, 3], tmp_path / "apuntes.txt")
    text = target.read_text(encoding="utf-8")
    assert text.startswith(page_heading(0) + "\n\nPágina de prueba 1")
    assert "partida al final." in text, "a word cut at the end of a line is joined"
    assert page_heading(3) in text
    assert empty == [3], "the page with no text is said"


def test_the_text_of_one_page_has_no_heading(document, tmp_path):
    target, empty = export_text(Source(document), [2], tmp_path / "una.txt")
    assert target.read_text(encoding="utf-8") == "Página de prueba 3\n"
    assert empty == []


def test_a_locked_document_needs_its_password(sample, tmp_path):
    locked = sample("con-contrasena.pdf")
    with pytest.raises(NeedsPassword):
        export_text(Source(locked), [0], tmp_path / "t.txt")
    target, _empty = export_text(Source(locked, "lector"), [0], tmp_path / "t.txt")
    assert target.exists()
