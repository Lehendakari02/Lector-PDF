"""Tests for the user's bookmarks, kept in the outline of the PDF."""

import pymupdf
import pytest

from app.core.bookmarks import GROUP_TITLE, AddBookmark, changes_outline
from app.core.commands import command_from_dict
from app.core.notes import Remove, Replace
from app.core.outline import read_outline


def mine(doc):
    return [(e.title, e.page) for e in read_outline(doc) if e.bookmark]


def test_bookmarks_go_first_under_their_own_item_and_the_index_stays(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        before = doc.get_toc()
        AddBookmark(4, 300.0, "Artículo 14", "b1").apply(doc)
        AddBookmark(2, 100.0, "Título preliminar", "b2").apply(doc)
        outline = read_outline(doc)
        assert outline[0].group and outline[0].title == GROUP_TITLE
        # In the order of the document, not in the order they were put.
        assert mine(doc) == [("Título preliminar", 2), ("Artículo 14", 4)]
        assert [e.level for e in outline[:3]] == [1, 2, 2]
        assert doc.get_toc()[3:] == before, "the document's own index is untouched"


def test_undo_takes_it_away_and_the_last_one_takes_the_group(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        before = doc.get_toc()
        first = AddBookmark(4, 300.0, "Uno", "b1")
        second = AddBookmark(6, 0.0, "Dos", "b2")
        first.apply(doc)
        second.apply(doc)
        first.undo(doc)
        assert mine(doc) == [("Dos", 6)]
        second.undo(doc)
        assert doc.get_toc() == before


def test_rename_and_remove_are_the_usual_orders():
    doc = pymupdf.open()
    doc.new_page()
    order = AddBookmark(0, 50.0, "Uno", "x")
    order.apply(doc)
    renamed = Replace(order, AddBookmark(0, 50.0, "Importante", "x"))
    renamed.apply(doc)
    assert mine(doc) == [("Importante", 0)]
    renamed.undo(doc)
    assert mine(doc) == [("Uno", 0)]
    gone = Remove(order)
    gone.apply(doc)
    assert doc.get_toc() == []
    gone.undo(doc)
    assert mine(doc) == [("Uno", 0)]
    assert changes_outline(order) and changes_outline(renamed) and changes_outline(gone)


def test_applying_twice_puts_only_one():
    doc = pymupdf.open()
    doc.new_page()
    order = AddBookmark(0, 0.0, "Uno", "x")
    order.apply(doc)
    order.apply(doc)  # recovered from the journal after it was saved
    assert len(mine(doc)) == 1


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_it_leads_to_the_very_place_also_on_a_turned_page(turn):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.set_rotation(turn)
    AddBookmark(0, 123.0, "Aquí", "x").apply(doc)
    (entry,) = [e for e in read_outline(doc) if e.bookmark]
    assert entry.top == pytest.approx(123.0, abs=0.5)


def test_it_is_saved_as_a_standard_bookmark(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    AddBookmark(1, 200.0, "Artículo 14. Igualdad", "x").apply(doc)
    path = tmp_path / "con-marcador.pdf"
    doc.save(path, garbage=1)
    with pymupdf.open(path) as saved:
        assert saved.get_toc() == [[1, GROUP_TITLE, -1], [2, "Artículo 14. Igualdad", 2]]


def test_it_is_written_and_read_back_for_the_journal():
    order = AddBookmark(3, 12.5, "Tema 5", "x", "Mis marcadores")
    assert command_from_dict(order.to_dict()) == order
