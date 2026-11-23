"""Tests for sleeping tabs: a document out of sight stops its helper."""

import threading

import pytest

from app.core import notes, tab_sleep
from app.core.render_service import RenderRequest, RenderService
from app.core.settings import Settings

WAIT_SECONDS = 30


class Watcher:
    def __init__(self):
        self.pages = []
        self.changed = []
        self.notes = {}
        self.crashes = 0
        self.searches_done = []
        self._condition = threading.Condition()
        self.service = RenderService(
            on_page=lambda page: self._add(self.pages, page),
            on_changed=lambda number, *_: self._add(self.changed, number),
            on_notes=self._notes,
            on_crashed=self._crashed,
            on_search_done=lambda number, _many: self._add(self.searches_done, number),
        )

    def _add(self, where, item):
        with self._condition:
            where.append(item)
            self._condition.notify_all()

    def _notes(self, page, found):
        with self._condition:
            self.notes[page] = found
            self._condition.notify_all()

    def _crashed(self):
        with self._condition:
            self.crashes += 1
            self._condition.notify_all()

    def wait(self, condition):
        with self._condition:
            assert self._condition.wait_for(condition, WAIT_SECONDS), "timed out"


@pytest.fixture
def watcher():
    made = Watcher()
    yield made
    made.service.shutdown()


def test_settings_have_sensible_defaults(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    assert tab_sleep.sleep_wanted(settings)
    assert tab_sleep.sleep_minutes(settings) == tab_sleep.DEFAULT_MINUTES == 15
    assert not tab_sleep.time_to_sleep(settings, 14 * 60)
    assert tab_sleep.time_to_sleep(settings, 15 * 60)
    settings.set(tab_sleep.MINUTES_SETTING, 5)
    assert tab_sleep.time_to_sleep(settings, 5 * 60)
    settings.set(tab_sleep.MINUTES_SETTING, 7)  # not a choice: the default
    assert tab_sleep.sleep_minutes(settings) == 15
    settings.set(tab_sleep.SLEEP_SETTING, False)
    assert not tab_sleep.time_to_sleep(settings, 10 * 3600)


def test_a_sleeping_helper_wakes_up_with_the_document(watcher, sample):
    service = watcher.service
    service.open(sample("boe.pdf"))
    service.want([RenderRequest(0, 1.0)])
    watcher.wait(lambda: len(watcher.pages) == 1)
    first = service.process_id
    assert service.sleep()
    assert service.asleep and not service.is_running()
    assert service.sleeps == 1
    service.want([RenderRequest(1, 1.0)])  # looked at again
    watcher.wait(lambda: len(watcher.pages) == 2)
    assert watcher.pages[1].page == 1
    assert service.process_id != first and not service.asleep
    assert watcher.crashes == 0 and service.restarts == 0  # not a crash


def test_the_changes_not_saved_survive_the_sleep(watcher, sample):
    service = watcher.service
    service.open(sample("boe.pdf"))
    number = service.apply(notes.new_text_box(0, (60, 80), "sigo aquí"))
    watcher.wait(lambda: number in watcher.changed)
    assert service.sleep()
    service.want_notes(0)
    watcher.wait(lambda: 0 in watcher.notes)
    assert [note.text for note in watcher.notes[0]] == ["sigo aquí"]


def test_a_busy_helper_does_not_sleep(watcher, sample):
    service = watcher.service
    assert not service.sleep()  # nothing open
    service.open(sample("largo.pdf"))
    service.search("de")
    assert not service.sleep()  # searching
    service.cancel_search()
    service.want([RenderRequest(0, 1.0)])
    watcher.wait(lambda: watcher.pages)
    assert service.sleep()
    assert not service.sleep()  # already asleep


def test_a_closed_document_is_not_asleep(watcher, sample):
    service = watcher.service
    service.open(sample("boe.pdf"))
    service.want([RenderRequest(0, 1.0)])
    watcher.wait(lambda: watcher.pages)
    assert service.sleep()
    service.close_document()
    assert not service.asleep
