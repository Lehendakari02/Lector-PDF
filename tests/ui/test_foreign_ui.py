"""Tests for taking away, in the window, what other programs put on a PDF:
picked and Supr, the eraser, the right button, Deshacer, saving and recovery."""

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.drawing import ERASER
from app.core.foreign import OTHER

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def foreign(window, sample, tmp_path, wait_until):
    """A BOE page where other programs left a highlight, a stroke, a stamp,
    a form field and a link."""
    path = tmp_path / "ajeno.pdf"
    with pymupdf.open(sample("boe.pdf")) as doc:
        page = doc[0]
        page.add_highlight_annot(pymupdf.Rect(100, 300, 300, 315))
        page.add_ink_annot([[(100, 400), (200, 400)]])
        page.add_stamp_annot(pymupdf.Rect(350, 500, 500, 550), stamp=0)
        field = pymupdf.Widget()
        field.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        field.field_name = "nombre"
        field.rect = pymupdf.Rect(100, 600, 300, 620)
        page.add_widget(field)
        page.insert_link(
            {"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(100, 650, 200, 670), "uri": "x:y"}
        )
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes and 0 in view._drawings)
    return view, path


def place(view, page: int, x: float, y: float) -> QPoint:
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def click(view, x: float, y: float) -> None:
    spot = place(view, 0, x, y)
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spot)
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spot)


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes and not view.saving)


def types_in(path) -> list[str]:  # kinds, once each
    """Every annotation of the first page, fields and links too."""
    with pymupdf.open(path) as doc:
        listed = doc.xref_get_key(doc[0].xref, "Annots")[1]
        xrefs = [int(word) for word in listed.strip("[]").split()[::3]]
        return sorted({doc.xref_get_key(xref, "Subtype")[1].lstrip("/") for xref in xrefs})


def test_fields_and_links_are_not_offered(foreign):
    view, _ = foreign
    kinds = sorted(item.kind for item in view.drawings_of(0))
    assert kinds == ["highlight", "ink", OTHER]


def test_picked_and_supr_takes_it_away_and_undo_brings_it_back(foreign, wait_until):
    view, _ = foreign
    click(view, 450, 525)  # the stamp
    picked = view.picked_item()
    assert picked is not None and picked.kind == OTHER
    QTest.keyClick(view, Qt.Key.Key_Delete)
    settle(view, wait_until)
    assert OTHER not in {item.kind for item in view.drawings_of(0)}
    assert view.modified
    assert view.undo()
    settle(view, wait_until)
    assert OTHER in {item.kind for item in view.drawings_of(0)}


def test_the_eraser_takes_a_highlight_of_another_program(window, foreign, wait_until):
    view, _ = foreign
    window.use_writing_tool(ERASER)
    click(view, 200, 307)
    settle(view, wait_until)
    assert "highlight" not in {item.kind for item in view.drawings_of(0)}


def test_the_right_button_offers_to_take_it_away(foreign, wait_until):
    view, _ = foreign
    menu = view.context_menu(place(view, 0, 450, 525))
    names = [action.text() for action in menu.actions()]
    assert "Borrar la anotación" in names
    assert "Copiar la anotación" not in names, "only taken away, not copied"
    next(action for action in menu.actions() if action.text() == "Borrar la anotación").trigger()
    settle(view, wait_until)
    assert OTHER not in {item.kind for item in view.drawings_of(0)}


def test_saved_without_it_and_the_rest_is_untouched(window, foreign, wait_until):
    view, path = foreign
    click(view, 150, 400)  # the stroke
    assert view.remove_picked()
    settle(view, wait_until)
    assert window.save_document()
    settle(view, wait_until)
    assert types_in(path) == ["Highlight", "Link", "Stamp", "Widget"]
    with pymupdf.open(path) as doc:  # really gone from the file, not only hidden
        assert not any("/Ink" in doc.xref_object(xref) for xref in range(1, doc.xref_length()))
    # Deshacer still puts it back, exactly as it was, from the copy the order keeps.
    assert view.undo()
    settle(view, wait_until)
    assert "ink" in {item.kind for item in view.drawings_of(0)}
    window.save_document()
    settle(view, wait_until)
    assert types_in(path) == ["Highlight", "Ink", "Link", "Stamp", "Widget"]
    assert view.redo()  # and away again
    settle(view, wait_until)
    assert "ink" not in {item.kind for item in view.drawings_of(0)}


def test_taken_away_saved_by_itself_and_undone(window, foreign, wait_until):
    """With "guardar solo mientras trabajo": what another program made is
    never lost for good by a save the user did not ask for."""
    from app.core import save_settings

    view, path = foreign
    window.settings.set(save_settings.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    click(view, 450, 525)  # the stamp
    assert view.remove_picked()
    settle(view, wait_until)
    window._autosave()
    settle(view, wait_until)
    assert "Stamp" not in types_in(path)
    assert view.undo()
    settle(view, wait_until)
    window._autosave()
    settle(view, wait_until)
    assert types_in(path) == ["Highlight", "Ink", "Link", "Stamp", "Widget"]


def test_deshacer_puts_it_back_before_saving(window, foreign, wait_until):
    view, path = foreign
    click(view, 150, 400)  # the stroke
    assert view.remove_picked()
    settle(view, wait_until)
    assert view.undo()
    settle(view, wait_until)
    assert "ink" in {item.kind for item in view.drawings_of(0)}
    window.save_document()
    settle(view, wait_until)
    assert types_in(path) == ["Highlight", "Ink", "Link", "Stamp", "Widget"]


def test_it_is_written_in_the_journal(window, foreign, wait_until):
    view, _ = foreign
    click(view, 450, 525)
    view.remove_picked()
    settle(view, wait_until)
    assert view.journal is not None and view.journal.count == 1


def test_too_big_to_copy_is_never_saved_by_itself_and_asked_first(
    window, sample, tmp_path, wait_until
):
    """An attachment of several megabytes left by another program: no copy is
    kept, so saving without it cannot be undone. Never saved by itself, and
    asked before saving by hand."""
    import os

    from app.core import save_settings
    from app.core.foreign import MAX_KEPT_BYTES
    from app.ui.main_window import FOREIGN_LOST

    path = tmp_path / "adjunto.pdf"
    with pymupdf.open(sample("boe.pdf")) as doc:
        doc[0].add_file_annot((450, 525), os.urandom(MAX_KEPT_BYTES + 1000), "grande.bin")
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._drawings)
    window.settings.set(save_settings.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    click(view, 452, 527)  # the attachment
    assert view.remove_picked()
    settle(view, wait_until)
    assert view.loses_undo_on_save
    window._autosave()
    settle(view, wait_until)
    assert "FileAttachment" in types_in(path), "not saved by itself"
    window.save_warning_answer = "cancel"
    assert not window.save_document()
    assert FOREIGN_LOST in window._save_warnings(window.current_document)
    window.save_warning_answer = "save_here"
    assert window.save_document()
    settle(view, wait_until)
    assert "FileAttachment" not in types_in(path) and not view.loses_undo_on_save
