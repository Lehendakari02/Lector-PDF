"""Tests for the list of everything put on a document, as the annotations
panel shows it."""

import pymupdf
import pytest

from app.core.annotation_list import (
    DRAWINGS,
    MARKS,
    NOTES,
    color_key,
    colors_of,
    document_entries,
    page_entries,
    same_color,
)
from app.core.commands import AddMarkup, Mark, new_name
from app.core.drawing import new_ink
from app.core.notes import new_note, new_text_box

YELLOW = (1.0, 0.9, 0.2)
GREEN = (0.3, 0.8, 0.3)


def document(rotation: int = 0) -> pymupdf.Document:
    doc = pymupdf.open()
    for number in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Artículo {number + 1}. El año de la ley.", fontsize=12)
        page.insert_text((72, 300), "Una línea más abajo, para subrayar.", fontsize=12)
        page.set_rotation(rotation)
    return doc


def words_rect(doc, number: int, text: str):
    page = doc[number]
    found = page.search_for(text)[0]
    return tuple(found * page.rotation_matrix)


def mark(doc, number, text, color=YELLOW, kind="highlight"):
    rect = words_rect(doc, number, text)
    AddMarkup(kind, (Mark(number, (rect,), new_name()),), color).apply(doc)


def test_marks_notes_texts_and_drawings_in_reading_order():
    with document() as doc:
        mark(doc, 0, "Una línea más abajo", GREEN, "underline")
        mark(doc, 0, "El año de la ley", YELLOW)
        new_note(0, (400, 500), "Repasar esto").apply(doc)
        new_text_box(0, (72, 600), "Ojo: plazo de 10 días").apply(doc)
        new_ink(0, [[(100, 700), (150, 720), (200, 710)]]).apply(doc)
        mark(doc, 2, "Artículo 3", GREEN)
        entries = document_entries(doc)
    assert [(e.page, e.kind) for e in entries] == [
        (0, "highlight"),
        (0, "underline"),
        (0, "note"),
        (0, "text_box"),
        (0, "ink"),
        (2, "highlight"),
    ]
    assert entries[0].text == "El año de la ley."
    assert entries[1].text == "Una línea más abajo,"
    assert entries[2].text == "Repasar esto"
    assert entries[3].text == "Ojo: plazo de 10 días"
    assert entries[4].text == ""
    assert entries[5].text == "Artículo 3."
    assert [e.group for e in entries] == [MARKS, MARKS, NOTES, NOTES, DRAWINGS, MARKS]
    assert same_color(entries[0].color, YELLOW) and same_color(entries[1].color, GREEN)
    colors = colors_of(entries)
    assert len(colors) == 5  # yellow, green, the note, the text and the pen
    assert same_color(colors[0], YELLOW) and same_color(colors[1], GREEN)


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_the_words_of_a_mark_on_a_turned_page(rotation):
    with document(rotation) as doc:
        mark(doc, 1, "El año de la ley")
        (entry,) = page_entries(doc, 1)
    assert entry.text == "El año de la ley."


def test_marks_made_by_other_programs_are_listed_too():
    with document() as doc:
        page = doc[0]
        page.add_highlight_annot(page.search_for("Una línea")[0])
        (entry,) = document_entries(doc)
    assert entry.kind == "highlight" and entry.text == "Una línea"
    assert entry.name.startswith("#")


def test_a_page_without_annotations_has_none_and_long_texts_are_cut():
    with document() as doc:
        assert document_entries(doc) == []
        new_note(1, (100, 100), "palabra " * 100).apply(doc)
        (entry,) = document_entries(doc)
    assert len(entry.text) <= 300 and entry.text.endswith("…")


def test_colour_keys():
    assert color_key((1.0, 0.0, 0.0)) == "#ff0000"
    assert same_color((1.0, 0.82, 0.2), (1.0, 0.83, 0.19))
    assert not same_color((1.0, 0.82, 0.2), (1.0, 0.7, 0.2))
    assert color_key((1.2, -0.1, 0.5)) == "#ff0080"
