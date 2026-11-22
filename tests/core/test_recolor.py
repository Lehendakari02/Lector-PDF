"""Tests for giving another colour to what is already on a page."""

import pymupdf
import pytest

from app.core.arrange import can_recolor, recolored
from app.core.commands import HIGHLIGHT, AddMarkup, Mark, new_name
from app.core.drawing import BOX, new_ink, new_shape, page_drawings
from app.core.notes import new_note, new_text_box, page_notes

GREEN = (0.56, 0.88, 0.42)


def everything(doc):
    return [*page_drawings(doc, 0), *page_notes(doc, 0)]


@pytest.fixture
def doc():
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 100), "Artículo 14. Los españoles son iguales ante la ley.")
    rect = tuple(page.search_for("Artículo 14")[0])
    AddMarkup(HIGHLIGHT, (Mark(0, (rect,), new_name()),), (1.0, 0.92, 0.23)).apply(document)
    new_ink(0, [[(100, 200), (150, 250), (200, 210)]]).apply(document)
    new_shape(BOX, 0, (100, 300), (200, 360), fill=True).apply(document)
    new_note(0, (400, 400), "Repasar").apply(document)
    new_text_box(0, (72, 500), "Ojo al plazo").apply(document)
    yield document
    document.close()


def test_every_kind_changes_colour_in_its_place_and_undo_brings_it_back(doc):
    before = {item.name: item for item in everything(doc)}
    assert len(before) == 5
    for item in before.values():
        change = recolored(item.order(), GREEN)
        assert change is not None, item.kind
        change.apply(doc)
    after = {item.name: item for item in everything(doc)}
    assert after.keys() == before.keys(), "the same ones, not new ones"
    for name, item in after.items():
        assert item.color == pytest.approx(GREEN, abs=0.01), item.kind
        assert item.rect == pytest.approx(before[name].rect, abs=0.5), "in the same place"
    for item in after.values():
        recolored(before[item.name].order(), GREEN).undo(doc)
    for item in everything(doc):
        assert item.color == pytest.approx(before[item.name].color, abs=0.01)


def test_the_same_colour_or_another_program_s_annotation_gives_nothing(doc):
    item = page_drawings(doc, 0)[0]
    assert recolored(item.order(), item.color) is None
    doc[0].add_highlight_annot(pymupdf.Rect(70, 88, 150, 104))
    foreign = next(i for i in page_drawings(doc, 0) if i.foreign is not None)
    assert not can_recolor(foreign.order())
    assert recolored(foreign.order(), GREEN) is None
