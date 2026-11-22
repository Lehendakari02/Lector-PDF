"""Tests for blank margins added to pages to write notes in."""

import pymupdf
import pytest

from app.core.commands import command_from_dict
from app.core.margins import AddMargin, cm, size_change, unturned
from app.core.notes import Remove, new_note


def ink_box(pixmap):
    xs, ys = [], []
    samples, n, width = pixmap.samples, pixmap.n, pixmap.width
    for index in range(0, len(samples), n):
        if samples[index] < 100:
            point = index // n
            xs.append(point % width)
            ys.append(point // width)
    return min(xs), min(ys), max(xs), max(ys)


def page_with_word(turn=0):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((150, 300), "Hola", fontsize=20)
    page.set_rotation(turn)
    return doc


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_the_page_grows_on_the_side_asked_and_the_content_stays(turn):
    doc = page_with_word(turn)
    width, height = doc[0].rect.width, doc[0].rect.height
    before = ink_box(doc[0].get_pixmap())
    order = AddMargin((0,), 50.0, 100.0, 70.0, "m")
    order.apply(doc)
    assert doc[0].rect.width == pytest.approx(width + 150)
    assert doc[0].rect.height == pytest.approx(height + 70)
    after = ink_box(doc[0].get_pixmap())
    # Room on the left moves it right on the page as shown; below, nothing.
    assert after[0] == before[0] + 50 and after[1] == before[1]
    order.undo(doc)
    assert (doc[0].rect.width, doc[0].rect.height) == (width, height)
    assert ink_box(doc[0].get_pixmap()) == before


def test_a_note_stays_on_its_word(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        word = doc[4].search_for("Artículo 14.")[0]
        new_note(4, (word.x1 + 2, word.y0), "Ojo").apply(doc)
        page = doc[4]  # kept: an annotation of a page let go crashes PyMuPDF
        note = page.first_annot.rect
        AddMargin((4,), cm(5), 0.0, 0.0, "m").apply(doc)
        page = doc[4]
        moved_word = page.search_for("Artículo 14.")[0]
        moved_note = page.first_annot.rect
        assert moved_word.x0 - word.x0 == pytest.approx(cm(5), abs=0.1)
        assert moved_note.x0 - note.x0 == pytest.approx(cm(5), abs=0.1)


def test_every_page_or_one(sample):
    with pymupdf.open(sample("largo.pdf")) as doc:
        widths = [page.rect.width for page in doc]
        AddMargin(tuple(range(doc.page_count)), 0.0, cm(3), 0.0, "all").apply(doc)
        assert [page.rect.width for page in doc] == pytest.approx([w + cm(3) for w in widths])


def test_twice_is_once_and_remove_takes_it_away():
    doc = page_with_word()
    order = AddMargin((0,), 0.0, 100.0, 0.0, "m")
    order.apply(doc)
    order.apply(doc)  # recovered from the journal after it was saved
    assert doc[0].rect.width == 500
    Remove(order).apply(doc)
    assert doc[0].rect.width == 400
    assert size_change(Remove(order)) == {0: (-100.0, 0.0)}
    assert size_change(order, undone=True) == {0: (-100.0, -0.0)}


def test_a_page_that_would_be_too_big_is_refused():
    doc = pymupdf.open()
    doc.new_page(width=14000, height=600)
    with pytest.raises(Exception, match="too big"):
        AddMargin((0,), 0.0, 1000.0, 0.0, "m").apply(doc)
    assert doc[0].rect.width == 14000


def test_it_is_saved_as_standard_page_boxes(tmp_path):
    doc = page_with_word()
    AddMargin((0,), 0.0, 100.0, 50.0, "m").apply(doc)
    path = tmp_path / "con-margen.pdf"
    doc.save(path, garbage=1)
    with pymupdf.open(path) as saved:
        assert (saved[0].rect.width, saved[0].rect.height) == (500, 650)


def test_sides_of_a_turned_page():
    assert unturned(0, (1, 2, 3, 4)) == (1, 2, 3, 4)
    assert unturned(90, (1, 2, 3, 4)) == (2, 3, 4, 1)


def test_it_is_written_and_read_back_for_the_journal():
    order = AddMargin((0, 3), 10.0, 0.0, 5.5, "m")
    assert command_from_dict(order.to_dict()) == order
