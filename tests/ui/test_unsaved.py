"""Tests for closing with changes not saved: Guardar / No guardar / Cancelar."""

import shutil

import pymupdf
import pytest

from app.core import saving
from app.ui.unsaved_dialog import CANCEL, DISCARD, SAVE, UnsavedDialog


@pytest.fixture
def opened(window, sample, tmp_path):
    """Open a copy of a sample in the window, free to be saved over."""

    def open_copy(name: str = "boe.pdf", copy: str | None = None):
        window.show_problem_dialogs = False
        path = tmp_path / (copy or name)
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        return path

    return open_copy


def marked(path) -> int:
    """How many marks the file on disk has."""
    with pymupdf.open(path) as doc:
        return sum(len(list(page.annots() or ())) for page in doc)


def listen_to_the_question(window) -> list:
    """The list where the names it asks about are noted, each time it asks."""
    asked = []
    ask = window._ask_unsaved

    def noted(pages):
        asked.append([page.title for page in pages])
        return ask(pages)

    window._ask_unsaved = noted
    return asked


def mark_something(window, wait_until) -> None:
    view = window.pdf_view
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 20))
    assert view.mark_selection("highlight")
    wait_until(lambda: view.modified and not view._changing)


# ---- the dialog itself ---------------------------------------------------


def test_the_dialog_for_one_document(qt_app):
    dialog = UnsavedDialog(["tema-5.pdf"])
    assert "tema-5.pdf" in dialog.question.text()
    assert dialog.names.isHidden()
    assert dialog.save_button.text().replace("&", "") == "Guardar"
    assert dialog.save_button.isDefault()
    assert dialog.choice == CANCEL, "closing it with the X or Esc is Cancelar"
    dialog.discard_button.click()
    assert dialog.choice == DISCARD


def test_the_dialog_for_several_documents(qt_app):
    dialog = UnsavedDialog(["tema-5.pdf", "ley.pdf"])
    assert "2" in dialog.question.text()
    assert not dialog.names.isHidden() and dialog.names.count() == 2
    assert dialog.save_button.text().replace("&", "") == "Guardar todos"
    dialog.save_button.click()
    assert dialog.choice == SAVE
    again = UnsavedDialog(["a.pdf", "b.pdf"])
    again.cancel_button.click()
    assert again.choice == CANCEL
    escaped = UnsavedDialog(["a.pdf"])
    escaped.reject()
    assert escaped.choice == CANCEL


# ---- what is always in sight ---------------------------------------------


def test_the_state_is_always_in_sight(window, opened, wait_until):
    label = window.save_state_label
    assert label.text() == "", "nothing open, nothing to say"
    opened()
    assert label.text() == "Guardado" and not label.property("pending")
    window.pdf_view.mark_modified()
    assert label.text() == "Cambios sin guardar" and label.property("pending")
    window.save_document()
    assert label.text() == "Guardando…"
    wait_until(lambda: not window.pdf_view.saving)
    assert label.text() == "Guardado" and not label.property("pending")


def test_the_tab_shows_a_dot_while_there_are_changes(window, opened, wait_until):
    path = opened()
    tabs = window.document_tabs
    assert tabs.tabText(0) == path.name
    window.pdf_view.mark_modified()
    assert tabs.tabText(0) == f"{path.name} ●"
    window.save_document()
    wait_until(lambda: not window.pdf_view.saving)
    assert tabs.tabText(0) == path.name


def test_the_state_follows_the_tab_in_front(window, opened):
    opened()
    opened("formulario.pdf")
    window.pdf_view.mark_modified()
    assert window.save_state_label.text() == "Cambios sin guardar"
    window.document_tabs.setCurrentIndex(0)
    assert window.save_state_label.text() == "Guardado"


# ---- closing a tab -------------------------------------------------------


def test_a_tab_without_changes_closes_without_asking(window, opened):
    opened()
    window.unsaved_answer = CANCEL  # would keep it open if it asked
    window.close_document()
    assert not window.documents


def test_cancel_keeps_the_tab_and_its_changes(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    window.unsaved_answer = CANCEL
    window.close_document()
    assert len(window.documents) == 1 and window.pdf_view.modified
    assert marked(path) == 0


def test_do_not_save_closes_the_tab_and_leaves_the_file_alone(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    before = path.read_bytes()
    window.unsaved_answer = DISCARD
    window.close_document()
    assert not window.documents
    assert path.read_bytes() == before


def test_save_saves_and_then_closes_the_tab(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    window.unsaved_answer = SAVE
    window.close_document()
    wait_until(lambda: not window.documents)
    assert marked(path) > 0
    assert window.isVisible(), "only the tab closes"


def test_it_asks_about_the_tab_being_closed_not_the_one_in_front(window, opened, wait_until):
    opened()
    mark_something(window, wait_until)
    opened("formulario.pdf")
    asked = listen_to_the_question(window)
    window.unsaved_answer = CANCEL
    window.close_document(1)
    assert not asked and len(window.documents) == 1, "the clean one just closes"
    window.close_document(0)
    assert asked == [["boe.pdf"]] and len(window.documents) == 1


def test_if_it_cannot_be_saved_the_tab_stays_open(window, opened, wait_until, monkeypatch):
    # Set before opening, so that the helper of this document is born with it.
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, "boe.pdf")
    path = opened()
    mark_something(window, wait_until)
    window.unsaved_answer = SAVE
    window.close_document()
    wait_until(lambda: not window.pdf_view.saving, seconds=60)
    assert len(window.documents) == 1 and window.pdf_view.modified
    assert not window._saving_to_close
    assert marked(path) == 0


# ---- closing the program -------------------------------------------------


def test_the_program_closes_without_asking_when_all_is_saved(window, opened):
    opened()
    window.unsaved_answer = CANCEL
    window.close()
    assert not window.isVisible()


def test_cancel_keeps_the_program_open(window, opened, wait_until):
    opened()
    mark_something(window, wait_until)
    window.unsaved_answer = CANCEL
    window.close()
    assert window.isVisible() and window.pdf_view.modified


def test_it_asks_once_for_all_the_documents_with_changes(window, opened, wait_until):
    opened()
    mark_something(window, wait_until)
    opened("formulario.pdf")
    opened("boe.pdf", "otro.pdf")
    mark_something(window, wait_until)
    asked = listen_to_the_question(window)
    window.unsaved_answer = CANCEL
    window.close()
    assert asked == [["boe.pdf", "otro.pdf"]]
    assert window.isVisible()


def test_save_all_saves_every_one_and_then_closes(window, opened, wait_until):
    first = opened()
    mark_something(window, wait_until)
    second = opened("boe.pdf", "otro.pdf")
    mark_something(window, wait_until)
    window.unsaved_answer = SAVE
    window.close()
    wait_until(lambda: not window.isVisible())
    assert marked(first) > 0 and marked(second) > 0


def test_do_not_save_closes_the_program_and_leaves_the_files_alone(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    before = path.read_bytes()
    window.unsaved_answer = DISCARD
    window.close()
    assert not window.isVisible()
    assert path.read_bytes() == before


def test_if_one_cannot_be_saved_the_program_stays_open(window, opened, wait_until, monkeypatch):
    first = opened()
    mark_something(window, wait_until)
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, "otro.pdf")
    second = opened("boe.pdf", "otro.pdf")
    mark_something(window, wait_until)
    window.unsaved_answer = SAVE
    window.close()
    wait_until(lambda: not any(page.view.saving for page in window.documents), seconds=60)
    assert window.isVisible() and len(window.documents) == 2
    assert marked(first) > 0, "the one that could be saved is saved"
    assert marked(second) == 0 and window.documents[1].view.modified


def test_cancelling_also_cancels_a_restart_that_was_asked_for(window, opened, wait_until):
    opened()
    mark_something(window, wait_until)
    window.unsaved_answer = CANCEL
    window.restart_wanted = True
    window.after_exit_command = ["instalador.exe"]
    window.close()
    assert window.isVisible()
    assert not window.restart_wanted and window.after_exit_command is None


def test_an_update_waits_for_the_saving_and_then_goes_on(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    window.unsaved_answer = SAVE
    window.after_exit_command = ["instalador.exe"]
    window.close()
    assert window.isVisible(), "still saving"
    wait_until(lambda: not window.isVisible())
    assert window.after_exit_command == ["instalador.exe"]
    assert marked(path) > 0
