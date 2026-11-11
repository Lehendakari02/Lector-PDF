"""Shared setup for interface tests."""

import time

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


@pytest.fixture
def wait_until(qt_app):
    """Keep the interface running until ``condition`` is true (or fail)."""

    def wait(condition, seconds: float = 30) -> None:
        deadline = time.monotonic() + seconds
        while not condition():
            assert time.monotonic() < deadline, "timed out waiting"
            qt_app.processEvents()
            time.sleep(0.005)

    return wait
