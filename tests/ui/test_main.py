"""Tests for the program entry point."""

from app.main import AUTOCLOSE_FLAG, main


def test_autoclose_opens_and_quits_cleanly():
    assert main(["lector-pdf", AUTOCLOSE_FLAG]) == 0
