"""Tests for app.core.tool_keys."""

from app.core.settings import Settings
from app.core.tool_keys import FAVOURITE_KEYS, TOOL_KEYS, TOOL_KEYS_SETTING, tool_keys_wanted


def test_every_tool_has_a_key_of_its_own():
    keys = list(TOOL_KEYS.values())
    assert len(set(keys)) == len(keys)
    assert all(len(key) == 1 and key.isalpha() and key.isupper() for key in keys)
    assert not set(keys) & set(FAVOURITE_KEYS)


def test_they_are_on_unless_turned_off(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    assert tool_keys_wanted(settings)
    settings.set(TOOL_KEYS_SETTING, "quizá")
    assert tool_keys_wanted(settings), "an odd value counts as the default"
    settings.set(TOOL_KEYS_SETTING, False)
    assert not tool_keys_wanted(Settings(settings.path))
