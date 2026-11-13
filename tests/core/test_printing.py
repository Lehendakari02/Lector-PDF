"""Tests for the arithmetic of printing."""

import pytest

from app.core.printing import (
    MAX_PRINT_DPI,
    PageRangeError,
    Scaling,
    is_landscape,
    parse_pages,
    placement,
    print_zoom,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3", [2]),
        ("1-3", [0, 1, 2]),
        ("1-3, 7", [0, 1, 2, 6]),
        ("1 - 3 ; 7", [0, 1, 2, 6]),
        ("8-", [7, 8, 9]),
        ("-2", [0, 1]),
        ("5,1", [4, 0]),  # in the order asked
        ("3-1", [2, 1, 0]),
        ("2,2,1-3", [1, 0, 2]),  # never twice
        ("1–2", [0, 1]),  # a long dash, as Word writes it
        (" 4 ,, ", [3]),
    ],
)
def test_pages_typed_by_the_user(text, expected):
    assert parse_pages(text, 10) == expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", PageRangeError.EMPTY),
        (" , ", PageRangeError.EMPTY),
        ("uno", PageRangeError.NOT_UNDERSTOOD),
        ("1-2-3", PageRangeError.NOT_UNDERSTOOD),
        ("-", PageRangeError.NOT_UNDERSTOOD),
        ("1.5", PageRangeError.NOT_UNDERSTOOD),
        ("0", PageRangeError.OUT_OF_RANGE),
        ("11", PageRangeError.OUT_OF_RANGE),
        ("8-12", PageRangeError.OUT_OF_RANGE),
    ],
)
def test_pages_that_cannot_be_understood(text, reason):
    with pytest.raises(PageRangeError) as error:
        parse_pages(text, 10)
    assert error.value.reason == reason


def test_the_piece_that_is_wrong_is_named():
    with pytest.raises(PageRangeError) as error:
        parse_pages("1-3, 40", 10)
    assert error.value.piece == "40"


def test_pages_are_drawn_sharp_but_not_absurdly():
    assert print_zoom(300) == pytest.approx(300 / 72)
    assert print_zoom(1200) == pytest.approx(MAX_PRINT_DPI / 72)
    assert print_zoom(72) == pytest.approx(150 / 72)


def test_fitting_keeps_the_shape_and_centres_the_page():
    # A wide page on tall paper: full width, centred up and down.
    left, top, width, height = placement(200, 100, 100, 100, Scaling.FIT)
    assert (left, width, height) == (0, 100, 50)
    assert top == 25
    # A small page grows until it touches the paper.
    assert placement(10, 20, 100, 100, Scaling.FIT) == (25, 0, 50, 100)


def test_real_size_does_not_change_the_page():
    assert placement(50, 80, 100, 100, Scaling.ACTUAL) == (25, 10, 50, 80)
    # Bigger than the paper: centred, the edges fall outside.
    assert placement(120, 100, 100, 100, Scaling.ACTUAL) == (-10, 0, 120, 100)


def test_an_empty_page_takes_no_room():
    assert placement(0, 0, 100, 100, Scaling.FIT) == (0, 0, 0, 0)


def test_landscape_pages_are_recognised():
    assert is_landscape(842, 595)
    assert not is_landscape(595, 842)
    assert not is_landscape(500, 500)


def test_scaling_from_the_settings():
    assert Scaling.from_setting("real") is Scaling.ACTUAL
    assert Scaling.from_setting("otra cosa") is Scaling.FIT
