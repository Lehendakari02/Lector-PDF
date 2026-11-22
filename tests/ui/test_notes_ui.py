"""Tests for sticky notes and text boxes in the window."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from app.core.notes import MONO, NOTE, SERIF, TEXT_BOX
from app.ui.features import Mode
from app.ui.main_window import MainWindow


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
        return view, path

    return open_it


def place(view, page: int, x: float, y: float) -> QPoint:
    """Where a point of a page is in the window."""
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def click(view, where: QPoint) -> None:
    QTest.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, where
    )


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view._asked_notes)


def write(view, text: str, wait_until) -> None:
    """Type in the open panel and keep it."""
    view.note_panel.edit.setPlainText(text)
    view.note_panel.save()
    settle(view, wait_until)


def in_file(path, page: int = 0):
    with pymupdf.open(path) as doc:
        sheet = doc[page]
        return [(a.type[1], a.info["content"]) for a in sheet.annots() or ()]


def save(window, wait_until) -> None:
    assert window.save_document()
    wait_until(lambda: not window.pdf_view.saving and not window.pdf_view.modified)


# ---- notes -----------------------------------------------------------------------


def test_the_note_tool_stays_in_hand_until_it_is_put_down(window, opened):
    view, _ = opened()
    window.set_mode(Mode.STUDY)
    action = window.feature_actions["note"]
    action.trigger()
    assert view.markup_tool == NOTE and action.isChecked()
    assert "nota" in window.statusBar().currentMessage()
    action.trigger()
    assert view.markup_tool == "" and not action.isChecked()
    action.trigger()
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.markup_tool == ""


def test_without_a_document_the_tools_say_so(window):
    window.feature_actions["note"].trigger()
    assert "Abre primero" in window.statusBar().currentMessage()
    assert window.pdf_view.markup_tool == ""


def test_a_click_with_the_note_tool_opens_the_panel_and_saving_puts_the_note(
    window, opened, wait_until
):
    view, path = opened()
    window.use_writing_tool(NOTE)
    click(view, place(view, 0, 300, 200))
    panel = view.note_panel
    assert panel is not None and panel.isVisible() and not panel.remove_button.isVisible()
    assert view.notes_of(0) == [], "nothing is put until it is written"
    write(view, "Repasar ¿año? ñ", wait_until)
    assert view.note_panel is None
    (note,) = view.notes_of(0)
    assert (note.kind, note.text) == (NOTE, "Repasar ¿año? ñ")
    x0, y0, x1, y1 = note.rect
    assert x0 < 300 < x1 and y0 < 200 < y1, "the icon is where the click was"
    assert view.modified and view.can_undo and view.markup_tool == NOTE
    assert in_file(path) == [], "the file does not change until it is saved"
    save(window, wait_until)
    assert in_file(path) == [("Text", "Repasar ¿año? ñ")]


def test_cancelling_or_writing_nothing_puts_no_note(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(NOTE)
    click(view, place(view, 0, 300, 200))
    view.note_panel.edit.setPlainText("me arrepiento")
    QTest.keyClick(view.note_panel.edit, Qt.Key.Key_Escape)
    assert view.note_panel is None
    click(view, place(view, 0, 300, 200))
    view.note_panel.edit.setPlainText("   ")
    view.note_panel.save()
    settle(view, wait_until)
    assert view.notes_of(0) == [] and not view.modified


def test_a_click_outside_keeps_what_was_being_written(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(NOTE)
    click(view, place(view, 0, 300, 200))
    view.note_panel.edit.setPlainText("no perder esto")
    click(view, place(view, 0, 100, 500))
    settle(view, wait_until)
    assert view.note_panel is None, "that click only closes the panel"
    assert [note.text for note in view.notes_of(0)] == ["no perder esto"]


def test_ctrl_enter_saves(window, opened, wait_until):
    view, _ = opened()
    window.use_writing_tool(NOTE)
    click(view, place(view, 0, 300, 200))
    view.note_panel.edit.setPlainText("rápido")
    QTest.keyClick(view.note_panel.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    settle(view, wait_until)
    assert [note.text for note in view.notes_of(0)] == ["rápido"]


def test_a_click_on_a_note_opens_it_whatever_is_in_hand(window, opened, wait_until):
    view, _ = opened()
    assert view.put_note(0, 300, 200, "la primera")
    settle(view, wait_until)
    click(view, place(view, 0, 300, 200))
    panel = view.note_panel
    assert panel is not None and panel.edit.toPlainText() == "la primera"
    assert panel.remove_button.isVisible() and not panel.edit.isReadOnly()
    write(view, "cambiada", wait_until)
    assert [note.text for note in view.notes_of(0)] == ["cambiada"]
    view.undo()
    settle(view, wait_until)
    assert [note.text for note in view.notes_of(0)] == ["la primera"]
    view.redo()
    settle(view, wait_until)
    assert [note.text for note in view.notes_of(0)] == ["cambiada"]


def test_borrar_takes_the_note_away_and_undo_brings_it_back(window, opened, wait_until):
    view, _ = opened()
    view.put_note(0, 300, 200, "sobra")
    settle(view, wait_until)
    click(view, place(view, 0, 300, 200))
    view.note_panel.remove_button.click()
    settle(view, wait_until)
    assert view.notes_of(0) == [] and view.note_panel is None
    view.undo()
    settle(view, wait_until)
    assert [note.text for note in view.notes_of(0)] == ["sobra"]


def test_emptying_a_note_removes_it(window, opened, wait_until):
    view, _ = opened()
    view.put_note(0, 300, 200, "sobra")
    settle(view, wait_until)
    click(view, place(view, 0, 300, 200))
    write(view, "", wait_until)
    assert view.notes_of(0) == []


def test_the_note_has_the_colour_chosen_for_the_tool(window, opened, wait_until):
    view, _ = opened()
    window.set_marker_color(NOTE, (0.47, 0.82, 1.0))
    assert view.markup_tool == NOTE, "choosing the colour takes the tool"
    view.put_note(0, 300, 200, "azul")
    settle(view, wait_until)
    (note,) = view.notes_of(0)
    assert all(abs(a - b) < 0.01 for a, b in zip(note.color, (0.47, 0.82, 1.0), strict=True))


def test_a_note_of_another_program_can_be_read_and_removed_but_not_changed(
    window, sample, tmp_path, wait_until
):
    path = tmp_path / "ajeno.pdf"
    with pymupdf.open(sample("boe.pdf")) as doc:
        page = doc[0]
        page.add_text_annot((300, 200), "de otro programa").update()
        doc.save(path)
    window.show_problem_dialogs = False
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and view._notes.get(0))
    (note,) = view.notes_of(0)
    assert not note.ours
    click(view, place(view, 0, 306, 206))
    panel = view.note_panel
    assert panel.edit.isReadOnly() and panel.edit.toPlainText() == "de otro programa"
    assert not panel.save_button.isVisible() and not panel.remove_button.isHidden()
    assert "borrar" in panel.findChild(QLabel).text()
    panel.cancel()
    assert not view.change_note(note, "otra cosa")
    assert not view.modified
    assert view.remove_note(note)
    wait_until(lambda: not view._changing and view._notes.get(0) == [])
    assert view.undo()
    wait_until(lambda: not view._changing and len(view._notes.get(0) or ()) == 1)


# ---- text boxes ------------------------------------------------------------------


def test_writing_text_on_the_page(window, opened, wait_until):
    view, path = opened()
    window.set_text_font(SERIF)
    window.set_text_size(18)
    window.set_marker_color(TEXT_BOX, (0.85, 0.15, 0.15))
    assert view.markup_tool == TEXT_BOX
    click(view, place(view, 0, 60, 300))
    write(view, "Esquema:\n· igualdad", wait_until)
    (box,) = view.notes_of(0)
    assert (box.kind, box.text, box.font, box.size) == (TEXT_BOX, "Esquema:\n· igualdad", SERIF, 18)
    assert abs(box.rect[0] - 60) < 1, "it starts at the click"
    assert box.rect[1] < 300 < box.rect[1] + 18, "and its first line is at the height of the click"
    save(window, wait_until)
    assert in_file(path) == [("FreeText", "Esquema:\n· igualdad")]


def test_the_page_is_drawn_again_with_the_text(window, opened, wait_until):
    view, _ = opened()
    before = bytes(view._cache[0][1].constBits())
    view.put_text_box(0, 60, 300, "se ve")
    settle(view, wait_until)
    wait_until(lambda: 0 not in view._stale)
    assert bytes(view._cache[0][1].constBits()) != before


def test_a_text_is_opened_with_the_tool_or_with_a_double_click(window, opened, wait_until):
    view, _ = opened()
    view.put_text_box(0, 60, 300, "antes")
    settle(view, wait_until)
    inside = place(view, 0, 70, 308)
    click(view, inside)
    assert view.note_panel is None, "a single click without the tool does nothing to it"
    QTest.mouseDClick(
        view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, inside
    )
    assert view.note_panel is not None and view.note_panel.edit.toPlainText() == "antes"
    write(view, "después", wait_until)
    assert [box.text for box in view.notes_of(0)] == ["después"]
    window.use_writing_tool(TEXT_BOX)
    click(view, inside)
    assert view.note_panel.edit.toPlainText() == "después"
    view.note_panel.cancel()


def test_changing_a_text_keeps_its_own_look(window, opened, wait_until):
    view, _ = opened()
    window.set_text_font(MONO)
    view.put_text_box(0, 60, 300, "en courier")
    settle(view, wait_until)
    window.set_text_font(SERIF)  # the tool changes; what is written does not
    (box,) = view.notes_of(0)
    assert view.change_note(box, "sigue en courier")
    settle(view, wait_until)
    (box,) = view.notes_of(0)
    assert (box.font, box.text) == (MONO, "sigue en courier")


def test_the_arrow_of_the_text_tool_offers_font_and_size(window, opened):
    opened()
    assert set(window.text_font_actions) == {"sans", "serif", "mono"}
    assert window.text_font_actions["sans"].isChecked()
    window.text_size_actions[24].trigger()
    assert window.pdf_view.text_size == 24 and window.text_size_actions[24].isChecked()
    assert window.pdf_view.markup_tool == TEXT_BOX
    assert not window.color_menus[TEXT_BOX].opacity_slider.isVisibleTo(window.color_menus[TEXT_BOX])


def test_the_choices_are_remembered_next_time(window, settings, opened, qt_app):
    opened()
    window.set_text_font(SERIF)
    window.set_text_size(14)
    window.set_marker_color(NOTE, (0.47, 0.82, 1.0))
    again = MainWindow(settings)
    try:
        assert (again.marker_styles.text_font, again.marker_styles.text_size) == (SERIF, 14)
        assert again.pdf_view.text_font == SERIF
        assert abs(again.pdf_view.note_color[0] - 0.47) < 0.01
    finally:
        again.shutdown_documents()
        again.deleteLater()


# ---- with everything else --------------------------------------------------------


def test_the_right_click_menu_offers_to_edit_and_remove(window, opened, wait_until):
    view, _ = opened()
    view.put_note(0, 300, 200, "con menú")
    settle(view, wait_until)
    menu = view.context_menu(place(view, 0, 300, 200))
    actions = menu.actions()
    assert [action.text() for action in actions[:2]] == ["Editar la nota…", "Borrar la nota"]
    actions[1].trigger()
    settle(view, wait_until)
    assert view.notes_of(0) == []
    elsewhere = view.context_menu(place(view, 0, 100, 600))
    assert elsewhere.actions()[0].text() == "Copiar"


def test_notes_come_back_after_a_power_cut(window, opened, wait_until, settings, qt_app):
    view, path = opened()
    view.put_note(0, 300, 200, "no perder")
    view.put_text_box(0, 60, 300, "tampoco esto")
    settle(view, wait_until)
    window.shutdown_documents()
    view.journal = None
    again = MainWindow(settings)
    try:
        again.show_problem_dialogs = False
        again.restore_session()
        again.recovery_answer = True
        assert again.offer_recovery() == 1
        other = again.pdf_view
        wait_until(lambda: other._changes == 2 and not other._changing and not other._asked_notes)
        assert sorted(note.text for note in other.notes_of(0)) == ["no perder", "tampoco esto"]
    finally:
        again.unsaved_answer = "discard"
        again.close()
        again.deleteLater()


def test_the_helper_dying_loses_no_note(window, opened, wait_until):
    view, path = opened()
    view.put_note(0, 300, 200, "sobrevive")
    settle(view, wait_until)
    restarts = view.service.restarts
    import os
    import signal

    os.kill(view.service.process_id, signal.SIGTERM)
    wait_until(lambda: view.service.restarts > restarts)
    view._want_notes(0, again=True)
    settle(view, wait_until)
    assert [note.text for note in view.notes_of(0)] == ["sobrevive"]
    save(window, wait_until)
    assert in_file(path) == [("Text", "sobrevive")]


# ---- what is being written, after a power cut ---------------------------------


def test_a_note_being_written_comes_back_after_a_power_cut(
    window, opened, wait_until, settings, qt_app
):
    view, path = opened()
    before = path.read_bytes()
    view.start_note(NOTE, 0, 300, 200, QPoint(40, 40))
    view.note_panel.edit.setPlainText("a medio escribir")
    assert view._draft_timer.isActive()
    view.write_draft()  # what the timer does every few seconds
    assert view.journal.draft_file.exists()
    assert path.read_bytes() == before, "the PDF is never written"
    assert not view.modified and view.notes_of(0) == [], "not a change yet"
    window.shutdown_documents()
    view.journal = None
    again = MainWindow(settings)
    try:
        again.show_problem_dialogs = False
        again.restore_session()
        again.recovery_answer = True
        assert again.offer_recovery() == 1
        other = again.pdf_view
        wait_until(lambda: other._changes == 1 and not other._changing and not other._asked_notes)
        assert [note.text for note in other.notes_of(0)] == ["a medio escribir"]
        assert not other.journal.draft_file.exists()
        assert len(other.journal.entries()) == 1
    finally:
        again.unsaved_answer = "discard"
        again.close()
        again.deleteLater()


def test_the_draft_goes_when_the_note_is_kept_or_cancelled(window, opened, wait_until):
    view, path = opened()
    view.start_note(NOTE, 0, 300, 200, QPoint(40, 40))
    view.note_panel.edit.setPlainText("se queda")
    view.write_draft()
    assert view.journal.draft_file.exists()
    view.note_panel.save()
    settle(view, wait_until)
    assert not view.journal.draft_file.exists()
    assert not view._draft_timer.isActive()
    assert len(view.journal.entries()) == 1
    view.start_note(NOTE, 0, 300, 400, QPoint(40, 40))
    view.note_panel.edit.setPlainText("no se queda")
    view.write_draft()
    view.note_panel.cancel()
    assert not view.journal.draft_file.exists()
    assert len(view.journal.entries()) == 1 and len(view.notes_of(0)) == 1


def test_a_text_changed_on_the_page_is_drafted_as_a_change(window, opened, wait_until):
    view, path = opened()
    assert view.put_text_box(0, 60, 300, "antes")
    settle(view, wait_until)
    view.open_note(view.notes_of(0)[0])
    view.note_panel.edit.setPlainText("después")
    view.write_draft()
    drafted = view.journal.draft()
    assert type(drafted).__name__ == "Replace" and drafted.new.text == "después"
    assert [note.text for note in view.notes_of(0)] == ["antes"], "nothing done yet"
    view.note_panel.edit.setPlainText("antes")
    view.write_draft()
    assert view.journal.draft() is None, "unchanged: nothing to bring back"
    view.close_note_panel()


def test_the_draft_is_written_again_only_when_what_is_written_changes(window, opened):
    view, _path = opened()
    view.start_note(NOTE, 0, 300, 200, QPoint(40, 40))
    view.note_panel.edit.setPlainText("una nota")
    view.write_draft()
    first = view.journal.draft_file.stat().st_mtime_ns
    view.journal.draft_file.write_text("cambiado a mano")  # to see whether it is written
    view.write_draft()
    assert view.journal.draft_file.read_text() == "cambiado a mano", "nothing new to write"
    view.note_panel.edit.setPlainText("una nota más larga")
    view.write_draft()
    assert "más larga" in view.journal.draft_file.read_text(encoding="utf-8")
    assert view.journal.draft_file.stat().st_mtime_ns >= first
    view.close_note_panel(keep=False)
