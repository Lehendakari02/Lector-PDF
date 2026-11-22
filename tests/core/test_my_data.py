"""Tests for «Mis datos»: kept data and which field asks for which."""

import pymupdf

from app.core.commands import command_from_dict
from app.core.forms import TEXT, FillField, FillFields, page_fields
from app.core.my_data import (
    ADDRESS,
    BIRTH,
    EMAIL,
    FIRST_SURNAME,
    FULL_NAME,
    ID,
    NAME,
    PHONE,
    POSTCODE,
    PROVINCE,
    SECOND_SURNAME,
    SURNAMES,
    SURNAMES_NAME,
    TOWN,
    MyData,
    choice_for,
    datum_for,
)


def test_fields_are_matched_as_spanish_forms_call_them():
    cases = {
        "Nombre y apellidos": FULL_NAME,
        "APELLIDOS, NOMBRE": SURNAMES_NAME,
        "Nombre del solicitante": FULL_NAME,
        "nombre": NAME,
        "Primer apellido": FIRST_SURNAME,
        "Apellidos": SURNAMES,
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


def test_fields_about_someone_else_or_another_thing_are_not_mine():
    # Review of Phase 3, A2: these got one's name or the date of birth.
    cases = {
        "DNI del solicitante": ID,
        "NIF del interesado": ID,
        "Domicilio del interesado": ADDRESS,
        "Correo electrónico del solicitante": EMAIL,
        "Teléfono del titular": PHONE,
        "Primer apellido": FIRST_SURNAME,
        "Segundo apellido": SECOND_SURNAME,
        "2º apellido": SECOND_SURNAME,
        "Apellido 1": FIRST_SURNAME,
        "Nombre de la vía": ADDRESS,
        "Solicitante": FULL_NAME,
        "Lugar de nacimiento": None,
        "Provincia de nacimiento": None,
        "País de nacimiento": None,
        "Tipo de documento": None,
        "Tipo de vía": None,
        "Nombre del representante": None,
        "DNI del cónyuge": None,
        "Nombre de la empresa": None,
        "Apellidos del padre": None,
    }
    for name, key in cases.items():
        assert datum_for(name) == key, name


def test_the_surnames_are_split_and_put_in_the_order_asked():
    data = MyData.from_setting({NAME: "Ana", SURNAMES: "de la Fuente García"})
    assert data.value(FIRST_SURNAME) == "de la Fuente"
    assert data.value(SECOND_SURNAME) == "García"
    assert data.value(SURNAMES_NAME) == "de la Fuente García, Ana"
    single = MyData.from_setting({NAME: "Ane", SURNAMES: "Etxeberria"})
    assert (single.value(FIRST_SURNAME), single.value(SECOND_SURNAME)) == ("Etxeberria", "")


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
