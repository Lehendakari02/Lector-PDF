"""Tests for writing the recognised text on a page as invisible text: the
page looks the same, the words are found where the picture shows them, and
Deshacer takes exactly that away."""

import math

import pymupdf
import pytest

from app.core.commands import CommandError, command_from_dict
from app.core.ocr import OcrPage, OcrWord
from app.core.search import find_in_page, read_page_text
from app.core.text_layer import LAYER_KEY, AddTextLayer, PageLayer, has_layer

WORDS = (
    OcrWord((72, 100, 130, 114), "Artículo"),
    OcrWord((134, 100, 146, 114), "14."),
    OcrWord((72, 120, 112, 134), "camión"),
    OcrWord((116, 120, 140, 134), "año"),
    OcrWord((144, 120, 200, 134), "(¿qué?)"),
    OcrWord((204, 120, 240, 134), "π≠3"),  # letters Helvetica does not have
)


def scanned_doc(rotation: int = 0) -> pymupdf.Document:
    """A page that is only a picture (here, a grey square)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    picture = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
    picture.set_rect(picture.irect, (200,))
    page.insert_image(page.rect, pixmap=picture)
    page.set_rotation(rotation)
    return doc


def order_for(page: int = 0, matrix=(1, 0, 0, 1, 0, 0), words=WORDS) -> AddTextLayer:
    return AddTextLayer((PageLayer.of(OcrPage(page, words, matrix)),))


def hit(doc, word: str, number: int = 0):
    """Where a word is found, on the page as it is shown."""
    page = doc[number]
    found = find_in_page(read_page_text(page), word)
    assert found, f"{word!r} not found"
    rect = pymupdf.Rect(found[0].rects[0]) * page.rotation_matrix
    return rect


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_the_words_are_found_where_the_picture_shows_them(rotation):
    with scanned_doc(rotation) as doc:
        before = doc[0].get_pixmap(dpi=40).samples
        order_for().apply(doc)
        assert doc[0].get_pixmap(dpi=40).samples == before, "the page looks the same"
        rect = hit(doc, "camion")
        assert rect.x0 == pytest.approx(72, abs=1) and rect.x1 == pytest.approx(112, abs=1)
        assert rect.y0 == pytest.approx(120, abs=1) and rect.y1 == pytest.approx(134, abs=1)
        assert hit(doc, "año").x0 == pytest.approx(116, abs=1)
        assert not find_in_page(read_page_text(doc[0]), "ano"), "ñ is not an n"


def test_spanish_letters_and_marks_are_kept_and_others_are_a_question_mark():
    with scanned_doc() as doc:
        order_for().apply(doc)
        text = doc[0].get_text()
    assert "Artículo 14." in text
    assert "camión año (¿qué?)" in text
    assert "?≠" not in text and "??3" in text


def test_words_of_a_straightened_picture_are_written_level_over_it():
    """Some readers break slanted lines, even inside a word: they go level."""
    turn = pymupdf.Matrix(3)  # the picture was turned 3 degrees to read it
    with scanned_doc() as doc:
        order_for(matrix=tuple(turn)).apply(doc)
        rect = hit(doc, "camion")
        covered = (pymupdf.Rect(72, 120, 112, 134).quad * turn).rect
        assert rect.x0 == pytest.approx(covered.x0, abs=1)
        assert rect.y0 == pytest.approx(covered.y0, abs=1)
        assert rect.y1 == pytest.approx(covered.y1, abs=1)
        blocks = doc[0].get_text("dict")["blocks"]
        line = next(block for block in blocks if block.get("lines"))["lines"][0]
        assert line["dir"] == pytest.approx((1, 0))


@pytest.mark.parametrize("quarter", [90, 180, 270])
def test_words_of_a_page_read_on_its_side_go_its_way(quarter):
    with scanned_doc() as doc:
        centre = pymupdf.Matrix(1, 0, 0, 1, -297.5, -421)
        turn = centre * pymupdf.Matrix(quarter + 1) * ~centre  # about the middle of the page
        order_for(matrix=tuple(turn)).apply(doc)
        blocks = doc[0].get_text("dict")["blocks"]
        dx, dy = next(block for block in blocks if block.get("lines"))["lines"][0]["dir"]
        assert math.degrees(math.atan2(dy, dx)) % 360 == pytest.approx(quarter, abs=0.5)
        assert "camión" in doc[0].get_text()


def test_undo_takes_away_exactly_what_was_written():
    with scanned_doc() as doc:
        contents = doc.xref_get_key(doc[0].xref, "Contents")
        order = order_for()
        assert order.apply(doc) == [0]
        assert has_layer(doc, 0)
        assert order.undo(doc) == [0]
        assert not has_layer(doc, 0)
        assert doc[0].get_text().strip() == ""
        listed = doc.xref_get_key(doc[0].xref, "Contents")[1]
        assert contents[1].strip("[]").split()[0] in listed  # the picture is still there
        assert doc.xref_get_key(doc[0].xref, LAYER_KEY)[0] == "null"


def test_written_twice_or_taken_away_twice_says_so():
    with scanned_doc() as doc:
        order = order_for()
        order.apply(doc)
        with pytest.raises(CommandError):
            order.apply(doc)
        order.undo(doc)
        with pytest.raises(CommandError):
            order.undo(doc)
        with pytest.raises(CommandError):
            order_for(page=3).apply(doc)


def test_saved_reopened_and_undone(tmp_path):
    path = tmp_path / "con-texto.pdf"
    order = order_for()
    with scanned_doc() as doc:
        order.apply(doc)
        doc.save(path, garbage=0, deflate=True)  # as the program saves
    with pymupdf.open(path) as saved:
        assert hit(saved, "articulo")
        order.undo(saved)
        assert saved[0].get_text().strip() == ""


def test_it_is_written_in_the_journal_and_read_back():
    order = order_for()
    again = command_from_dict(order.to_dict())
    assert again == order
    assert again.text_change


def test_pages_with_their_resources_kept_apart_or_in_the_page_tree():
    with scanned_doc() as doc:
        page_xref = doc[0].xref
        resources = doc.xref_get_key(page_xref, "Resources")
        holder = doc.get_new_xref()
        doc.update_object(holder, resources[1] if resources[0] == "dict" else "<<>>")
        doc.xref_set_key(page_xref, "Resources", f"{holder} 0 R")
        order_for().apply(doc)
        assert hit(doc, "camion")
        assert doc[0].get_pixmap(dpi=20)  # the picture is still drawn
    with scanned_doc() as doc:
        page_xref = doc[0].xref
        resources = doc.xref_get_key(page_xref, "Resources")[1]
        parent = int(doc.xref_get_key(page_xref, "Parent")[1].split()[0])
        doc.xref_set_key(parent, "Resources", resources)
        doc.xref_set_key(page_xref, "Resources", "null")
        before = doc[0].get_pixmap(dpi=20).samples
        order_for().apply(doc)
        assert hit(doc, "camion")
        assert doc[0].get_pixmap(dpi=20).samples == before, "the picture is still there"


def test_a_page_with_nothing_on_it_gets_its_text_too():
    with pymupdf.open() as doc:
        doc.new_page()
        order_for().apply(doc)
        assert hit(doc, "camion")
        order_for().undo(doc)
        assert doc[0].get_text().strip() == ""


def bad_ocr_text(doc, number=0) -> str:
    return doc[number].get_text()


def test_recognising_again_takes_away_the_bad_text_and_undo_brings_it_back(sample):
    with pymupdf.open(sample("ocr-malo.pdf")) as doc:
        before_text = bad_ocr_text(doc)
        before_picture = doc[0].get_pixmap(dpi=40).samples
        assert "Articu1o" in before_text
        order = AddTextLayer(order_for().layers, replace=True)
        order.apply(doc)
        text = doc[0].get_text()
        assert "Articu1o" not in text and "camión" in text
        assert doc[0].get_pixmap(dpi=40).samples == before_picture, "it looks the same"
        order.undo(doc)
        assert bad_ocr_text(doc) == before_text
        assert not has_layer(doc, 0)
        order.apply(doc)  # Rehacer
        assert "Articu1o" not in doc[0].get_text()


def test_recognising_our_own_text_again_twice_and_undoing_both(tmp_path):
    with scanned_doc() as doc:
        first = order_for()
        first.apply(doc)
        second = AddTextLayer(order_for(words=WORDS[:2]).layers, replace=True)
        third = AddTextLayer(order_for(words=WORDS[2:4]).layers, replace=True)
        second.apply(doc)
        assert "camión" not in doc[0].get_text()
        third.apply(doc)
        assert "Artículo" not in doc[0].get_text() and "camión" in doc[0].get_text()
        path = tmp_path / "otra-vez.pdf"
        doc.save(path, garbage=0, deflate=True)
    with pymupdf.open(path) as saved:
        third.undo(saved)
        assert saved[0].get_text().split() == ["Artículo", "14."]
        second.undo(saved)
        assert "camión año" in saved[0].get_text()
        first.undo(saved)
        assert saved[0].get_text().strip() == ""


def test_visible_text_stays_when_recognising_again():
    with scanned_doc() as doc:
        doc[0].insert_text((300, 700), "Sello visible", fontsize=12)
        doc[0].insert_text((72, 110), "Oculto", fontsize=12, render_mode=3)
        AddTextLayer(order_for(words=WORDS[2:3]).layers, replace=True).apply(doc)
        text = doc[0].get_text()
    assert "Sello visible" in text and "Oculto" not in text and "camión" in text


def test_replace_is_written_in_the_journal():
    order = AddTextLayer(order_for().layers, replace=True)
    assert command_from_dict(order.to_dict()) == order
