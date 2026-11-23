"""Tests for sleeping tabs in the window."""

import time

from app.core import notes, tab_sleep

LATER = 16 * 60  # seconds: longer than the 15 minutes of the settings


def open_two(window, sample, wait_until):
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    first = window.current_document
    wait_until(lambda: first.view.cached_pages())
    assert window.open_document(sample("largo.pdf"))
    second = window.current_document
    wait_until(lambda: second.view.cached_pages())
    return first, second


def test_a_tab_out_of_sight_for_a_while_goes_to_sleep_and_wakes_up(window, sample, wait_until):
    first, second = open_two(window, sample, wait_until)
    # Leaving the screen it keeps only the pictures it was showing.
    shown = set(first.view._visible_pages())
    assert set(first.view.cached_pages()) <= shown
    assert window.sleep_unseen_tabs(time.monotonic() + 60) == 0  # not long enough
    assert window.sleep_unseen_tabs(time.monotonic() + LATER) == 1
    assert first.asleep and not second.asleep  # the one in front never sleeps
    assert not first.view.service.is_running()
    assert set(first.view.cached_pages()) <= shown  # still something to show at once
    window.document_tabs.setCurrentIndex(0)
    wait_until(lambda: first.view.service.is_running())
    assert not first.asleep
    first.view.scroll_to_page(5)
    wait_until(lambda: 5 in first.view.cached_pages())


def test_a_sleeping_tab_keeps_its_changes_and_its_page(window, sample, wait_until):
    first, _second = open_two(window, sample, wait_until)
    window.document_tabs.setCurrentIndex(0)
    first.view.scroll_to_page(3)
    assert first.view._do(notes.new_text_box(3, (60, 80), "no te vayas"))
    wait_until(lambda: first.view.modified)
    wait_until(lambda: not first.view.service._in_flight)
    window.document_tabs.setCurrentIndex(1)
    assert window.sleep_unseen_tabs(time.monotonic() + LATER) == 1
    window.document_tabs.setCurrentIndex(0)
    assert first.view.current_page == 3 and first.view.modified
    first.view._want_notes(3, again=True)
    wait_until(lambda: [note.text for note in first.view.notes_of(3)] == ["no te vayas"])
    assert first.view.can_undo


def test_sleeping_tabs_can_be_turned_off(window, settings, sample, wait_until):
    first, _second = open_two(window, sample, wait_until)
    settings.set(tab_sleep.SLEEP_SETTING, False)
    assert window.sleep_unseen_tabs(time.monotonic() + 10 * 3600) == 0
    assert not first.asleep


def test_a_tab_reading_its_scanned_pages_does_not_sleep(window, sample, wait_until):
    first, _second = open_two(window, sample, wait_until)
    first.text_recognition = object()  # a run going on
    try:
        assert window.sleep_unseen_tabs(time.monotonic() + LATER) == 0
    finally:
        first.text_recognition = None


def test_the_setting_is_in_the_settings_window(window, settings):
    from app.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(window)
    assert dialog.sleep_box.isChecked()
    assert dialog.sleep_minutes_box.currentData() == 15
    dialog.sleep_minutes_box.setCurrentIndex(dialog.sleep_minutes_box.findData(60))
    dialog.sleep_minutes_box.activated.emit(dialog.sleep_minutes_box.currentIndex())
    assert tab_sleep.sleep_minutes(settings) == 60
    dialog.sleep_box.setChecked(False)
    assert not tab_sleep.sleep_wanted(settings)
    assert not dialog.sleep_minutes_box.isEnabled()
    dialog.deleteLater()
