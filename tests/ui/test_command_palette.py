"""Tests for the function finder window."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ui.command_palette import CommandPalette
from app.ui.features import FEATURES


def test_starts_listing_every_function(window):
    palette = CommandPalette(window)
    assert palette.results.count() == len(FEATURES)
    assert palette.results.currentRow() == 0


def test_typing_filters_and_enter_chooses_the_first(window):
    palette = CommandPalette(window)
    palette.show()
    QTest.keyClicks(palette.query, "unir")
    assert palette.results.item(0).text().startswith("Unir")
    QTest.keyClick(palette.query, Qt.Key.Key_Return)
    assert palette.chosen.id == "merge"
    assert palette.result() == CommandPalette.DialogCode.Accepted


def test_arrow_keys_move_through_the_results_while_typing(window):
    palette = CommandPalette(window)
    palette.show()
    QTest.keyClicks(palette.query, "firmar")
    QTest.keyClick(palette.query, Qt.Key.Key_Down)
    assert palette.results.currentRow() == 1
    QTest.keyClick(palette.query, Qt.Key.Key_Up)
    QTest.keyClick(palette.query, Qt.Key.Key_Up)
    assert palette.results.currentRow() == 0
    QTest.keyClick(palette.query, Qt.Key.Key_Down)
    QTest.keyClick(palette.query, Qt.Key.Key_Return)
    assert palette.chosen.id == "sign_certificate"


def test_no_results_shows_a_message_and_enter_does_nothing(window):
    palette = CommandPalette(window)
    palette.show()
    QTest.keyClicks(palette.query, "xyzxyz")
    assert palette.results.count() == 0
    assert palette.empty.isVisible()
    QTest.keyClick(palette.query, Qt.Key.Key_Return)
    assert palette.chosen is None
    assert palette.isVisible()


def test_escape_closes_without_choosing(window):
    palette = CommandPalette(window)
    palette.show()
    QTest.keyClick(palette, Qt.Key.Key_Escape)
    assert palette.chosen is None
    assert not palette.isVisible()
