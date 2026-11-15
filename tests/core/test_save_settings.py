"""Tests for app.core.save_settings."""

import pytest

from app.core import save_settings as ss
from app.core.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "ajustes.json")


def test_without_touching_anything_the_defaults_are_the_safe_ones(settings):
    assert ss.close_choice(settings) == ss.ASK
    assert ss.when_closing(settings) == ss.ASK
    assert ss.autosave_wanted(settings) is False
    assert ss.autosave_seconds(settings) == 30
    assert ss.versions_count(settings) == 10
    assert ss.versions_room_bytes(settings) == 1024 * 1024 * 1024
    assert ss.discarded_days(settings) == 7


def test_what_is_chosen_is_what_is_read(settings):
    settings.set(ss.CLOSE_SETTING, ss.DISCARD)
    settings.set(ss.AUTOSAVE_SECONDS_SETTING, 120)
    settings.set(ss.VERSIONS_COUNT_SETTING, 50)
    settings.set(ss.VERSIONS_ROOM_SETTING, 250)
    settings.set(ss.DISCARDED_DAYS_SETTING, 30)
    assert ss.close_choice(settings) == ss.DISCARD
    assert ss.autosave_seconds(settings) == 120
    assert ss.versions_count(settings) == 50
    assert ss.versions_room_mb(settings) == 250
    assert ss.discarded_days(settings) == 30


@pytest.mark.parametrize("strange", ["siempre", 0, -3, 7.5, None, True, [1], {"a": 1}])
def test_a_strange_value_counts_as_the_default(settings, strange):
    for name in (
        ss.CLOSE_SETTING,
        ss.AUTOSAVE_SETTING,
        ss.AUTOSAVE_SECONDS_SETTING,
        ss.VERSIONS_COUNT_SETTING,
        ss.VERSIONS_ROOM_SETTING,
        ss.DISCARDED_DAYS_SETTING,
    ):
        settings.set(name, strange)
    assert ss.close_choice(settings) == ss.ASK
    assert ss.autosave_wanted(settings) is (strange is True)
    assert ss.autosave_seconds(settings) == 30
    assert ss.versions_count(settings) == 10
    assert ss.versions_room_mb(settings) == 1024
    assert ss.discarded_days(settings) == 7


def test_saving_by_itself_also_saves_when_closing(settings):
    settings.set(ss.AUTOSAVE_SETTING, True)
    assert ss.when_closing(settings) == ss.SAVE
    settings.set(ss.CLOSE_SETTING, ss.DISCARD)
    assert ss.when_closing(settings) == ss.SAVE, "the stored choice waits for autosave to go off"
    settings.set(ss.AUTOSAVE_SETTING, False)
    assert ss.when_closing(settings) == ss.DISCARD


def test_the_defaults_are_among_the_choices():
    assert ss.AUTOSAVE_SECONDS in ss.AUTOSAVE_SECONDS_CHOICES
    assert ss.VERSIONS_COUNT in ss.VERSIONS_COUNT_CHOICES
    assert ss.VERSIONS_ROOM in ss.VERSIONS_ROOM_CHOICES
    assert ss.DISCARDED_DAYS in ss.DISCARDED_DAYS_CHOICES
