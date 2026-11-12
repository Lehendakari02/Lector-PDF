"""Tests for the size of the interface chosen in the settings."""

import pytest

from app.core.interface_size import (
    NORMAL_SIZE,
    SIZE_SETTING,
    SIZES,
    apply_before_start,
    size_from_setting,
    wanted_size,
)
from app.core.restart import OWN_VARIABLES_MARK
from app.core.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "ajustes.json")


def test_the_normal_size_is_offered_and_is_the_default(settings):
    assert NORMAL_SIZE in SIZES
    assert wanted_size(settings) == NORMAL_SIZE


@pytest.mark.parametrize("value", [None, "125", 90, 1000, 1.25, True])
def test_a_strange_value_means_the_normal_size(value):
    assert size_from_setting(value) == NORMAL_SIZE


def test_the_normal_size_changes_nothing(settings):
    environ = {}
    assert apply_before_start(settings, environ) == NORMAL_SIZE
    assert environ == {}


def test_a_bigger_size_is_given_to_qt(settings):
    settings.set(SIZE_SETTING, 125)
    environ = {}
    assert apply_before_start(settings, environ) == 125
    assert environ["QT_SCALE_FACTOR"] == "1.25"
    assert "QT_SCALE_FACTOR" in environ[OWN_VARIABLES_MARK]


def test_a_size_set_from_outside_is_respected(settings):
    settings.set(SIZE_SETTING, 150)
    environ = {"QT_SCALE_FACTOR": "2"}
    apply_before_start(settings, environ)
    assert environ == {"QT_SCALE_FACTOR": "2"}
