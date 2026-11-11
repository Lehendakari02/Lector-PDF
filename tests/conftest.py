"""Shared test setup."""

import os

# Run Qt without a real screen so interface tests work on GitHub's machines.
# Must be set before PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
