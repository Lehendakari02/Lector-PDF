"""Tests for the colour and opacity of the marking tools."""

import pytest

from app.core.commands import DEFAULT_COLORS, HIGHLIGHT, MARKUP_KINDS, UNDERLINE
from app.core.marker_styles import (
    MAX_RECENT,
    MIN_OPACITY,
    QUICK_COLORS,
    MarkerStyles,
    clamp_opacity,
    from_hex,
    same_color,
    to_hex,
)


def test_colours_are_written_and_read_back():
    assert to_hex((1.0, 0.0, 0.5)) == "#ff0080"
    assert from_hex("#ff0080") == pytest.approx((1.0, 0.0, 128 / 255))
    assert from_hex("#FF0080") == from_hex("#ff0080")
    for color in QUICK_COLORS:
        assert same_color(from_hex(to_hex(color)), color)


@pytest.mark.parametrize("bad", ["", "ff0080", "#ff00", "#gg0000", None, 12, "#ff00800"])
def test_what_is_not_a_colour_is_none(bad):
    assert from_hex(bad) is None


def test_colours_out_of_range_are_brought_in():
    assert to_hex((2.0, -1.0, 0.0)) == "#ff0000"


@pytest.mark.parametrize(
    ("given", "expected"),
    [(0.5, 0.5), (0, MIN_OPACITY), (7, 1.0), ("x", 1.0), (None, 1.0), (float("nan"), 1.0)],
)
def test_opacity_always_makes_sense(given, expected):
    assert clamp_opacity(given) == expected


def test_every_tool_starts_with_its_colour_and_full_opacity():
    styles = MarkerStyles()
    for kind in MARKUP_KINDS:
        assert styles.of(kind).color == DEFAULT_COLORS[kind]
        assert styles.of(kind).opacity == 1.0
    assert styles.recent == []


def test_each_tool_keeps_its_own_style():
    styles = MarkerStyles()
    styles.set_color(HIGHLIGHT, QUICK_COLORS[1])
    styles.set_opacity(HIGHLIGHT, 0.4)
    assert styles.of(HIGHLIGHT).color == QUICK_COLORS[1]
    assert styles.of(HIGHLIGHT).opacity == 0.4
    assert styles.of(UNDERLINE).color == DEFAULT_COLORS[UNDERLINE]
    assert styles.of(UNDERLINE).opacity == 1.0


def test_only_colours_outside_the_palette_are_remembered_as_recent():
    styles = MarkerStyles()
    styles.set_color(HIGHLIGHT, QUICK_COLORS[3])
    assert styles.recent == []
    styles.set_color(HIGHLIGHT, (0.2, 0.3, 0.4))
    styles.set_color(UNDERLINE, (0.5, 0.5, 0.5))
    styles.set_color(HIGHLIGHT, (0.2, 0.3, 0.4))  # again: goes first, not twice
    assert [to_hex(c) for c in styles.recent] == [to_hex((0.2, 0.3, 0.4)), "#808080"]
    for step in range(MAX_RECENT + 3):
        styles.set_color(HIGHLIGHT, (step / 20, 0.0, 0.33))
    assert len(styles.recent) == MAX_RECENT
    assert same_color(styles.recent[0], ((MAX_RECENT + 2) / 20, 0.0, 0.33))


def test_the_styles_survive_the_settings_file():
    styles = MarkerStyles()
    styles.set_color(HIGHLIGHT, (0.2, 0.3, 0.4))
    styles.set_opacity(UNDERLINE, 0.55)
    back = MarkerStyles.from_setting(styles.to_setting())
    assert same_color(back.of(HIGHLIGHT).color, (0.2, 0.3, 0.4))
    assert back.of(UNDERLINE).opacity == 0.55
    assert [to_hex(c) for c in back.recent] == [to_hex((0.2, 0.3, 0.4))]


@pytest.mark.parametrize(
    "damaged",
    [
        None,
        "x",
        [],
        {"tools": 3},
        {"tools": {"highlight": "red"}},
        {"tools": {"highlight": {"color": "red", "opacity": "a lot"}}, "recent": [1, "#12", {}]},
        {"recent": "#ffffff"},
    ],
)
def test_damaged_settings_fall_back_to_the_defaults(damaged):
    styles = MarkerStyles.from_setting(damaged)
    assert styles.of(HIGHLIGHT).color == DEFAULT_COLORS[HIGHLIGHT]
    assert styles.of(HIGHLIGHT).opacity == 1.0
    assert styles.recent == []


def test_a_partly_right_setting_keeps_what_is_right():
    styles = MarkerStyles.from_setting(
        {"tools": {"highlight": {"color": "#00ff00", "opacity": 0.3}, "underline": 5}}
    )
    assert to_hex(styles.of(HIGHLIGHT).color) == "#00ff00"
    assert styles.of(HIGHLIGHT).opacity == 0.3
    assert styles.of(UNDERLINE).color == DEFAULT_COLORS[UNDERLINE]
