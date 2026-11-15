"""Tests for app.core.favourites: tools kept the way someone likes them."""

import pytest

from app.core.commands import HIGHLIGHT, UNDERLINE
from app.core.drawing import ARROW, DRAW, OVAL, SHAPE_TOOL
from app.core.favourites import (
    MAX_FAVOURITES,
    Favourite,
    Favourites,
    apply_to,
    clean_name,
    favourite_of,
)
from app.core.marker_styles import MarkerStyles
from app.core.notes import NOTE, SERIF, TEXT_BOX

YELLOW = (1.0, 0.92, 0.23)
RED = (0.85, 0.15, 0.15)
BLUE = (0.13, 0.39, 0.85)


def styles_with(**changes) -> MarkerStyles:
    styles = MarkerStyles()
    styles.set_color(DRAW, RED)
    styles.set_width(DRAW, 4)
    styles.set_opacity(DRAW, 0.5)
    styles.set_shape(OVAL)
    styles.set_text_font(SERIF)
    styles.set_text_size(18)
    return styles


def test_a_favourite_is_the_tool_as_it_is_set_now():
    styles = styles_with()
    pen = favourite_of(styles, DRAW)
    assert (pen.kind, pen.color, pen.width, pen.opacity) == (DRAW, RED, 4, 0.5)
    shape = favourite_of(styles, SHAPE_TOOL)
    assert shape.shape == OVAL
    text = favourite_of(styles, TEXT_BOX)
    assert (text.font, text.size) == (SERIF, 18)


def test_what_a_tool_does_not_have_does_not_tell_favourites_apart():
    styles = styles_with()
    before = favourite_of(styles, HIGHLIGHT)
    styles.set_shape(ARROW)
    styles.set_text_size(10)
    styles.set_width(DRAW, 8)
    assert favourite_of(styles, HIGHLIGHT) == before
    assert favourite_of(styles, NOTE).opacity == 1.0


def test_taking_a_favourite_sets_only_its_tool():
    styles = MarkerStyles()
    untouched = styles.of(HIGHLIGHT)
    apply_to(styles, Favourite(DRAW, RED, 0.5, 8))
    assert styles.of(DRAW).color == RED and styles.of(DRAW).opacity == 0.5
    assert styles.width_of(DRAW) == 8 and styles.width_of(SHAPE_TOOL) == 2
    assert styles.of(HIGHLIGHT) == untouched
    apply_to(styles, Favourite(SHAPE_TOOL, BLUE, 1.0, 4, OVAL))
    assert styles.shape == OVAL and styles.width_of(SHAPE_TOOL) == 4
    apply_to(styles, Favourite(TEXT_BOX, BLUE, font=SERIF, size=24))
    assert (styles.text_font, styles.text_size) == (SERIF, 24)
    assert favourite_of(styles, DRAW) == Favourite(DRAW, RED, 0.5, 8)


@pytest.mark.parametrize(
    "favourite",
    [
        Favourite(HIGHLIGHT, YELLOW, 0.6),
        Favourite(DRAW, RED, 0.5, 8),
        Favourite(SHAPE_TOOL, BLUE, 1.0, 4, OVAL, name="Rodear"),
        Favourite(TEXT_BOX, BLUE, font=SERIF, size=24),
        Favourite(NOTE, YELLOW),
    ],
)
def test_favourites_are_written_and_read_back(favourite):
    again = Favourite.from_setting(favourite.to_setting())
    assert again.same_tool(favourite) and again.name == favourite.name


@pytest.mark.parametrize(
    "bad",
    [None, 7, "x", [], {}, {"tool": "laser", "color": "#ff0000"}, {"tool": DRAW, "color": "red"}],
)
def test_what_is_not_a_favourite_is_left_out(bad):
    assert Favourite.from_setting(bad) is None
    assert len(Favourites.from_setting([bad, Favourite(DRAW, RED).to_setting()])) == 1


def test_odd_values_fall_back_to_sensible_ones():
    read = Favourite.from_setting(
        {"tool": SHAPE_TOOL, "color": "#ff0000", "opacity": "x", "width": -3, "shape": "star"}
    )
    assert (read.opacity, read.width, read.shape) == (1.0, 0.5, ARROW)
    assert Favourites.from_setting("nonsense").items == []
    assert Favourites.from_setting(None).items == []


def test_the_same_tool_is_not_kept_twice():
    favourites = Favourites()
    assert favourites.add(Favourite(DRAW, RED, 1.0, 2)) == 0
    assert favourites.add(Favourite(DRAW, RED, 1.0, 4)) == 1
    assert favourites.add(Favourite(DRAW, RED, 1.0, 2, name="otro nombre")) == 0
    assert favourites.add(Favourite(UNDERLINE, RED)) == 2
    assert len(favourites) == 3
    doubled = [Favourite(DRAW, RED).to_setting()] * 3
    assert len(Favourites.from_setting(doubled)) == 1


def test_the_bar_has_a_limit():
    favourites = Favourites()
    for width in range(1, MAX_FAVOURITES + 1):
        assert favourites.add(Favourite(DRAW, RED, 1.0, width)) == width - 1
    assert favourites.full
    assert favourites.add(Favourite(DRAW, BLUE)) == -1
    assert favourites.add(Favourite(DRAW, RED, 1.0, 3)) == 2, "one that is there is found"
    assert len(Favourites.from_setting(favourites.to_setting() * 2)) == MAX_FAVOURITES


def test_remove_rename_and_move():
    favourites = Favourites([Favourite(DRAW, RED), Favourite(DRAW, BLUE), Favourite(NOTE, YELLOW)])
    assert favourites.rename(1, "  Boli   azul \n")
    assert favourites[1].name == "Boli azul"
    assert favourites.rename(1, "") and favourites[1].name == ""
    assert not favourites.rename(9, "x") and not favourites.remove(9)
    assert favourites.move(0, 1) == 1
    assert [f.color for f in favourites][:2] == [BLUE, RED]
    assert favourites.move(1, 10) == 2 and favourites.move(2, -10) == 0
    assert favourites.move(7, 1) == 7
    assert favourites.remove(0) and len(favourites) == 2


def test_names_are_one_short_line():
    assert clean_name("x" * 100) == "x" * 30
    assert clean_name(None) == "" and clean_name(12) == ""
    assert clean_name(" a\tb\nc ") == "a b c"
