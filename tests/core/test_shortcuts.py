"""Tests for app.core.shortcuts: the keys of every function, to change."""

from app.core import shortcuts
from app.core.settings import Settings
from app.core.tool_keys import FAVOURITE_KEYS, TOOL_KEYS


def test_the_usual_keys_come_without_touching_anything(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    assert shortcuts.keys_of(settings, "save") == ("Ctrl+S",)
    assert shortcuts.keys_of(settings, "redo") == ("Ctrl+Y", "Ctrl+Shift+Z")
    assert shortcuts.keys_of(settings, "underline") == ("S",)
    assert shortcuts.keys_of(settings, "favourite_3") == ("3",)
    assert shortcuts.keys_of(settings, "summary") == ()  # none, ready to be given one
    assert not shortcuts.is_changed(settings, "save")


def test_the_usual_keys_never_clash():
    by_key: dict[str, list[str]] = {}
    for command_id, keys in shortcuts.DEFAULTS.items():
        assert len(keys) <= shortcuts.MAX_KEYS
        for key in keys:
            assert not shortcuts.is_reserved(key)
            by_key.setdefault(key, []).append(command_id)
    assert {key: ids for key, ids in by_key.items() if len(ids) > 1} == {}
    assert set(TOOL_KEYS) | {f"favourite_{n}" for n in range(1, len(FAVOURITE_KEYS) + 1)} <= set(
        shortcuts.DEFAULTS
    )


def test_a_key_changed_is_kept_and_only_the_changes_are_stored(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    shortcuts.set_keys(settings, "underline", ["U"])
    shortcuts.set_keys(settings, "summary", ["Ctrl+Shift+R", "F8", "F9"])  # two at most
    again = Settings(settings.path)
    assert shortcuts.keys_of(again, "underline") == ("U",)
    assert shortcuts.keys_of(again, "summary") == ("Ctrl+Shift+R", "F8")
    assert shortcuts.is_changed(again, "underline")
    assert set(again.get(shortcuts.SETTING)) == {"underline", "summary"}
    shortcuts.set_keys(again, "underline", ["S"])  # its usual key again: not stored
    assert set(again.get(shortcuts.SETTING)) == {"summary"}


def test_a_function_can_be_left_without_keys(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    shortcuts.set_keys(settings, "print", [])
    assert shortcuts.keys_of(settings, "print") == ()
    shortcuts.reset(settings, "print")
    assert shortcuts.keys_of(settings, "print") == ("Ctrl+P",)


def test_reset_all(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    shortcuts.set_keys(settings, "underline", ["U"])
    shortcuts.set_keys(settings, "save", ["F2"])
    shortcuts.reset(settings)
    assert shortcuts.keys_of(settings, "underline") == ("S",)
    assert shortcuts.keys_of(settings, "save") == ("Ctrl+S",)


def test_damaged_settings_count_as_the_usual_keys(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    settings.set(shortcuts.SETTING, "nonsense")
    assert shortcuts.keys_of(settings, "save") == ("Ctrl+S",)
    settings.set(shortcuts.SETTING, {"save": "Ctrl+S", "copy": [3]})
    assert shortcuts.keys_of(settings, "save") == ("Ctrl+S",)
    assert shortcuts.keys_of(settings, "copy") == ("Ctrl+C",)


def test_plain_keys_only_count_on_the_document():
    assert shortcuts.is_plain("R") and shortcuts.is_plain("Shift+R") and shortcuts.is_plain("7")
    assert shortcuts.is_plain("+") and shortcuts.is_plain(",")
    for key in ("Ctrl+R", "Alt+R", "F11", "Del", "Ctrl++", "Shift+F3", "Meta+R"):
        assert not shortcuts.is_plain(key), key


def test_the_keys_that_move_through_the_document_are_never_given():
    for key in ("Esc", "Space", "Up", "PgDown", "Return", "Tab"):
        assert shortcuts.is_reserved(key)
    assert not shortcuts.is_reserved("F2")


def test_who_has_a_key_and_clashes(tmp_path):
    settings = Settings(tmp_path / "ajustes.json")
    ids = ["highlight", "underline", "save"]
    assert shortcuts.users_of(settings, "S", ids) == ["underline"]
    assert shortcuts.users_of(settings, "S", ids, but="underline") == []
    shortcuts.set_keys(settings, "highlight", ["S"])
    assert shortcuts.clashes(settings, ids) == {"S": ["highlight", "underline"]}
