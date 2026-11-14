"""Tests for the earlier versions of a PDF in the window."""

import shutil

import pymupdf
import pytest

from app.core.versions import Versions
from app.ui.main_window import MainWindow
from app.ui.versions_dialog import RESTORE, VIEW, VersionsDialog


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    def open_copy(name: str = "texto-partido.pdf", copy: str | None = None):
        window.show_problem_dialogs = False
        path = tmp_path / (copy or name)
        if not path.exists():
            shutil.copy(sample(name), path)
        assert window.open_document(path)
        wait_until(lambda: 0 in window.pdf_view._texts)
        return path

    return open_copy


def mark(window, wait_until, first: int = 0) -> None:
    view = window.pdf_view
    before = view._changes
    view.select((0, first), (0, first + 10))
    assert view.mark_selection("highlight")
    wait_until(lambda: view._changes > before and not view._changing)


def save(window, wait_until) -> None:
    assert window.save_document()
    wait_until(lambda: not window.pdf_view.saving)


def marks_in(path) -> int:
    with pymupdf.open(path) as doc:
        return sum(len(list(page.annots() or ())) for page in doc)


def test_the_versions_live_next_to_the_settings(window, settings):
    assert window.versions.folder == settings.path.parent / "versiones"


def test_the_first_save_keeps_how_the_file_was(window, opened, wait_until):
    path = opened()
    original = path.read_bytes()
    assert window.versions.of(path) == []
    mark(window, wait_until)
    save(window, wait_until)
    (version,) = window.versions.of(path)
    assert version.file.read_bytes() == original
    assert marks_in(path) == 1 and marks_in(version.file) == 0


def test_later_saves_in_the_same_session_keep_nothing_more(window, opened, wait_until):
    path = opened()
    for first in (0, 30, 60):
        mark(window, wait_until, first)
        save(window, wait_until)
    assert len(window.versions.of(path)) == 1


def test_each_session_keeps_its_own_version(window, opened, wait_until, settings, qt_app):
    path = opened()
    mark(window, wait_until)
    save(window, wait_until)
    window.close()
    again = MainWindow(settings)
    again.show_problem_dialogs = False
    assert again.open_document(path)
    wait_until(lambda: 0 in again.pdf_view._texts)
    mark(again, wait_until, 30)
    save(again, wait_until)
    assert [marks_in(v.file) for v in again.versions.of(path)] == [1, 0]


def test_save_as_keeps_the_file_it_is_about_to_replace(window, opened, wait_until, tmp_path):
    path = opened()
    other = tmp_path / "ya-existia.pdf"
    other.write_bytes(path.read_bytes())
    mark(window, wait_until)
    assert window.save_document_as(other)
    wait_until(lambda: not window.pdf_view.saving)
    assert len(window.versions.of(other)) == 1
    assert window.versions.of(path) == [], "the original was not touched"
    new = tmp_path / "nuevo.pdf"
    assert window.save_document_as(new)
    wait_until(lambda: not window.pdf_view.saving)
    assert window.versions.of(new) == [], "a file that did not exist has nothing to keep"


def test_saving_goes_on_when_the_version_cannot_be_kept(window, opened, wait_until, tmp_path):
    path = opened()
    blocked = tmp_path / "archivo"
    blocked.write_text("a file, not a folder")
    window.versions = Versions(blocked / "versiones")
    mark(window, wait_until)
    save(window, wait_until)
    assert marks_in(path) == 1
    message = window.statusBar().currentMessage()
    assert "Guardado" in message and "versión anterior" in message


def test_restoring_brings_the_document_back_and_can_be_undone(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    save(window, wait_until)
    (morning,) = window.versions.of(path)
    window.restore_answer = True
    assert window.restore_version(morning)
    assert marks_in(path) == 0
    assert window.current_document.path == path, "the tab is open again on the restored file"
    assert not window.pdf_view.modified
    assert "ha vuelto" in window.statusBar().currentMessage()
    kept = [marks_in(v.file) for v in window.versions.of(path)]
    assert sorted(kept) == [0, 1], "how it was just before restoring is one more version"
    with_marks = next(v for v in window.versions.of(path) if marks_in(v.file) == 1)
    assert window.restore_version(with_marks)
    assert marks_in(path) == 1


def test_restoring_keeps_the_page_and_sets_unsaved_changes_aside(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    path = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), path)
    assert window.open_document(path)
    wait_until(lambda: 0 in window.pdf_view._texts)
    mark(window, wait_until)
    save(window, wait_until)
    mark(window, wait_until, 30)  # not saved
    window.pdf_view.scroll_to_page(9)
    (morning,) = window.versions.of(path)
    window.restore_answer = True
    assert window.restore_version(morning)
    wait_until(lambda: window.pdf_view.current_page == 9)
    assert len(window.journal.discarded()) == 1, "the unsaved change can still be recovered"


def test_saying_no_restores_nothing(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    save(window, wait_until)
    window.restore_answer = False
    assert window.restore_version(window.versions.of(path)[0]) is False
    assert marks_in(path) == 1 and len(window.documents) == 1


def test_a_version_that_is_gone_is_explained_and_the_document_stays(
    window, opened, wait_until, monkeypatch
):
    monkeypatch.setattr("app.ui.main_window.RESTORE_PAUSE", 0)
    path = opened()
    mark(window, wait_until)
    save(window, wait_until)
    (morning,) = window.versions.of(path)
    morning.file.unlink()
    window.restore_answer = True
    assert window.restore_version(morning) is False
    assert "No se ha podido restaurar" in window.statusBar().currentMessage()
    assert marks_in(path) == 1 and window.current_document.path == path


def test_looking_at_a_version_opens_it_apart_and_changes_nothing(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    save(window, wait_until)
    (morning,) = window.versions.of(path)
    assert window.view_version(morning)
    assert len(window.documents) == 2
    shown = window.current_document
    assert shown.path != path and "versión del" in shown.title
    assert marks_in(shown.path) == 0 and marks_in(path) == 1
    assert shown.path not in window.history.recent()
    assert window.history.session()[0] == [path], "it does not come back as a tab"


def test_the_menu_has_earlier_versions(window, opened):
    assert not window.versions_action.isEnabled(), "no document, nothing to show"
    opened()
    assert window.versions_action.isEnabled()
    file_menu = window.menuBar().actions()[0].menu()
    assert window.versions_action in file_menu.actions()


def test_the_list_of_versions(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    save(window, wait_until)
    versions = window.versions.of(path)
    dialog = VersionsDialog(path.name, versions)
    line = dialog.list.item(0).text()
    assert "hoy" in line and "KB" in line
    assert dialog.view_button.isEnabled() and dialog.restore_button.isEnabled()
    dialog.restore_button.click()
    assert dialog.action == RESTORE and dialog.chosen == versions[0]
    other = VersionsDialog(path.name, versions)
    other.view_button.click()
    assert other.action == VIEW
    closed = VersionsDialog(path.name, versions)
    closed.reject()
    assert closed.action == "" and closed.chosen is None


def test_the_list_when_there_are_no_versions(qt_app):
    dialog = VersionsDialog("tema.pdf", [])
    assert "Todavía no hay" in dialog.message.text()
    assert dialog.list.isHidden()
    assert not dialog.view_button.isEnabled() and not dialog.restore_button.isEnabled()
