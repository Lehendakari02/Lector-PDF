"""Tests for covering data for real: it cannot be copied or found afterwards."""

import json

import pymupdf
import pytest

from app.core.commands import CommandError, command_from_dict
from app.core.redaction import CoverData, cover_areas, cover_text

DNI = "12345678Z"


@pytest.fixture
def doc():
    document = pymupdf.open()
    for number in range(3):
        page = document.new_page(width=400, height=500)
        page.insert_text((50, 100), f"Página {number + 1}. DNI: {DNI}. Fin.")
        page.insert_text((50, 300), "Texto que se queda.")
    picture = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
    picture.clear_with(40)
    document[1].insert_image(pymupdf.Rect(50, 350, 150, 450), pixmap=picture)
    first = document[0]
    dni = first.search_for(DNI)[0]
    first.add_text_annot(dni.tl, f"Mi DNI es {DNI}")  # a note on it
    first.insert_link({"kind": pymupdf.LINK_URI, "from": dni, "uri": "https://x.es"})
    del first  # pages held here would be stale after the changes
    document.set_toc([[1, "Dos", 2]])
    yield document
    document.close()


def text_of(document) -> str:
    return "".join(page.get_text() for page in document)


def box_of(page, text) -> tuple[float, ...]:
    """Where a text is, as seen on the page (turned if the page is)."""
    rect = (page.search_for(text)[0] * page.rotation_matrix).normalize()
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def test_covered_text_is_gone_and_the_rest_stays(doc):
    order = cover_areas([(0, box_of(doc[0], DNI))]).prepared(doc)
    assert order.apply(doc) == [0]
    first = doc[0].get_text()
    assert DNI not in first
    assert "Fin." in first and "Texto que se queda." in first
    assert DNI in doc[1].get_text(), "other pages are not touched"


def test_a_black_box_is_left_where_it_was(doc):
    box = box_of(doc[0], DNI)
    cover_areas([(0, box)]).prepared(doc).apply(doc)
    middle = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    assert doc[0].get_pixmap().pixel(*map(int, middle)) == (0, 0, 0)
    assert not list(doc[0].annots(types=[pymupdf.PDF_ANNOT_REDACT]))


def test_notes_and_links_over_it_go_too(doc):
    cover_areas([(0, box_of(doc[0], DNI))]).prepared(doc).apply(doc)
    assert not list(doc[0].annots())
    assert doc[0].get_links() == []


def test_the_part_of_a_picture_under_it_is_painted_over(doc):
    cover_areas([(1, (50, 350, 100, 450))]).prepared(doc).apply(doc)
    xref = doc[1].get_images()[0][0]
    picture = pymupdf.Pixmap(doc, xref)
    left, right = picture.pixel(5, 50), picture.pixel(95, 50)
    assert left != right, "half of the picture is changed"


def test_every_place_of_a_text(doc):
    order = cover_text(DNI).prepared(doc)
    assert order.pages() == [0, 1, 2]
    order.apply(doc)
    assert DNI not in text_of(doc)
    assert text_of(doc).count("Texto que se queda.") == 3


def test_a_text_that_is_not_there(doc):
    with pytest.raises(CommandError):
        cover_text("no está").prepared(doc)


def test_undoing_brings_everything_back(doc):
    before = text_of(doc)
    order = cover_text(DNI).prepared(doc)
    order.apply(doc)
    assert order.undo(doc) == [0, 1, 2]
    assert text_of(doc) == before
    assert [annot.info["content"] for annot in doc[0].annots()] == [f"Mi DNI es {DNI}"]
    assert [link["uri"] for link in doc[0].get_links()] == ["https://x.es"]
    assert doc.get_toc() == [[1, "Dos", 2]]


def test_a_document_of_one_page_can_be_covered_and_undone(tmp_path):
    single = pymupdf.open()
    single.new_page().insert_text((50, 100), DNI)
    order = cover_text(DNI).prepared(single)
    order.apply(single)
    order.undo(single)
    assert single.page_count == 1 and DNI in single[0].get_text()


def test_a_field_over_it_leaves_the_form(doc):
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "dni"
    widget.field_value = DNI
    widget.rect = pymupdf.Rect(50, 200, 200, 220)
    doc[2].add_widget(widget)
    order = cover_areas([(2, (40, 190, 210, 230))]).prepared(doc)
    order.apply(doc)
    assert not list(doc[2].widgets())
    assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields") == ("array", "[]")
    order.undo(doc)
    assert [(w.field_name, w.field_value) for w in doc[2].widgets()] == [("dni", DNI)]


def test_after_saving_nothing_can_be_found(doc, tmp_path):
    cover_text(DNI).prepared(doc).apply(doc)
    target = tmp_path / "tapado.pdf"
    doc.save(target, garbage=4, deflate=True)
    assert DNI.encode() not in target.read_bytes()
    with pymupdf.open(target) as saved:
        assert DNI not in text_of(saved)


def test_on_a_turned_page_the_box_seen_is_covered(doc):
    doc[0].set_rotation(90)
    box = box_of(doc[0], DNI)  # as seen, turned
    cover_areas([(0, box)]).prepared(doc).apply(doc)
    assert DNI not in doc[0].get_text()
    assert "Texto que se queda." in doc[0].get_text()


def test_it_goes_through_the_journal(doc):
    order = cover_text(DNI).prepared(doc)
    read = command_from_dict(json.loads(json.dumps(order.to_dict())))
    assert isinstance(read, CoverData)
    assert read.areas == order.areas and read.copy.kept == order.copy.kept
    read.apply(doc)
    read.undo(doc)
    assert DNI in doc[2].get_text()


def test_boxes_too_thin_cover_nothing(doc):
    with pytest.raises(CommandError):
        cover_areas([(0, (50, 50, 50.5, 90))]).prepared(doc)


def test_a_signed_document_is_written_whole_after_covering(sample, tmp_path):
    from app.core.saving import keeps_signatures, write_copy

    signed = pymupdf.open(sample("firmado.pdf"))
    assert keeps_signatures(signed)
    words = signed[0].get_text().split()
    word = max(words, key=len)
    order = cover_text(word).prepared(signed)
    order.apply(signed)
    assert not keeps_signatures(signed), "the first version would still have it"
    written = write_copy(signed, tmp_path / "tapado.pdf")
    with pymupdf.open(written) as saved:
        assert word not in saved[0].get_text()
    assert word.encode("latin-1", "ignore") not in written.read_bytes()
    signed.close()
