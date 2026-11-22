"""Tests for reading and filling the fields of a PDF form."""

import pymupdf
import pytest

from app.core.commands import CommandError, command_from_dict
from app.core.forms import CHECK, COMBO, LIST, RADIO, TEXT, FillField, page_fields


def fields_by_name(doc):
    found = {}
    for field in page_fields(doc, 0):
        found.setdefault(field.name, []).append(field)
    return found


def test_every_kind_of_field_is_read(full_form):
    with pymupdf.open(full_form) as doc:
        found = fields_by_name(doc)
    assert found["nombre"][0].kind == TEXT and found["nombre"][0].value == ""
    assert found["observaciones"][0].multiline
    assert found["provincia"][0].kind == COMBO
    assert found["provincia"][0].choices == ("Álava", "Bizkaia", "Gipuzkoa", "Madrid", "A Coruña")
    assert found["acepto"][0].kind == CHECK and found["acepto"][0].on == "Yes"
    assert not found["acepto"][0].checked
    assert [(field.kind, field.on) for field in found["grupo"]] == [(RADIO, "uno"), (RADIO, "dos")]
    assert found["turno"][0].kind == LIST and found["turno"][0].value == "Mañana"
    tops = [field.rect[1] for field in page_fields(pymupdf.open(full_form), 0)]
    assert tops == sorted(tops), "in the order of the form"


def test_a_field_filled_is_saved_as_a_standard_form_and_undone(full_form, tmp_path):
    with pymupdf.open(full_form) as doc:
        order = FillField(0, "nombre", TEXT, "", "Íñigo Pérez Muñoz")
        assert command_from_dict(order.to_dict()) == order
        assert order.apply(doc) == [0]
        assert fields_by_name(doc)["nombre"][0].value == "Íñigo Pérez Muñoz"
        doc.save(tmp_path / "relleno.pdf")
        order.undo(doc)
        assert fields_by_name(doc)["nombre"][0].value == ""
    with pymupdf.open(tmp_path / "relleno.pdf") as saved:
        widget = next(w for w in saved[0].widgets() if w.field_name == "nombre")
        assert widget.field_value == "Íñigo Pérez Muñoz"
        assert "Muñoz" in saved[0].get_text(), "its look is drawn: every reader shows it"


def test_check_boxes_lists_and_options(full_form):
    with pymupdf.open(full_form) as doc:
        FillField(0, "acepto", CHECK, "", "Yes").apply(doc)
        FillField(0, "provincia", COMBO, "", "Bizkaia").apply(doc)
        FillField(0, "turno", LIST, "Mañana", "Tarde").apply(doc)
        FillField(0, "grupo", RADIO, "", "dos").apply(doc)
        found = fields_by_name(doc)
        assert found["acepto"][0].checked
        assert found["provincia"][0].value == "Bizkaia"
        assert found["turno"][0].value == "Tarde"
        assert [field.checked for field in found["grupo"]] == [False, True]
        FillField(0, "grupo", RADIO, "dos", "uno").apply(doc)
        assert [field.checked for field in fields_by_name(doc)["grupo"]] == [True, False]
        FillField(0, "grupo", RADIO, "dos", "uno").undo(doc)
        assert [field.checked for field in fields_by_name(doc)["grupo"]] == [False, True]
        FillField(0, "acepto", CHECK, "", "Yes").undo(doc)
        assert not fields_by_name(doc)["acepto"][0].checked


def test_a_field_that_is_not_there_is_an_error(full_form):
    with pymupdf.open(full_form) as doc, pytest.raises(CommandError):
        FillField(0, "no_existe", TEXT, "", "x").apply(doc)


def test_on_a_page_kept_turned_the_field_is_where_it_is_seen(full_form):
    with pymupdf.open(full_form) as doc:
        straight = fields_by_name(doc)["nombre"][0].rect
        doc[0].set_rotation(90)
        turned = fields_by_name(doc)["nombre"][0].rect
    width = turned[2] - turned[0]
    assert width == pytest.approx(straight[3] - straight[1], abs=0.1), "now it is upright"
