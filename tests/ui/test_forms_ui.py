"""Tests for filling a PDF form on the page."""

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.forms import page_fields

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


def place(view, page: int, x: float, y: float) -> QPoint:
    """Where a point of a page is in the window."""
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def click_field(view, name: str, index: int = 0) -> None:
    field = [field for field in view.fields_of(0) if field.name == name][index]
    x0, y0, x1, y1 = field.rect
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, (x0 + x1) / 2, (y0 + y1) / 2))


def value_of(view, name: str) -> str:
    return next(field for field in view.fields_of(0) if field.name == name).value


@pytest.fixture
def form(window, full_form, wait_until):
    window.show_problem_dialogs = False
    assert window.open_document(full_form)
    view = window.pdf_view
    wait_until(lambda: view.fields_of(0))
    return view


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def test_opening_a_form_says_how_to_fill_it(window, form):
    assert "formulario" in window.statusBar().currentMessage()
    assert form.has_form


def test_writing_in_a_box_and_tab_to_the_next(form, wait_until, full_form):
    click_field(form, "nombre")
    editor = form.field_editor
    assert editor is not None and editor.isVisible() and editor.box.hasFocus()
    editor.box.insert("Íñigo Pérez")  # (QTest types only plain letters)
    QTest.keyClick(editor.box, Qt.Key.Key_Tab)
    wait_until(lambda: form.field_editor is not None and form.field_editor.field.name == "dni")
    assert value_of(form, "nombre") == "Íñigo Pérez", "seen at once"
    QTest.keyClicks(form.field_editor.box, "12345678Z")
    QTest.keyClick(form.field_editor.box, Qt.Key.Key_Return)
    assert form.field_editor is None
    settle(form, wait_until)
    wait_until(lambda: value_of(form, "dni") == "12345678Z")
    assert form.modified
    assert form.undo()
    wait_until(lambda: value_of(form, "dni") == "")
    assert form.redo()
    wait_until(lambda: value_of(form, "dni") == "12345678Z")
    assert form.save()
    wait_until(lambda: not form.modified)
    with pymupdf.open(full_form) as saved:
        values = {field.name: field.value for field in page_fields(saved, 0)}
    assert values["nombre"] == "Íñigo Pérez" and values["dni"] == "12345678Z"


def test_esc_leaves_the_box_as_it_was(form, wait_until):
    click_field(form, "nombre")
    QTest.keyClicks(form.field_editor.box, "borrar")
    QTest.keyClick(form.field_editor.box, Qt.Key.Key_Escape)
    assert form.field_editor is None
    assert value_of(form, "nombre") == "" and not form._changing


def test_check_boxes_and_options_with_a_click(form, wait_until):
    click_field(form, "acepto")
    assert value_of(form, "acepto") == "Yes"
    settle(form, wait_until)
    click_field(form, "grupo", 1)
    settle(form, wait_until)
    wait_until(lambda: [f.checked for f in form.fields_of(0) if f.name == "grupo"] == [False, True])
    click_field(form, "grupo", 0)
    settle(form, wait_until)
    wait_until(lambda: [f.checked for f in form.fields_of(0) if f.name == "grupo"] == [True, False])
    click_field(form, "acepto")
    settle(form, wait_until)
    wait_until(lambda: value_of(form, "acepto") == "")
    assert len(form._undo) == 4


def test_a_list_offers_its_choices(form, wait_until):
    click_field(form, "provincia")
    menu = form.choice_menu
    assert [action.text() for action in menu.actions()] == [
        "Álava",
        "Bizkaia",
        "Gipuzkoa",
        "Madrid",
        "A Coruña",
    ]
    next(action for action in menu.actions() if action.text() == "Bizkaia").trigger()
    menu.close()
    settle(form, wait_until)
    wait_until(lambda: value_of(form, "provincia") == "Bizkaia")
    click_field(form, "turno")
    next(a for a in form.choice_menu.actions() if a.text() == "Tarde").trigger()
    form.choice_menu.close()
    settle(form, wait_until)
    wait_until(lambda: value_of(form, "turno") == "Tarde")


def test_the_keyboard_alone_fills_the_form(window, form, wait_until):
    assert window.fill_form()
    assert form.field_editor.field.name == "nombre"
    QTest.keyClick(form.field_editor.box, Qt.Key.Key_Tab)  # nothing written: no change
    QTest.keyClick(form.field_editor.box, Qt.Key.Key_Tab)
    QTest.keyClick(form.field_editor.box, Qt.Key.Key_Tab)
    wait_until(lambda: form._field_focus is not None and form._field_focus.name == "provincia")
    QTest.keyClick(form, Qt.Key.Key_Tab)
    assert form._field_focus.name == "acepto"
    QTest.keyClick(form, Qt.Key.Key_Space)
    assert value_of(form, "acepto") == "Yes"
    QTest.keyClick(form, Qt.Key.Key_Backtab)
    assert form._field_focus.name == "provincia"
    QTest.keyClick(form, Qt.Key.Key_Escape)
    assert form._field_focus is None
    settle(form, wait_until)
    assert len(form._undo) == 1


def test_what_is_being_written_is_kept_from_a_power_cut(form, wait_until):
    click_field(form, "observaciones")
    editor = form.field_editor
    assert editor.field.multiline
    editor.box.insertPlainText("Primera línea")
    QTest.keyClick(editor.box, Qt.Key.Key_Return)  # a new line, not the end
    QTest.keyClicks(editor.box, "segunda")
    assert form.field_editor is editor
    order = form.draft_order()
    assert order.name == "observaciones" and order.after == "Primera línea\nsegunda"
    form.write_draft()
    assert form.journal.draft() is not None
    QTest.keyClick(editor.box, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    settle(form, wait_until)
    wait_until(lambda: value_of(form, "observaciones") == "Primera línea\nsegunda")
    assert form.journal.draft() is None


def test_a_field_that_cannot_be_changed_says_so(window, tmp_path, sample, wait_until):
    path = tmp_path / "bloqueado.pdf"
    with pymupdf.open(sample("formulario.pdf")) as doc:
        page = doc[0]
        widget = next(w for w in page.widgets() if w.field_name == "nombre")
        parent = int(doc.xref_get_key(widget.xref, "Parent")[1].split()[0])
        doc.xref_set_key(parent, "Ff", "1")  # read only
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: view.fields_of(0))
    click_field(view, "nombre")
    assert view.field_editor is None
    assert "no se puede cambiar" in window.statusBar().currentMessage()


def test_on_a_scan_escribir_writes_anywhere(window, sample, tmp_path, wait_until):
    import shutil

    from app.core.notes import TEXT_BOX
    from app.ui.text_editor import TextEditor

    path = tmp_path / "escaneado.pdf"
    shutil.copy(sample("escaneado.pdf"), path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages())
    window.feature_actions["type_text"].trigger()
    assert view.markup_tool == TEXT_BOX
    assert window.feature_actions["type_text"].isChecked()
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 120, 200))
    editor = view.note_panel
    assert isinstance(editor, TextEditor)
    QTest.keyClicks(editor.edit, "12345678Z")
    QTest.keyClick(editor.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    settle(view, wait_until)
    wait_until(lambda: [note.text for note in view.notes_of(0)] == ["12345678Z"])
