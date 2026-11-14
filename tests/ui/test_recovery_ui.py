"""Tests for the recovery journal in the window: nothing is lost without saving."""

import shutil
import time
from contextlib import contextmanager

import pymupdf
import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from app.core.journal import Journal
from app.core.settings import Settings
from app.ui.main_window import MainWindow
from app.ui.recovery_dialog import RecoveryDialog
from app.ui.unsaved_dialog import CANCEL, DISCARD, SAVE


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    """Open a copy of a sample in the window, with the letters of its first page ready."""

    def open_copy(name: str = "texto-partido.pdf", copy: str | None = None, target=None):
        target = target or window
        target.show_problem_dialogs = False
        path = tmp_path / (copy or name)
        if not path.exists():
            shutil.copy(sample(name), path)
        assert target.open_document(path)
        view = target.pdf_view
        wait_until(lambda: 0 in view._texts)
        return path

    return open_copy


def mark(window, wait_until, first: int = 0, kind: str = "highlight") -> None:
    view = window.pdf_view
    before = view._changes
    view.select((0, first), (0, first + 10))
    assert view.mark_selection(kind)
    wait_until(lambda: view._changes > before and not view._changing)


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view.saving)


def marks_in(path) -> int:
    with pymupdf.open(path) as doc:
        return sum(len(list(page.annots() or ())) for page in doc)


def die(window) -> None:
    """The program goes away without closing anything: a power cut."""
    window.shutdown_documents()
    for page in window.documents:
        page.view.journal = None  # the dead one writes no more


@contextmanager
def started_again(settings, qt_app):
    """The program opened again after that, with the same settings and data folder."""
    window = MainWindow(Settings(settings.path))
    window.show_problem_dialogs = False
    window.show()
    qt_app.processEvents()
    try:
        yield window
    finally:
        window.unsaved_answer = DISCARD
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


# ---- the journal follows the work -----------------------------------------


def test_the_journal_lives_next_to_the_settings(window, settings):
    assert window.journal.folder == settings.path.parent / "diario"


def test_every_change_is_written_down_at_once_and_the_pdf_is_not_touched(
    window, opened, wait_until
):
    path = opened()
    before = path.read_bytes()
    assert window.journal.pending() == []
    mark(window, wait_until)
    mark(window, wait_until, 30, "underline")
    (pending,) = Journal(window.journal.folder).pending()
    assert pending.path == path and pending.count == 2
    assert path.read_bytes() == before


def test_undoing_leaves_nothing_to_recover(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    view = window.pdf_view
    view.undo()
    settle(view, wait_until)
    assert window.journal.pending() == []
    view.redo()
    settle(view, wait_until)
    assert window.journal.pending()[0].count == 1


def test_saving_empties_the_journal(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    window.save_document()
    settle(window.pdf_view, wait_until)
    assert window.journal.pending() == []
    assert not list(window.journal.folder.glob("*"))


def test_a_save_that_fails_keeps_the_journal(window, opened, wait_until, monkeypatch):
    from app.core import saving

    monkeypatch.setenv(saving.TEST_LOCKED_FILES, "texto-partido.pdf")
    opened()
    mark(window, wait_until)
    window.save_document()
    wait_until(lambda: not window.pdf_view.saving, seconds=60)
    assert window.journal.pending()[0].count == 1


def test_save_as_moves_the_journal_to_the_new_file(window, opened, wait_until, tmp_path):
    opened()
    mark(window, wait_until)
    copy = tmp_path / "copia.pdf"
    assert window.save_document_as(copy)
    settle(window.pdf_view, wait_until)
    assert window.journal.pending() == []
    mark(window, wait_until, 30)
    (pending,) = window.journal.pending()
    assert pending.path == copy


# ---- "No guardar" is not the end ------------------------------------------


def test_do_not_save_sets_the_changes_aside(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    window.unsaved_answer = DISCARD
    window.close_document()
    assert window.journal.pending() == [], "nothing to offer at the next start"
    (aside,) = window.journal.discarded()
    assert aside.path == path and aside.count == 1


def test_closing_the_program_without_saving_sets_them_aside_too(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    window.unsaved_answer = DISCARD
    window.close()
    assert window.journal.pending() == [] and len(window.journal.discarded()) == 1


def test_cancel_and_save_leave_nothing_aside(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    window.unsaved_answer = CANCEL
    window.close_document()
    assert window.journal.discarded() == [] and window.journal.pending()[0].count == 1
    window.unsaved_answer = SAVE
    window.close_document()
    wait_until(lambda: not window.documents)
    assert window.journal.discarded() == [] and window.journal.pending() == []


def test_discarded_changes_can_be_brought_back(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    mark(window, wait_until, 30, "strikeout")
    window.unsaved_answer = DISCARD
    window.close_document()
    assert marks_in(path) == 0
    (aside,) = window.journal.discarded()
    assert window.recover_changes(aside)
    view = window.pdf_view
    wait_until(lambda: view._changes == 2 and not view._changing)
    assert window.current_document.path == path, "the document was opened again"
    assert view.modified and view.can_undo, "they are back as changes not saved"
    assert "recuperados" in window.statusBar().currentMessage()
    assert window.journal.discarded() == []
    assert window.journal.pending()[0].count == 2, "and protected again from a power cut"
    assert marks_in(path) == 0, "the PDF only changes when it is saved"
    window.save_document()
    settle(view, wait_until)
    assert marks_in(path) == 2
    assert window.journal.pending() == []


def test_discarded_changes_join_the_ones_of_an_open_document(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    window.unsaved_answer = DISCARD
    window.close_document()
    opened()
    mark(window, wait_until, 30)
    (aside,) = window.journal.discarded()
    assert window.recover_changes(aside)
    view = window.pdf_view
    wait_until(lambda: view._changes == 2 and not view._changing)
    assert window.journal.pending()[0].count == 2
    window.save_document()
    settle(view, wait_until)
    assert marks_in(path) == 2


def test_a_recovered_change_can_be_undone(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    window.unsaved_answer = DISCARD
    window.close_document()
    window.recover_changes(window.journal.discarded()[0])
    view = window.pdf_view
    wait_until(lambda: view._changes == 1 and not view._changing)
    assert view.undo()
    settle(view, wait_until)
    assert window.journal.pending() == []


def test_changes_of_a_file_that_is_gone_are_kept(window, opened, wait_until):
    path = opened()
    mark(window, wait_until)
    window.unsaved_answer = DISCARD
    window.close_document()
    path.unlink()
    (aside,) = window.journal.discarded()
    assert window.recover_changes(aside) is False
    assert "No se encuentra" in window.statusBar().currentMessage()
    assert len(window.journal.discarded()) == 1


def test_the_menu_has_recover_discarded_changes(window):
    assert "descartados" in window.recover_discarded_action.text()
    file_menu = window.menuBar().actions()[0].menu()
    assert window.recover_discarded_action in file_menu.actions()


# ---- after a power cut ----------------------------------------------------


def test_after_a_power_cut_the_changes_come_back(window, opened, wait_until, settings, qt_app):
    path = opened()
    mark(window, wait_until)
    mark(window, wait_until, 30, "underline")
    mark(window, wait_until, 60, "strikeout")
    window.pdf_view.undo()  # the last one was taken back before the cut
    settle(window.pdf_view, wait_until)
    die(window)
    assert marks_in(path) == 0, "nothing had been saved"

    with started_again(settings, qt_app) as again:
        again.restore_session()
        assert again.current_document.path == path, "the tab is back"
        again.recovery_answer = True
        assert again.offer_recovery() == 1
        view = again.pdf_view
        wait_until(lambda: view._changes == 2 and not view._changing)
        assert view.modified and "Cambios sin guardar" in again.save_state_label.text()
        assert marks_in(path) == 0, "recovering does not save by itself"
        again.save_document()
        settle(view, wait_until)
        assert marks_in(path) == 2
        assert again.journal.pending() == []


def test_a_second_power_cut_right_after_recovering_loses_nothing(
    window, opened, wait_until, settings, qt_app
):
    path = opened()
    mark(window, wait_until)
    die(window)
    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = True
        again.offer_recovery()
        wait_until(lambda: again.pdf_view._changes == 1 and not again.pdf_view._changing)
        mark(again, wait_until, 30)
        die(again)
        again.documents.clear()  # nothing to ask when this dead one is cleared away
    with started_again(settings, qt_app) as third:
        third.restore_session()
        third.recovery_answer = True
        assert third.offer_recovery() == 1
        view = third.pdf_view
        wait_until(lambda: view._changes == 2 and not view._changing)
        third.save_document()
        settle(view, wait_until)
    assert marks_in(path) == 2


def test_the_document_is_opened_if_its_tab_did_not_come_back(
    window, opened, wait_until, settings, qt_app
):
    path = opened()
    mark(window, wait_until)
    die(window)
    with started_again(settings, qt_app) as again:
        assert not again.documents, "the tabs were not restored this time"
        again.recovery_answer = True
        assert again.offer_recovery() == 1
        assert again.current_document.path == path


def test_saying_not_now_keeps_them_for_later_and_does_not_ask_again(
    window, opened, wait_until, settings, qt_app
):
    path = opened()
    mark(window, wait_until)
    die(window)
    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = False
        assert again.offer_recovery() == 0
        assert not again.pdf_view.modified
        assert again.journal.pending() == []
        (aside,) = again.journal.discarded()
        assert aside.path == path
        assert again.offer_recovery() == 0, "asked only once"
        # A new change after that starts a clean journal.
        mark(again, wait_until, 30)
        assert again.journal.pending()[0].count == 1


def test_with_nobody_to_ask_the_changes_stay_where_they_are(
    window, opened, wait_until, settings, qt_app
):
    opened()
    mark(window, wait_until)
    die(window)
    with started_again(settings, qt_app) as again:
        assert again.offer_recovery() == 0
        assert len(again.journal.pending()) == 1


def test_a_clean_start_offers_nothing(window):
    window.recovery_answer = True
    assert window.offer_recovery() == 0


def test_several_documents_are_recovered_at_once(window, opened, wait_until, settings, qt_app):
    first = opened()
    mark(window, wait_until)
    second = opened("texto-partido.pdf", "otro.pdf")
    mark(window, wait_until)
    mark(window, wait_until, 30)
    die(window)
    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = True
        assert again.offer_recovery() == 2
        wait_until(lambda: all(not p.view._changing for p in again.documents))
        changes = {page.path: page.view._changes for page in again.documents}
        assert changes == {first: 1, second: 2}


def test_killed_in_the_middle_of_saving_the_marks_are_not_doubled(
    window, opened, wait_until, settings, qt_app
):
    # The PDF was already replaced by the new one, but the program died before
    # it could empty the journal.
    path = opened()
    mark(window, wait_until)
    journal_file = window.pdf_view.journal.file
    kept = journal_file.read_bytes()
    window.save_document()
    settle(window.pdf_view, wait_until)
    assert marks_in(path) == 1
    journal_file.parent.mkdir(exist_ok=True)
    journal_file.write_bytes(kept)
    die(window)
    with started_again(settings, qt_app) as again:
        again.restore_session()
        again.recovery_answer = True
        again.offer_recovery()
        view = again.pdf_view
        wait_until(lambda: not view._changing)
        again.save_document()
        settle(view, wait_until)
    assert marks_in(path) == 1


# ---- the page being read survives too -------------------------------------


def test_the_page_is_remembered_while_reading_not_only_when_closing(
    window, sample, tmp_path, wait_until, settings, qt_app
):
    window.show_problem_dialogs = False
    path = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), path)
    assert window.open_document(path)
    window._place_timer.setInterval(10)
    window.pdf_view.scroll_to_page(7)
    wait_until(lambda: window.history.place_of(path).page == 7)
    die(window)
    with started_again(settings, qt_app) as again:
        again.restore_session()
        wait_until(lambda: again.pdf_view.current_page == 7)


# ---- the question itself ---------------------------------------------------


def pending_for(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    mark(window, wait_until, 30)
    return window.journal.pending()


def test_the_question_after_a_power_cut(window, opened, wait_until):
    items = pending_for(window, opened, wait_until)
    dialog = RecoveryDialog(items, crashed=True)
    assert "sin guardar" in dialog.message.text()
    line = dialog.list.item(0).text()
    assert "texto-partido.pdf" in line and "2 cambios" in line and "hoy" in line
    assert dialog.recover_button.isDefault()
    assert "Ahora no" in dialog.later_button.text().replace("&", "")
    assert "7" in dialog.keep_note.text()
    dialog.recover_button.click()
    assert dialog.chosen == items
    closed = RecoveryDialog(items, crashed=True)
    closed.reject()
    assert closed.chosen == []


def test_the_list_of_discarded_changes(window, opened, wait_until):
    opened()
    mark(window, wait_until)
    window.unsaved_answer = DISCARD
    window.close_document()
    items = window.journal.discarded()
    dialog = RecoveryDialog(items, crashed=False)
    assert "1 cambio" in dialog.list.item(0).text()
    assert dialog.list.currentRow() == 0 and dialog.recover_button.isEnabled()
    dialog.recover_button.click()
    assert dialog.chosen == items


def test_the_list_of_discarded_changes_when_there_are_none(qt_app):
    dialog = RecoveryDialog([], crashed=False)
    assert "No hay" in dialog.message.text()
    assert dialog.list.isHidden() and not dialog.recover_button.isEnabled()


def test_older_changes_say_their_day(window, opened, wait_until):
    from dataclasses import replace

    (item,) = pending_for(window, opened, wait_until)
    dialog = RecoveryDialog([replace(item, when=time.time() - 86400)], crashed=True)
    assert "ayer" in dialog.list.item(0).text()
    older = RecoveryDialog([replace(item, when=time.time() - 5 * 86400)], crashed=True)
    assert "/" in older.list.item(0).text()
