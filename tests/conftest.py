"""Shared test setup."""

import os
from pathlib import Path

import pytest

# Run Qt without a real screen so interface tests work on GitHub's machines.
# Must be set before PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SAMPLES_DIR = Path(__file__).resolve().parent / "ejemplos"


@pytest.fixture
def sample():
    """Return the path of a sample PDF from ``tests/ejemplos`` by file name."""

    def find(name: str) -> Path:
        path = SAMPLES_DIR / name
        assert path.is_file(), f"Missing sample file: {path}"
        return path

    return find
