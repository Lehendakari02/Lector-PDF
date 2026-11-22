"""Tests for the user's own names for colours."""

from app.core.color_names import LONGEST_NAME, SETTING, ColorNames

YELLOW = (1.0, 0.92, 0.23)


class FakeSettings(dict):
    def set(self, key, value):
        self[key] = value


def test_nothing_comes_named():
    assert ColorNames(FakeSettings()).name_of(YELLOW) == ""
    assert ColorNames().named() == {}


def test_a_name_is_kept_in_the_settings_and_read_back():
    settings = FakeSettings()
    ColorNames(settings).set_name(YELLOW, "  Definiciones  ")
    assert list(settings[SETTING].values()) == ["Definiciones"]
    assert ColorNames(settings).name_of(YELLOW) == "Definiciones"


def test_a_colour_read_back_from_a_pdf_finds_its_name():
    names = ColorNames(FakeSettings())
    names.set_name(YELLOW, "Plazos")
    assert names.name_of((0.996, 0.918, 0.231)) == "Plazos"
    assert names.name_of((0.0, 0.0, 1.0)) == ""


def test_renaming_replaces_and_empty_takes_it_away():
    settings = FakeSettings()
    names = ColorNames(settings)
    names.set_name(YELLOW, "Uno")
    names.set_name((0.998, 0.92, 0.23), "Dos")
    assert names.named() == {next(iter(names.named())): "Dos"}
    names.set_name(YELLOW, "")
    assert names.name_of(YELLOW) == "" and settings[SETTING] == {}


def test_long_names_are_cut_and_bad_settings_ignored():
    names = ColorNames(FakeSettings())
    names.set_name(YELLOW, "x" * 100)
    assert len(names.name_of(YELLOW)) == LONGEST_NAME
    broken = FakeSettings({SETTING: {"nothex": "a", "#ffeb3b": 3, "#00ff00": "Verde"}})
    assert ColorNames(broken).named() == {"#00ff00": "Verde"}
    assert ColorNames(FakeSettings({SETTING: "rubbish"})).named() == {}
