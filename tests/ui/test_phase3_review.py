"""Tests for the fixes of the Phase 3 code review (task 3.8b)."""

import shutil
import struct
from pathlib import Path

import pymupdf
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from app.core import my_signature
from app.core.drawing import PICTURE
from app.core.forms import page_fields
from app.core.my_data import ID, NAME, SURNAMES, MyData
from app.ui.signature_dialog import upright_picture
from tests.ui.test_forms_ui import click_field, place, settle, value_of
from tests.ui.test_signature_ui import photo

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def form(window, full_form, wait_until):
    window.show_problem_dialogs = False
    assert window.open_document(full_form)
    view = window.pdf_view
    wait_until(lambda: view.fields_of(0))
    return view


def values_in(path) -> dict:
    with pymupdf.open(path) as doc:
        pages = range(doc.page_count)
        return {field.name: field.value for n in pages for field in page_fields(doc, n)}


# ---- A1: what is being written in a field counts when saving or closing ------------


def test_ctrl_s_while_writing_in_a_field_saves_it(window, form, wait_until, full_form):
    click_field(form, "nombre")
    form.field_editor.box.insert("Ana")
    assert window.save_document(), "not «No hay cambios que guardar»"
    assert form.field_editor is None
    wait_until(lambda: not form.saving and not form.modified)
    assert values_in(full_form)["nombre"] == "Ana"


def test_closing_while_writing_in_a_field_asks_and_keeps_it(window, form, wait_until, full_form):
    click_field(form, "nombre")
    form.field_editor.box.insert("Ana")
    window.unsaved_answer = "save"
    window.close()
    wait_until(lambda: not form.saving)
    assert values_in(full_form)["nombre"] == "Ana"


# ---- M2: the whole form, not only the pages seen -----------------------------------


def _long_form(path: Path) -> None:
    with pymupdf.open() as doc:
        for number in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Página {number + 1}")
        for number, (name, label) in enumerate((("nombre", "Nombre"), ("doc", "D.N.I."))):
            widget = pymupdf.Widget()
            widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
            widget.field_name = name
            widget.field_label = label
            widget.rect = pymupdf.Rect(100, 700, 300, 720)
            doc[2 * number].add_widget(widget)  # pages 1 and 3
        doc.save(path)


def test_my_data_fill_the_pages_not_seen_yet(window, tmp_path, wait_until):
    path = tmp_path / "solicitud.pdf"
    _long_form(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 2 in view._fields)  # read at once, without going there
    window.my_data_answer = MyData.from_setting({NAME: "Ane", ID: "12345678Z"})
    menu = window.show_my_data()
    assert "2 campos" in menu.actions()[0].text()
    menu.actions()[0].trigger()
    settle(view, wait_until)
    wait_until(lambda: [f.value for f in view.fields_of(2)] == ["12345678Z"])
    assert view.focus_field(+1).page == 0
    assert view.focus_field(+1).page == 2, "Tab reaches the last page too"


# ---- M3: saving what was just signed proposes "-firmado" however it is saved -------


def _signed(window, tmp_path, wait_until):
    path = tmp_path / "contrato.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=595, height=842)
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    window.signature_answer = my_signature.clean(Path(photo(tmp_path)).read_bytes())
    window.settings.set("firma/fecha", False)
    assert window.show_signature() is None
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 300, 400))
    wait_until(lambda: any(item.kind == PICTURE for item in view.drawings_of(0)))
    return path, view


def test_saving_when_closing_proposes_a_signed_copy(window, tmp_path, wait_until):
    path, view = _signed(window, tmp_path, wait_until)
    asked = []
    window.signed_save_answer = "copy"
    window.save_as_answer = lambda suggested: asked.append(suggested) or str(suggested)
    window.unsaved_answer = "save"
    window.close()
    wait_until(lambda: not view.saving and (tmp_path / "contrato-firmado.pdf").exists())
    assert [p.name for p in asked] == ["contrato-firmado.pdf"]
    with pymupdf.open(path) as doc:
        assert not list(doc[0].annots()), "the original stays as it was"


def test_a_signed_copy_not_chosen_is_asked_again_and_undone_is_not_asked(
    window, tmp_path, wait_until
):
    path, view = _signed(window, tmp_path, wait_until)
    window.signed_save_answer = "copy"
    window.save_as_answer = lambda suggested: ""  # the window to choose was cancelled
    assert not window.save_document()
    assert view.signed_by_hand, "asked again the next time"
    view.undo()
    wait_until(lambda: not view.drawings_of(0))
    assert not view.signed_by_hand, "nothing signed any more: nothing to ask"


# ---- M4: a phone photo lying down -------------------------------------------------


def test_a_phone_photo_is_turned_as_it_is_meant(tmp_path, qt_app):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 100), 0)
    pix.clear_with(240)
    jpeg = pix.tobytes("jpg")
    # EXIF: Orientation 6, "turn it a quarter to the right to see it".
    tiff = b"II*\x00" + struct.pack("<IH", 8, 1) + struct.pack("<HHIHH", 0x0112, 3, 1, 6, 0)
    exif = b"Exif\x00\x00" + tiff + struct.pack("<I", 0)
    segment = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    path = tmp_path / "movil.jpg"
    path.write_bytes(jpeg[:2] + segment + jpeg[2:])
    upright = pymupdf.Pixmap(upright_picture(str(path)))
    assert (upright.width, upright.height) == (100, 300)
    assert upright_picture(str(tmp_path / "no-existe.jpg")) == b""


# ---- B2 and B3: the date and the stamps stay clear and inside the page -------------


def test_the_date_goes_over_a_signature_at_the_foot_of_the_page(window, tmp_path, wait_until):
    path = tmp_path / "contrato.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=595, height=842)
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    window.signature_answer = my_signature.clean(Path(photo(tmp_path)).read_bytes())
    window.settings.set("firma/fecha", True)
    assert window.show_signature() is None
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 300, 838))
    wait_until(lambda: view.notes_of(0) and view.drawings_of(0))
    (signed,) = [item for item in view.drawings_of(0) if item.kind == PICTURE]
    (date,) = view.notes_of(0)
    assert date.rect[3] <= signed.rect[1] + 0.5, "over it, not on it"


def test_a_stamp_by_the_right_edge_stays_inside_the_page(window, sample, tmp_path, wait_until):
    from app.core.stamps import OWN, Stamp

    path = tmp_path / "escaneado.pdf"
    shutil.copy(sample("escaneado.pdf"), path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages())
    width = view._sizes[0].width
    assert view.put_stamp(Stamp(OWN, "Recibido y conforme"), 0, width - 2, 300)
    settle(view, wait_until)
    wait_until(lambda: view.notes_of(0))
    assert view.notes_of(0)[0].rect[2] <= width + 0.5


# ---- B4 and B6: passwords and lists with several choices -------------------------


def test_a_password_field_shows_dots(window, tmp_path, wait_until):
    path = tmp_path / "clave.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = "clave"
        widget.field_flags = 1 << 13
        widget.rect = pymupdf.Rect(100, 100, 300, 120)
        page.add_widget(widget)
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: view.fields_of(0))
    view.use_field(view.fields_of(0)[0])
    assert view.field_editor.box.echoMode() == QLineEdit.EchoMode.Password
    QTest.keyClick(view.field_editor.box, Qt.Key.Key_Escape)


def test_a_list_with_several_choices_is_not_changed(window, tmp_path, wait_until):
    from app.core.forms import _field_object

    path = tmp_path / "dias.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_LISTBOX
        widget.field_name = "dias"
        widget.choice_values = ["lunes", "martes", "jueves"]
        widget.field_flags = 1 << 21
        widget.rect = pymupdf.Rect(100, 100, 300, 160)
        page.add_widget(widget)
        field = _field_object(doc, next(page.widgets()).xref)
        doc.xref_set_key(field, "V", "[(lunes) (jueves)]")
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: view.fields_of(0))
    assert not view.use_field(view.fields_of(0)[0])
    assert "varias opciones" in window.statusBar().currentMessage()
    assert view.choice_menu is None and not view.modified


def test_the_surnames_go_one_in_each_box(window, tmp_path, wait_until):
    path = tmp_path / "apellidos.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for index, (name, label) in enumerate(
            (
                ("a1", "Primer apellido"),
                ("a2", "Segundo apellido"),
                ("lugar", "Lugar de nacimiento"),
            )
        ):
            widget = pymupdf.Widget()
            widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
            widget.field_name = name
            widget.field_label = label
            widget.rect = pymupdf.Rect(100, 100 + 40 * index, 300, 120 + 40 * index)
            page.add_widget(widget)
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: len(view.fields_of(0)) == 3)
    data = MyData.from_setting({NAME: "Ane", SURNAMES: "Etxeberria Goñi", "birth": "01/02/1990"})
    window.settings.set("mis_datos", data.to_setting())
    assert window.fill_with_my_data() == 2
    settle(view, wait_until)
    wait_until(lambda: value_of(view, "a2") == "Goñi")
    assert value_of(view, "a1") == "Etxeberria" and value_of(view, "lugar") == ""
