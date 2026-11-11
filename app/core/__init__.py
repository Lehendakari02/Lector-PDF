"""PDF logic: opening, searching, annotating, signing...

Nothing in this package may import from ``app.ui`` or from Qt (PySide6), so the
PDF logic can be tested on its own and reused by a future tablet/mobile version.
``tests/core/test_core_is_ui_free.py`` enforces this rule.
"""
