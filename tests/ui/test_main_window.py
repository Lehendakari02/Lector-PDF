"""Smoke test: the main window can be created and shown."""

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app import APP_NAME, __version__
from app.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_main_window_shows_name_and_versions(qt_app):
    window = MainWindow()
    window.show()
    qt_app.processEvents()

    assert window.isVisible()
    assert window.windowTitle() == APP_NAME
    title = window.findChild(QLabel, "placeholderTitle")
    assert __version__ in title.text()
    versions = window.findChild(QLabel, "placeholderVersions")
    assert "PyMuPDF" in versions.text()
    window.close()
