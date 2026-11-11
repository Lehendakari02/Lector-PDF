"""Shared setup for interface tests."""

import pytest
from PySide6.QtWidgets import QApplication

from app.core.settings import Settings
from app.ui.main_window import MainWindow
from app.ui.theme import prepare_application


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    prepare_application(app)
    return app


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "ajustes.json")


@pytest.fixture
def window(qt_app, settings):
    main_window = MainWindow(settings)
    main_window.show()
    qt_app.processEvents()
    yield main_window
    main_window.close()
