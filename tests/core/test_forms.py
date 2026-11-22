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


def _boxes_with_one_name(doc, page, name="sexo", states=("H", "M")):
    """Two check boxes with one name and an "on" of their own each (Sí / No)."""
    parent, kids = doc.get_new_xref(), []
    height = page.rect.height
    for index, state in enumerate(states):
        shown, empty = doc.get_new_xref(), doc.get_new_xref()
        for xref, stream in ((shown, b"0 0 1 rg 4 4 8 8 re f"), (empty, b"")):
            doc.update_object(xref, "<< /Type /XObject /Subtype /Form /BBox [0 0 16 16] >>")
            doc.update_stream(xref, stream)
        kid = doc.get_new_xref()
        top = 100 + 30 * index
        doc.update_object(
            kid,
            f"<< /Type /Annot /Subtype /Widget /Rect [100 {height - top - 16} 116 {height - top}]"
            f" /Parent {parent} 0 R /P {page.xref} 0 R /AS /Off"
            f" /AP << /N << /{state} {shown} 0 R /Off {empty} 0 R >> >> >>",
        )
        kids.append(kid)
    refs = " ".join(f"{kid} 0 R" for kid in kids)
    doc.update_object(parent, f"<< /FT /Btn /T ({name}) /V /Off /Kids [{refs}] >>")
    doc.xref_set_key(page.xref, "Annots", f"[{refs}]")
    doc.xref_set_key(doc.pdf_catalog(), "AcroForm", f"<< /Fields [{parent} 0 R] >>")
    return parent, kids


def test_boxes_with_one_name_are_one_answer():
    doc = pymupdf.open()
    parent, kids = _boxes_with_one_name(doc, doc.new_page())
    FillField(0, "sexo", CHECK, "", "M").apply(doc)
    assert [(f.on, f.checked) for f in page_fields(doc, 0)] == [("H", False), ("M", True)]
    assert doc.xref_get_key(parent, "V") == ("name", "/M"), "a name, not a text"
    assert [doc.xref_get_key(kid, "AS")[1] for kid in kids] == ["/Off", "/M"]
    FillField(0, "sexo", CHECK, "M", "H").apply(doc)
    assert [f.checked for f in page_fields(doc, 0)] == [True, False]
    FillField(0, "sexo", CHECK, "M", "H").undo(doc)
    assert [f.checked for f in page_fields(doc, 0)] == [False, True]
    FillField(0, "sexo", CHECK, "", "M").undo(doc)
    assert [f.checked for f in page_fields(doc, 0)] == [False, False]
    assert doc.xref_get_key(parent, "V") == ("name", "/Off")


def _list_with_codes(doc, page):
    from app.core.forms import _field_object

    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    widget.field_name = "prov"
    widget.choice_values = ["x"]
    widget.rect = pymupdf.Rect(50, 50, 200, 70)
    page.add_widget(widget)
    field = _field_object(doc, next(page.widgets()).xref)
    doc.xref_set_key(field, "Opt", "[[(28) (Madrid)] [(48) (Bizkaia)]]")
    doc.xref_set_key(field, "V", "(28)")
    return field


def test_a_list_with_codes_shows_the_names_and_writes_the_codes():
    doc = pymupdf.open()
    page = doc.new_page()
    field = _list_with_codes(doc, page)
    found = page_fields(doc, 0)[0]
    assert found.choices == ("Madrid", "Bizkaia")
    assert found.value == "Madrid"
    FillField(0, "prov", COMBO, "Madrid", "Bizkaia").apply(doc)
    assert doc.xref_get_key(field, "V") == ("string", "48"), "the code, as the standard says"
    assert page_fields(doc, 0)[0].value == "Bizkaia"
    assert "Bizkaia" in doc[0].get_text("text", clip=pymupdf.Rect(40, 40, 210, 80))
    FillField(0, "prov", COMBO, "Madrid", "Bizkaia").undo(doc)
    assert doc.xref_get_key(field, "V") == ("string", "28")


def test_hidden_fields_are_left_out():
    doc = pymupdf.open()
    page = doc.new_page()
    for name, top in (("visto", 50), ("oculto", 100)):
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = pymupdf.Rect(50, top, 200, top + 20)
        page.add_widget(widget)
    hidden = next(w for w in page.widgets() if w.field_name == "oculto")
    doc.xref_set_key(hidden.xref, "F", "2")
    assert [field.name for field in page_fields(doc, 0)] == ["visto"]


def test_password_fields_and_lists_with_several_taken_are_known():
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "clave"
    widget.field_flags = 1 << 13
    widget.rect = pymupdf.Rect(50, 50, 200, 70)
    page.add_widget(widget)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_LISTBOX
    widget.field_name = "dias"
    widget.choice_values = ["lunes", "martes", "jueves"]
    widget.field_flags = 1 << 21
    widget.rect = pymupdf.Rect(50, 100, 200, 160)
    page.add_widget(widget)
    from app.core.forms import _field_object

    days = _field_object(doc, next(w for w in page.widgets() if w.field_name == "dias").xref)
    doc.xref_set_key(days, "V", "[(lunes) (jueves)]")
    doc.reload_page(page)
    found = {field.name: field for field in page_fields(doc, 0)}
    assert found["clave"].password and not found["dias"].password
    assert found["dias"].several
