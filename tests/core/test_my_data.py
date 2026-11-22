"""Tests for «Mis datos»: kept data and which field asks for which."""

import pymupdf

from app.core.commands import command_from_dict
from app.core.forms import TEXT, FillField, FillFields, page_fields
from app.core.my_data import (
    ADDRESS,
    BIRTH,
    EMAIL,
    FULL_NAME,
    ID,
    NAME,
    PHONE,
    POSTCODE,
    PROVINCE,
    SURNAMES,
    TOWN,
    MyData,
    choice_for,
    datum_for,
)


def test_fields_are_matched_as_spanish_forms_call_them():
    cases = {
        "Nombre y apellidos": FULL_NAME,
        "APELLIDOS, NOMBRE": FULL_NAME,
        "Nombre del solicitante": FULL_NAME,
        "nombre": NAME,
        "Primer apellido": SURNAMES,
        "D.N.I.": ID,
        "N.I.F./N.I.E.": ID,
        "Número de documento": ID,
        "Domicilio": ADDRESS,
        "Dirección": ADDRESS,
        "codigoPostal": POSTCODE,
        "C.P.": POSTCODE,
        "Municipio": TOWN,
        "Provincia": PROVINCE,
        "Teléfono móvil": PHONE,
        "Correo electrónico": EMAIL,
        "e-mail": EMAIL,
        "Fecha de nacimiento": BIRTH,
    }
    for name, key in cases.items():
        assert datum_for(name) == key, name
    assert datum_for("Observaciones") is None
    assert datum_for("", "dni") == ID, "the name, when there is no description"


def test_the_data_are_kept_and_the_full_name_is_made():
    data = MyData.from_setting({NAME: " Íñigo ", SURNAMES: "Pérez Muñoz", "otro": "x"})
    assert data.value(FULL_NAME) == "Íñigo Pérez Muñoz"
    assert data.to_setting() == {NAME: "Íñigo", SURNAMES: "Pérez Muñoz"}
    assert MyData.from_setting(None).empty
    assert choice_for("bizkaia", ("Álava", "Bizkaia")) == "Bizkaia"
    assert choice_for("Alava", ("Álava", "Bizkaia")) == "Álava"
    assert choice_for("Navarra", ("Álava",)) is None


def test_several_fields_are_one_change(full_form):
    with pymupdf.open(full_form) as doc:
        order = FillFields(
            (FillField(0, "nombre", TEXT, "", "Íñigo"), FillField(0, "dni", TEXT, "", "1234Z"))
        )
        assert command_from_dict(order.to_dict()) == order
        order.apply(doc)
        values = {field.name: field.value for field in page_fields(doc, 0)}
        assert (values["nombre"], values["dni"]) == ("Íñigo", "1234Z")
        order.undo(doc)
        values = {field.name: field.value for field in page_fields(doc, 0)}
        assert (values["nombre"], values["dni"]) == ("", "")
