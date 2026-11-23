"""Tests for turning, moving and taking away pages."""

import json

import pymupdf
import pytest

from app.core.commands import CommandError, command_from_dict
from app.core.page_orders import (
    DeletePages,
    InsertPages,
    MovePages,
    RotatePages,
    SourceNeedsPassword,
    delete_pages,
    insert_pages,
    move_pages,
    moved_order,
    rotate_pages,
)


@pytest.fixture
def doc():
    document = pymupdf.open()
    for number in range(5):
        width, height = (595, 842) if number != 1 else (842, 595)
        page = document.new_page(width=width, height=height)
        page.insert_text((72, 72), f"P{number + 1}")
        note = page.add_text_annot((100, 100), f"nota {number + 1}")
        document.xref_set_key(note.xref, "NM", f"(n{number + 1})")
    yield document
    document.close()


def texts(document) -> list[str]:
    return [page.get_text().strip().split("\n")[0] for page in document]


def sizes(document) -> list[tuple[float, float]]:
    return [(page.rect.width, page.rect.height) for page in document]


def journal_round_trip(order):
    return command_from_dict(json.loads(json.dumps(order.to_dict())))


# ---- turning ----------------------------------------------------------------


def test_turning_pages_and_undoing_it(doc):
    order = rotate_pages([3, 0], 90)
    assert order.pages_ == (0, 3)
    assert order.apply(doc) == [0, 3]
    assert [page.rotation for page in doc] == [90, 0, 0, 90, 0]
    order.apply(doc)
    assert doc[0].rotation == 180
    order.undo(doc)
    order.undo(doc)
    assert [page.rotation for page in doc] == [0] * 5


def test_turning_left_is_turning_three_quarters(doc):
    order = rotate_pages([2], -90)
    assert order.by == 270
    order.apply(doc)
    assert doc[2].rotation == 270


def test_the_layout_of_a_turn_swaps_the_sides_of_those_pages(doc):
    before = sizes(doc)
    order = rotate_pages([1], 90)
    mapping, after = order.layout(before, False)
    order.apply(doc)
    assert mapping == [0, 1, 2, 3, 4]
    assert after == sizes(doc)
    assert order.layout(before, False)[1][0] == before[0]
    assert rotate_pages([1], 180).layout(before, False)[1] == before


def test_a_page_that_is_not_there_cannot_be_turned(doc):
    with pytest.raises(CommandError):
        rotate_pages([7], 90).apply(doc)


def test_turning_goes_through_the_journal(doc):
    order = journal_round_trip(rotate_pages([1, 2], 270))
    assert order == RotatePages((1, 2), 270)


# ---- moving -----------------------------------------------------------------


def test_the_new_order_of_moved_pages():
    assert moved_order(5, [3], 0) == [3, 0, 1, 2, 4]
    assert moved_order(5, [0], 5) == [1, 2, 3, 4, 0]
    assert moved_order(5, [0, 2], 4) == [1, 3, 0, 2, 4]
    assert moved_order(5, [1, 2], 2) == [0, 1, 2, 3, 4]  # where they already are


@pytest.mark.parametrize(
    ("pages", "to", "expected"),
    [
        ([3], 0, ["P4", "P1", "P2", "P3", "P5"]),
        ([0], 5, ["P2", "P3", "P4", "P5", "P1"]),
        ([0, 4], 2, ["P2", "P1", "P5", "P3", "P4"]),
    ],
)
def test_moving_pages_and_undoing_it(doc, pages, to, expected):
    before = texts(doc)
    order = move_pages(pages, to)
    order.apply(doc)
    assert texts(doc) == expected
    order.undo(doc)
    assert texts(doc) == before


def test_what_is_written_on_a_page_moves_with_it(doc):
    move_pages([4], 0).apply(doc)
    assert [annot.info["content"] for annot in doc[0].annots()] == ["nota 5"]


def test_the_layout_of_a_move_follows_the_pages(doc):
    before = sizes(doc)
    order = move_pages([1], 4)
    mapping, after = order.layout(before, False)
    order.apply(doc)
    assert after == sizes(doc)
    assert mapping == [0, 3, 1, 2, 4]
    back, again = order.layout(after, True)
    order.undo(doc)
    assert again == sizes(doc) == before
    assert back == [0, 2, 3, 1, 4]
    assert order.first_after(5) == 3


def test_links_and_outline_follow_moved_pages(doc):
    doc[0].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(0, 0, 50, 50), "page": 3})
    doc.set_toc([[1, "Cuatro", 4]])
    move_pages([3], 0).apply(doc)
    assert doc.get_toc() == [[1, "Cuatro", 1]]
    assert [link["page"] for link in doc[1].get_links()] == [0]


def test_any_new_order_is_reached_moving_few_pages(doc):
    import itertools

    from app.core.page_orders import _rearrange, _staying

    first = texts(doc)
    assert _staying([3, 0, 1, 2, 4]) == {0, 1, 2, 4}, "only page 4 has to move"
    for order in itertools.permutations(range(5)):
        _rearrange(doc, list(order))
        assert texts(doc) == [first[old] for old in order]
        back = [0] * 5
        for place, old in enumerate(order):
            back[old] = place
        _rearrange(doc, back)
        assert texts(doc) == first


def test_moving_pages_of_a_document_with_a_structure_tree(sample):
    # MuPDF's own rearranging reads freed memory with these (the BOE has one).
    with pymupdf.open(sample("boe.pdf")) as boe:
        first = [page.get_text()[:80] for page in boe]
        order = move_pages([0], boe.page_count)
        order.apply(boe)
        assert [page.get_text()[:80] for page in boe] == first[1:] + first[:1]
        order.undo(boe)
        assert [page.get_text()[:80] for page in boe] == first


def test_moving_goes_through_the_journal(doc):
    assert journal_round_trip(move_pages([2, 0], 4)) == MovePages((0, 2), 4)


# ---- taking away ------------------------------------------------------------


def test_taking_pages_away_and_putting_them_back(doc):
    before_sizes = sizes(doc)
    order = delete_pages([1, 3]).prepared(doc)
    assert order.kept and order.sizes == (before_sizes[1], before_sizes[3])
    order.apply(doc)
    assert texts(doc) == ["P1", "P3", "P5"]
    order.undo(doc)
    assert texts(doc) == ["P1", "P2", "P3", "P4", "P5"]
    assert sizes(doc) == before_sizes
    assert [annot.info["content"] for annot in doc[3].annots()] == ["nota 4"]


def test_the_layout_of_taking_pages_away(doc):
    before = sizes(doc)
    order = delete_pages([0, 1]).prepared(doc)
    mapping, after = order.layout(before, False)
    assert mapping == [None, None, 0, 1, 2]
    assert after == before[2:]
    back, again = order.layout(after, True)
    assert back == [2, 3, 4]
    assert again == before


def test_every_page_cannot_be_taken_away(doc):
    with pytest.raises(CommandError):
        delete_pages(range(5)).prepared(doc)
    with pytest.raises(CommandError):
        delete_pages(range(5)).apply(doc)


def test_without_a_copy_it_cannot_be_undone(doc):
    order = delete_pages([2])
    order.apply(doc)
    with pytest.raises(CommandError):
        order.undo(doc)


def test_links_to_the_pages_and_outline_come_back(doc):
    doc[0].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(0, 0, 50, 50), "page": 2})
    doc[2].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(0, 0, 50, 50), "page": 4})
    doc.set_toc([[1, "Uno", 1], [1, "Tres", 3], [2, "Dentro", 3], [1, "Cinco", 5]])
    order = delete_pages([2]).prepared(doc)
    order.apply(doc)
    assert doc[0].get_links() == []
    order.undo(doc)
    assert [link["page"] for link in doc[0].get_links()] == [2]
    assert [link["page"] for link in doc[2].get_links()] == [4]
    assert doc.get_toc() == [[1, "Uno", 1], [1, "Tres", 3], [2, "Dentro", 3], [1, "Cinco", 5]]


def test_form_fields_come_back_with_their_names(doc):
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "nombre"
    widget.rect = pymupdf.Rect(200, 200, 300, 220)
    widget.field_value = "Ana"
    doc[2].add_widget(widget)
    order = delete_pages([2]).prepared(doc)
    order.apply(doc)
    order.undo(doc)
    found = [(widget.field_name, widget.field_value) for widget in doc[2].widgets()]
    assert found == [("nombre", "Ana")]


def test_taking_away_goes_through_the_journal_with_its_copy(doc):
    doc.set_toc([[1, "Dos", 2]])
    doc[1].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(0, 0, 50, 50), "page": 0})
    order = delete_pages([1]).prepared(doc)
    read = journal_round_trip(order)
    assert isinstance(read, DeletePages)
    assert read.kept == order.kept and read.sizes == order.sizes
    read.apply(doc)
    read.undo(doc)
    assert texts(doc)[1] == "P2"
    assert doc.get_toc() == [[1, "Dos", 2]]
    assert [link["page"] for link in doc[1].get_links()] == [0]


def test_after_saving_the_pages_still_come_back(doc, tmp_path):
    order = delete_pages([4]).prepared(doc)
    order.apply(doc)
    target = tmp_path / "guardado.pdf"
    doc.save(target, garbage=3)
    with pymupdf.open(target) as saved:
        order.undo(saved)
        assert texts(saved) == ["P1", "P2", "P3", "P4", "P5"]


def test_the_fields_of_pages_taken_away_leave_the_form(doc):
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "nombre"
    widget.rect = pymupdf.Rect(200, 200, 300, 220)
    doc[2].add_widget(widget)
    order = delete_pages([2]).prepared(doc)
    order.apply(doc)
    assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields") == ("array", "[]")
    order.undo(doc)
    kind, fields = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")
    assert len(fields.strip("[] ").split()) == 3


# ---- putting pages in -------------------------------------------------------


def make_pdf(path, name, count, size=(595, 842)):
    other = pymupdf.open()
    for number in range(count):
        page = other.new_page(width=size[0], height=size[1])
        page.insert_text((72, 72), f"{name}{number + 1}")
    other.save(path)
    other.close()
    return path


def test_pages_of_another_pdf_go_where_asked_and_undo_takes_them(doc, tmp_path):
    other = make_pdf(tmp_path / "otro.pdf", "X", 2, (300, 400))
    order = insert_pages(1, [other])
    assert order.sizes == ((300.0, 400.0), (300.0, 400.0))
    order.apply(doc)
    assert texts(doc) == ["P1", "X1", "X2", "P2", "P3", "P4", "P5"]
    order.undo(doc)
    assert texts(doc) == ["P1", "P2", "P3", "P4", "P5"]


def test_only_some_pages_and_at_the_end(doc, tmp_path):
    other = make_pdf(tmp_path / "otro.pdf", "X", 4)
    insert_pages(5, [(other, None, [3, 1])]).apply(doc)
    assert texts(doc)[5:] == ["X4", "X2"]


def test_a_picture_is_a_page_the_size_of_a_sheet(doc, tmp_path):
    picture = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 200), False)
    picture.clear_with(200)
    path = tmp_path / "foto.png"
    picture.save(path)
    order = insert_pages(0, [path])
    assert order.sizes == ((842.0, 595.0),), "wider than tall: a sheet on its side"
    order.apply(doc)
    assert doc[0].get_images()
    assert doc.page_count == 6


def test_a_pdf_with_a_password_needs_it(doc, sample):
    locked = sample("con-contrasena.pdf")
    with pytest.raises(SourceNeedsPassword):
        insert_pages(0, [locked])
    assert insert_pages(0, [(locked, "lector")]).sizes


def test_the_layout_of_pages_put_in(doc, tmp_path):
    other = make_pdf(tmp_path / "otro.pdf", "X", 2, (300, 400))
    order = insert_pages(2, [other])
    before = sizes(doc)
    mapping, after = order.layout(before, False)
    order.apply(doc)
    assert after == sizes(doc)
    assert mapping == [0, 1, 4, 5, 6]
    back, again = order.layout(after, True)
    assert back == [0, 1, None, None, 2, 3, 4]
    assert again == before


def test_putting_pages_goes_through_the_journal(doc, tmp_path):
    other = make_pdf(tmp_path / "otro.pdf", "X", 1)
    read = journal_round_trip(insert_pages(0, [other]))
    assert isinstance(read, InsertPages)
    read.apply(doc)
    assert texts(doc)[0] == "X1"
