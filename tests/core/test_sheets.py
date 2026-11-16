"""Tests for the sheets put between the pages: plain, ruled and squared."""

import pymupdf
import pytest

from app.core import sheets
from app.core.commands import CommandError, command_from_dict
from app.core.sheets import PLAIN, RULED, SHEETS, SQUARED, InsertSheet, is_sheet, new_sheet


@pytest.fixture
def doc():
    document = pymupdf.open()
    for number in range(3):
        page = document.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Página {number + 1}")
    yield document
    document.close()


def texts(document) -> list[str]:
    return [page.get_text().strip() for page in document]


@pytest.mark.parametrize("kind", SHEETS)
def test_a_sheet_goes_where_it_is_asked_and_undo_takes_it_away(doc, kind):
    order = new_sheet(1, kind, (595, 842))
    assert order.apply(doc) == [1]
    assert doc.page_count == 4
    assert texts(doc) == ["Página 1", "", "Página 2", "Página 3"]
    assert is_sheet(doc, 1) and not is_sheet(doc, 0) and not is_sheet(doc, 2)
    assert order.undo(doc) == [1]
    assert texts(doc) == ["Página 1", "Página 2", "Página 3"]


def test_it_can_go_at_the_end_and_at_the_start(doc):
    new_sheet(3).apply(doc)
    new_sheet(0).apply(doc)
    assert texts(doc) == ["", "Página 1", "Página 2", "Página 3", ""]


def test_the_sheet_takes_the_size_it_is_given(doc):
    new_sheet(1, PLAIN, (842, 595)).apply(doc)
    assert (doc[1].rect.width, doc[1].rect.height) == (842, 595)


def test_undo_finds_its_sheet_even_if_pages_moved_before_it(doc):
    first, second = new_sheet(1), new_sheet(0)
    first.apply(doc)
    second.apply(doc)  # the first sheet is now page 2
    first_place = [n for n in range(doc.page_count) if is_sheet(doc, n)]
    assert first_place == [0, 2]
    second.undo(doc)
    first.undo(doc)
    assert texts(doc) == ["Página 1", "Página 2", "Página 3"]


def test_doing_it_twice_puts_one_sheet(doc):
    order = new_sheet(1)
    order.apply(doc)
    order.apply(doc)  # redo after a recovery that already had it
    assert doc.page_count == 4


def test_undo_without_its_sheet_says_so(doc):
    with pytest.raises(CommandError):
        new_sheet(1).undo(doc)


def test_a_place_outside_the_document_is_refused(doc):
    with pytest.raises(CommandError):
        new_sheet(9).apply(doc)


def test_an_unknown_kind_becomes_a_plain_sheet():
    assert new_sheet(0, "flowers").kind == PLAIN


def test_ruled_and_squared_sheets_have_light_lines_and_plain_ones_none(doc):
    for at, kind in ((1, PLAIN), (2, RULED), (3, SQUARED)):
        new_sheet(at, kind).apply(doc)
    plain, ruled, squared = (doc[n].get_drawings() for n in (1, 2, 3))
    assert plain == []
    ruled_lines = [item for path in ruled for item in path["items"]]
    assert len(ruled_lines) > 25  # an A4 notebook page
    assert all(abs(line[1].y - line[2].y) < 0.01 for line in ruled_lines)  # all across
    assert all(path["color"] == pytest.approx(sheets.LINE_COLOR, abs=0.01) for path in ruled)
    squared_lines = [item for path in squared for item in path["items"]]
    assert len(squared_lines) > len(ruled_lines)
    assert any(abs(line[1].x - line[2].x) < 0.01 for line in squared_lines)  # some down


def test_the_lines_are_part_of_the_page_not_annotations(doc):
    new_sheet(1, SQUARED).apply(doc)
    assert list(doc[1].annots()) == []


def test_it_is_written_down_and_read_back(doc):
    order = new_sheet(2, RULED, (500, 700))
    again = command_from_dict(order.to_dict())
    assert again == order
    assert isinstance(again, InsertSheet)


def test_a_damaged_size_gives_a_page_that_can_be_used():
    assert sheets.clamp_size(None) == (595.0, 842.0)
    assert sheets.clamp_size((0, 10)) == (595.0, 842.0)
    assert sheets.clamp_size((5, 99999)) == (72.0, 14400.0)


def test_the_last_page_cannot_be_taken_away():
    document = pymupdf.open()
    order = new_sheet(0)
    order.apply(document)
    with pytest.raises(CommandError):
        order.undo(document)
    document.close()


def test_saved_it_is_still_there_and_any_reader_sees_it(doc, tmp_path):
    new_sheet(1, RULED).apply(doc)
    path = tmp_path / "con-hoja.pdf"
    doc.save(path)
    with pymupdf.open(path) as saved:
        assert saved.page_count == 4
        assert is_sheet(saved, 1)
        assert len(saved[1].get_drawings()) == 1
