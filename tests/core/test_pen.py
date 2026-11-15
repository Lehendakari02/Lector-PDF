"""Tests for app.core.pen: what the pen and the fingers do, and the defaults."""

import pytest

from app.core import pen
from app.core.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "ajustes.json")


def test_without_touching_anything(settings):
    assert pen.pressure_wanted(settings) is True
    assert pen.finger_mode(settings) == pen.AUTO
    assert pen.pen_seen(settings) is False


def test_what_is_chosen_is_what_is_read(settings):
    settings.set(pen.PRESSURE_SETTING, False)
    settings.set(pen.FINGER_SETTING, pen.MOVES)
    settings.set(pen.PEN_SEEN_SETTING, True)
    again = Settings(settings.path)
    assert pen.pressure_wanted(again) is False
    assert pen.finger_mode(again) == pen.MOVES
    assert pen.pen_seen(again) is True


def test_odd_values_count_as_the_defaults(settings):
    settings.set(pen.PRESSURE_SETTING, "no")
    settings.set(pen.FINGER_SETTING, "pies")
    settings.set(pen.PEN_SEEN_SETTING, "tal vez")
    assert pen.pressure_wanted(settings) is True
    assert pen.finger_mode(settings) == pen.AUTO
    assert pen.pen_seen(settings) is False


def test_the_finger_draws_until_a_pen_is_seen():
    assert pen.finger_uses_tool(pen.AUTO, seen=False)
    assert not pen.finger_uses_tool(pen.AUTO, seen=True)
    assert pen.finger_uses_tool(pen.DRAWS, seen=True)
    assert not pen.finger_uses_tool(pen.MOVES, seen=False)


def test_a_touch_just_after_the_pen_is_the_hand_that_holds_it():
    assert pen.palm(0.2) and pen.palm(5.0, pen_down=True)
    assert not pen.palm(pen.PALM_SECONDS + 0.1)
    assert not pen.palm(float("inf"))
