"""Tests for taking away annotations made by other programs, and putting them
back exactly as they were."""

import pymupdf
import pytest

from app.core.commands import CommandError, command_from_dict
from app.core.drawing import page_drawings
from app.core.foreign import OTHER, Foreign, key_of
from app.core.notes import Remove, page_notes


@pytest.fixture
def doc():
    """A page with what other programs put: marks, drawings, notes, a stamp…"""
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 100), "Texto de prueba para marcar con otro programa.")
    page.add_highlight_annot(pymupdf.Rect(70, 88, 300, 104))
    page.add_ink_annot([[(100, 200), (150, 250), (200, 210)]])
    page.add_line_annot((100, 300), (300, 300))
    page.add_rect_annot(pymupdf.Rect(100, 350, 200, 420))
    page.add_freetext_annot(pymupdf.Rect(300, 350, 500, 400), "Texto de Edge")
    page.add_text_annot((400, 500), "Nota de Adobe")
    page.add_stamp_annot(pymupdf.Rect(100, 600, 250, 650), stamp=0)
    page.add_polygon_annot([(300, 600), (400, 600), (350, 680)])
    page.add_squiggly_annot(pymupdf.Rect(70, 88, 150, 104))
    yield document
    document.close()


def everything(document, number=0):
    return [*page_notes(document, number), *page_drawings(document, number)]


def annotation_types(document, number=0) -> list[str]:
    return sorted(annot.type[1] for annot in document[number].annots())


def test_all_of_them_are_read_and_can_be_taken_away(doc):
    items = everything(doc)
    assert len(items) == 9
    assert all(item.removable and not item.ours for item in items)
    assert all(item.name.startswith("#") for item in items)
    kinds = {item.kind for item in items}
    assert {"highlight", "ink", "note", "text_box", OTHER} <= kinds


def test_taking_one_away_and_undo_puts_back_exactly_the_same(doc):
    before = annotation_types(doc)
    highlight = next(item for item in page_drawings(doc, 0) if item.kind == "highlight")
    xref = highlight.foreign.xrefs[0]
    written = doc.xref_object(xref)
    order = Remove(highlight.order())
    assert order.apply(doc) == [0]
    assert "Highlight" not in annotation_types(doc)
    order.undo(doc)
    assert annotation_types(doc) == before
    assert doc.xref_object(xref) == written, "the very same object, untouched"


def test_a_note_takes_its_popup_and_its_replies_with_it(doc):
    page = doc[0]
    note = next(item for item in page_notes(doc, 0) if item.kind == "note")
    parent = note.foreign.xrefs[0]
    reply = page.add_text_annot((420, 520), "Respuesta")
    doc.xref_set_key(reply.xref, "IRT", f"{parent} 0 R")
    reply_xref = reply.xref
    note = next(item for item in page_notes(doc, 0) if item.name == key_of(parent))
    assert len(note.foreign.xrefs) == 4  # the note, its pop-up, the reply and its pop-up
    order = Remove(note.order())
    order.apply(doc)
    left = [annot.xref for annot in doc[0].annots()]
    assert parent not in left and reply_xref not in left
    assert "Popup" not in doc.xref_get_key(doc[0].xref, "Annots")[1]
    popups = [x for x in note.foreign.xrefs if doc.xref_get_key(x, "Subtype")[1] == "/Popup"]
    listed = doc.xref_get_key(doc[0].xref, "Annots")[1]
    assert all(f"{x} 0 R" not in listed for x in popups)
    order.undo(doc)
    listed = doc.xref_get_key(doc[0].xref, "Annots")[1]
    assert all(f"{x} 0 R" in listed for x in note.foreign.xrefs)


@pytest.mark.parametrize("kind", ["Ink", "Line", "Square", "FreeText", "Stamp", "Polygon"])
def test_every_kind_goes_and_comes_back(doc, kind):
    item = next(item for item in everything(doc) if item.foreign.subtype == kind)
    order = Remove(item.order())
    order.apply(doc)
    assert kind not in annotation_types(doc)
    order.undo(doc)
    assert kind in annotation_types(doc)


def test_form_fields_signatures_and_links_are_never_read(doc):
    page = doc[0]
    field = pymupdf.Widget()
    field.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    field.field_name = "nombre"
    field.rect = pymupdf.Rect(100, 700, 300, 720)
    page.add_widget(field)
    page.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(100, 750, 200, 770),
            "uri": "https://boe.es",
        }
    )
    subtypes = {item.foreign.subtype for item in everything(doc)}
    assert subtypes.isdisjoint({"Widget", "Link", "Popup"})


def test_it_is_written_in_the_journal_and_read_back(doc):
    item = page_drawings(doc, 0)[0]
    order = Remove(item.order())
    again = command_from_dict(order.to_dict())
    assert again == order
    assert isinstance(again.order, Foreign)


def test_saved_without_it_and_deshacer_still_works_after_saving(doc, tmp_path):
    item = next(item for item in page_drawings(doc, 0) if item.kind == "ink")
    order = Remove(item.order())
    order.apply(doc)
    path = tmp_path / "sin-dibujo.pdf"
    doc.save(path, garbage=0, deflate=True)  # as the program saves
    with pymupdf.open(path) as saved:  # and goes on with the saved file
        assert "Ink" not in annotation_types(saved)
        order.undo(saved)
        assert "Ink" in annotation_types(saved)


def test_a_list_kept_apart_from_the_page_is_changed_too(doc):
    listed = doc.xref_get_key(doc[0].xref, "Annots")[1]
    holder = doc.get_new_xref()
    doc.update_object(holder, listed)
    doc.xref_set_key(doc[0].xref, "Annots", f"{holder} 0 R")
    item = next(item for item in page_drawings(doc, 0) if item.kind == "ink")
    order = Remove(item.order())
    order.apply(doc)
    assert "Ink" not in annotation_types(doc)
    order.undo(doc)
    assert "Ink" in annotation_types(doc)
    assert doc.xref_get_key(doc[0].xref, "Annots")[0] == "xref"


def test_another_object_in_that_place_is_not_touched(doc):
    item = page_drawings(doc, 0)[0]
    wrong = Foreign(0, item.foreign.xrefs, "Circle", item.foreign.rect)
    with pytest.raises(CommandError):
        Remove(wrong).apply(doc)
    with pytest.raises(CommandError):
        Foreign(0, (99999,), "Ink", (0, 0, 1, 1)).undo(doc)


def test_taking_away_what_is_not_there_says_so(doc):
    item = page_drawings(doc, 0)[0]
    order = Remove(item.order())
    order.apply(doc)
    with pytest.raises(CommandError):
        order.apply(doc)


def test_ours_are_not_foreign(doc):
    from app.core.drawing import new_shape

    new_shape("box", 0, (50, 50), (90, 90)).apply(doc)
    ours = [item for item in page_drawings(doc, 0) if item.ours]
    assert len(ours) == 1 and ours[0].foreign is None
