"""Tests for the saving settings: closing without being asked, saving by itself,
how many versions and how many days."""

import shutil

import pymupdf
import pytest

from app.core import save_settings as ss
from app.core import saving
from app.ui.main_window import SAVE_HERE
from app.ui.unsaved_dialog import UnsavedDialog


@pytest.fixture
def opened(window, sample, tmp_path):
    def open_copy(name: str = "boe.pdf", copy: str | None = None):
        window.show_problem_dialogs = False
        path = tmp_path / (copy or name)
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        return path

    return open_copy


def marked(path) -> int:
    with pymupdf.open(path) as doc:
        return sum(len(list(page.annots() or ())) for page in doc)


def mark_something(window, wait_until) -> None:
    view = window.pdf_view
    wait_until(lambda: 0 in view._texts)
    view.select((0, 0), (0, 20))
    assert view.mark_selection("highlight")
    wait_until(lambda: view.modified and not view._changing)


def idle(window, wait_until) -> None:
    """The quiet time has passed (without waiting for it)."""
    window._autosave_timer.stop()
    window._autosave()
    wait_until(lambda: not any(page.view.saving for page in window.documents), seconds=60)


def _choose(box, value) -> None:
    box.setCurrentIndex(box.findData(value))
    box.activated.emit(box.currentIndex())


# ---- when closing -------------------------------------------------------------


def test_save_always_saves_and_closes_without_asking(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    window.settings.set(ss.CLOSE_SETTING, ss.SAVE)
    window.close_document()
    wait_until(lambda: not window.documents, seconds=60)
    assert marked(path) > 0


def test_save_always_still_asks_about_a_signed_pdf(window, opened):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    window.pdf_view.mark_modified()
    window.settings.set(ss.CLOSE_SETTING, ss.SAVE)
    window.close_document()  # nobody answers the warning: nothing is saved
    assert len(window.documents) == 1 and path.read_bytes() == before


def test_never_save_closes_and_keeps_the_changes_some_days(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    window.settings.set(ss.CLOSE_SETTING, ss.DISCARD)
    window.show_problem_dialogs = True  # a dialog here would hang the test
    window.close_document()
    assert not window.documents and marked(path) == 0
    (discarded,) = window.journal.discarded()
    assert discarded.path == path


def test_the_program_closes_saving_everything_without_asking(window, opened, wait_until):
    first = opened()
    mark_something(window, wait_until)
    second = opened("texto-partido.pdf")
    mark_something(window, wait_until)
    window.settings.set(ss.CLOSE_SETTING, ss.SAVE)
    window.close()
    wait_until(lambda: not window.isVisible(), seconds=60)
    assert marked(first) > 0 and marked(second) > 0


# ---- saving by itself -----------------------------------------------------------


def test_nothing_is_saved_by_itself_unless_asked_for(window, opened, wait_until):
    path = opened()
    mark_something(window, wait_until)
    assert not window._autosave_timer.isActive()
    idle(window, wait_until)
    assert marked(path) == 0 and window.pdf_view.modified


def test_it_saves_after_a_while_without_changes(window, opened, wait_until):
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    path = opened()
    assert not window._autosave_timer.isActive(), "nothing to save yet"
    mark_something(window, wait_until)
    assert window._autosave_timer.isActive()
    assert window._autosave_timer.interval() == 30_000
    assert marked(path) == 0, "never at once, while editing"
    idle(window, wait_until)
    assert marked(path) > 0 and not window.pdf_view.modified


def test_every_change_starts_the_quiet_time_again(window, opened, wait_until):
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.settings.set(ss.AUTOSAVE_SECONDS_SETTING, 10)
    window.apply_save_settings()
    opened()
    mark_something(window, wait_until)
    wait_until(lambda: window._autosave_timer.remainingTime() < 9_000)
    window.pdf_view.undo()
    wait_until(lambda: window._autosave_timer.remainingTime() > 9_000, seconds=5)


def test_it_saves_when_leaving_the_tab(window, opened, wait_until):
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    first = opened()
    mark_something(window, wait_until)
    opened("texto-partido.pdf")  # another tab comes to the front
    wait_until(lambda: not window.documents[0].view.saving, seconds=60)
    assert marked(first) > 0 and not window.documents[0].view.modified


def test_a_signed_pdf_is_never_saved_by_itself(window, opened, wait_until):
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    path = opened("firmado.pdf")
    before = path.read_bytes()
    window.pdf_view.mark_modified()
    idle(window, wait_until)
    assert path.read_bytes() == before and window.pdf_view.modified
    assert "firmado" in window.statusBar().currentMessage()
    # Once the user has said "save here anyway", it is a file like any other.
    window.save_warning_answer = SAVE_HERE
    assert window.save_document()
    wait_until(lambda: not window.pdf_view.saving)
    window.save_warning_answer = None
    window.pdf_view.mark_modified()
    idle(window, wait_until)
    assert not window.pdf_view.modified


def test_closing_with_saving_by_itself_saves_without_asking(window, opened, wait_until):
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.settings.set(ss.CLOSE_SETTING, ss.DISCARD)  # does not count meanwhile
    window.apply_save_settings()
    path = opened()
    mark_something(window, wait_until)
    window.close_document()
    wait_until(lambda: not window.documents, seconds=60)
    assert marked(path) > 0


def test_a_failed_saving_by_itself_is_explained_once(window, opened, wait_until, monkeypatch):
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, "boe.pdf")
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    opened()
    page = window.current_document
    mark_something(window, wait_until)
    idle(window, wait_until)
    assert page.autosave_failed and window.pdf_view.modified
    assert "No se ha podido guardar" in window.statusBar().currentMessage()
    window.show_problem_dialogs = True  # a second window here would hang the test
    idle(window, wait_until)
    assert window.pdf_view.modified
    window.show_problem_dialogs = False


def test_it_waits_while_a_question_is_open(window, opened, wait_until, qt_app):
    window.settings.set(ss.AUTOSAVE_SETTING, True)
    window.apply_save_settings()
    path = opened()
    mark_something(window, wait_until)
    dialog = UnsavedDialog(["boe.pdf"], window)
    dialog.open()
    qt_app.processEvents()
    window._autosave_timer.stop()
    window._autosave()
    assert not window.pdf_view.saving and window._autosave_timer.isActive()
    dialog.reject()
    dialog.deleteLater()
    idle(window, wait_until)
    assert marked(path) > 0


# ---- versions and days ----------------------------------------------------------


def test_the_limits_of_the_versions_follow_the_settings(window):
    assert window.versions.max_per_document == 10
    window.settings.set(ss.VERSIONS_COUNT_SETTING, 3)
    window.settings.set(ss.VERSIONS_ROOM_SETTING, 250)
    window.apply_save_settings()
    assert window.versions.max_per_document == 3
    assert window.versions.max_total_bytes == 250 * 1024 * 1024


def test_the_question_says_the_days_chosen(window, qt_app):
    dialog = UnsavedDialog(["a.pdf"], window, days=1)
    texts = " ".join(label.text() for label in dialog.findChildren(type(dialog.question)))
    assert "1 día " in texts
    dialog.deleteLater()


# ---- the settings window --------------------------------------------------------


def test_the_settings_window_has_a_tab_for_saving(window):
    dialog = window.open_settings()
    names = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert names[:2] == ["General", "Guardado"]
    assert dialog.close_box.currentData() == ss.ASK
    assert not dialog.autosave_box.isChecked()
    assert not dialog.autosave_seconds_box.isEnabled()
    assert dialog.versions_count_box.currentData() == 10
    assert dialog.versions_room_box.currentData() == 1024
    assert dialog.discarded_days_box.currentData() == 7
    dialog.close()


def test_what_is_chosen_is_kept_and_followed_at_once(window, opened, wait_until):
    opened()
    mark_something(window, wait_until)
    dialog = window.open_settings()
    _choose(dialog.close_box, ss.DISCARD)
    _choose(dialog.versions_count_box, 20)
    _choose(dialog.discarded_days_box, 30)
    assert window.settings.get(ss.CLOSE_SETTING) == ss.DISCARD
    assert window.versions.max_per_document == 20
    assert "30 días" in dialog.close_note.text()
    dialog.autosave_box.setChecked(True)
    assert window.settings.get(ss.AUTOSAVE_SETTING) is True
    assert window._autosave_timer.isActive(), "there were changes waiting"
    assert not dialog.close_box.isEnabled() and dialog.autosave_seconds_box.isEnabled()
    _choose(dialog.autosave_seconds_box, 60)
    assert window._autosave_timer.interval() == 60_000
    dialog.autosave_box.setChecked(False)
    assert not window._autosave_timer.isActive() and dialog.close_box.isEnabled()
    dialog.close()
