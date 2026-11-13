"""Tests for "Guardar" and "Guardar como" in the window."""

import shutil

import pymupdf
import pytest
from PySide6.QtGui import QKeySequence

from app import APP_NAME
from app.core import saving


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    """The window with a copy of a sample open, free to be saved over."""

    def open_copy(name: str = "boe.pdf"):
        window.show_problem_dialogs = False
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        return path

    return open_copy


def test_save_is_off_until_there_is_something_to_save(window, opened):
    assert not window.save_action.isEnabled() and not window.save_as_action.isEnabled()
    opened()
    assert not window.save_action.isEnabled(), "nothing has changed yet"
    assert not window.feature_actions["save"].isEnabled()
    assert window.save_as_action.isEnabled()
    assert window.feature_actions["save_as"].isEnabled()
    window.pdf_view.mark_modified()
    assert window.save_action.isEnabled() and window.feature_actions["save"].isEnabled()


def test_the_usual_shortcuts(window):
    assert window.save_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Save)
    assert window.save_as_action.shortcut() == QKeySequence("Ctrl+Shift+S")
    assert window.save_action in window.actions(), "works with the menu bar hidden"
    assert window.save_as_action in window.actions()


def test_the_buttons_sit_next_to_print(window):
    from app.ui.features import Mode, features_of

    names = [feature.id for feature in features_of(Mode.READ)]
    assert names[names.index("save") : names.index("save") + 3] == ["save", "save_as", "print"]


def test_saving_without_changes_says_so(window, opened):
    opened()
    assert window.save_document() is False
    assert "No hay cambios" in window.statusBar().currentMessage()


def test_saving_writes_the_file_and_turns_save_off_again(window, opened, wait_until):
    path = opened()
    view = window.pdf_view
    view.mark_modified()
    before = path.stat().st_mtime_ns
    assert window.save_document() is True
    assert not window.save_action.isEnabled(), "not twice at the same time"
    wait_until(lambda: not view.saving)
    assert not view.modified and not window.save_action.isEnabled()
    assert "Guardado" in window.statusBar().currentMessage()
    assert path.stat().st_mtime_ns != before
    with pymupdf.open(path) as doc:
        assert doc.page_count == view.page_count and not doc.is_repaired
    assert not saving.temp_path_for(path).exists()


def test_a_change_made_while_saving_is_still_pending(window, opened, wait_until):
    opened()
    view = window.pdf_view
    view.mark_modified()
    window.save_document()
    view.mark_modified()  # made after the save was asked for
    wait_until(lambda: not view.saving)
    assert view.modified and window.save_action.isEnabled()


def test_save_as_moves_the_tab_to_the_new_file(window, opened, tmp_path, wait_until):
    path = opened()
    original = path.read_bytes()
    view = window.pdf_view
    view.mark_modified()
    target = tmp_path / "otra carpeta" / "tema nuevo"
    target.parent.mkdir()
    assert window.save_document_as(target) is True
    wait_until(lambda: not view.saving)
    saved = target.with_name("tema nuevo.pdf")  # the ending is added
    assert saved.is_file() and path.read_bytes() == original
    page = window.current_document
    assert page.path == saved and not view.modified
    assert window.document_tabs.tabText(0) == "tema nuevo.pdf"
    assert window.document_tabs.tabToolTip(0) == str(saved)
    assert window.windowTitle() == f"tema nuevo.pdf – {APP_NAME}"
    assert window.history.recent()[0] == saved
    # The next plain save goes to the new file.
    view.mark_modified()
    window.save_document()
    wait_until(lambda: not view.saving)
    assert path.read_bytes() == original and not view.modified


def test_save_as_refuses_a_file_open_in_another_tab(window, opened, tmp_path):
    first = opened("boe.pdf")
    opened("formulario.pdf")
    assert window.save_document_as(first) is False
    assert "abierto" in window.statusBar().currentMessage()
    assert not window.pdf_view.saving


def test_save_as_over_its_own_file_is_a_plain_save(window, opened, wait_until):
    path = opened()
    view = window.pdf_view
    view.mark_modified()
    assert window.save_document_as(path) is True
    wait_until(lambda: not view.saving)
    assert window.current_document.path == path and not view.modified


def test_a_held_file_is_explained_and_nothing_is_lost(window, opened, wait_until, monkeypatch):
    path = opened()
    before = path.read_bytes()
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, path.name)
    window.current_document.view.service.shutdown()  # a new helper sees the test setting
    window.current_document.view.service._closing = False
    window.current_document.view.service.open(path)
    view = window.pdf_view
    view.mark_modified()
    window.save_document()
    wait_until(lambda: not view.saving, seconds=60)
    assert view.modified and window.save_action.isEnabled(), "still to be saved"
    message = window.statusBar().currentMessage()
    assert "No se ha podido guardar" in message and "Otro programa" in message
    assert path.read_bytes() == before


def test_each_tab_has_its_own_pending_changes(window, opened):
    opened("boe.pdf")
    opened("formulario.pdf")
    window.pdf_view.mark_modified()
    assert window.save_action.isEnabled()
    window.document_tabs.setCurrentIndex(0)
    assert not window.save_action.isEnabled()
    window.document_tabs.setCurrentIndex(1)
    assert window.save_action.isEnabled()
