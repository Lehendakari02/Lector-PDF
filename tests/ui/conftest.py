"""Shared setup for interface tests."""

import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
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
    main_window.unsaved_answer = "discard"  # never wait for an answer when a test ends
    main_window.close()
    # Really destroy it. Windows left behind make every later change of the
    # style sheet slower, and the tests ended up taking twice as long.
    main_window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def documents_in_temporary_folders_are_fine(monkeypatch):
    """The documents of the tests all live in temporary folders: do not warn
    about it before every save (the tests of that warning turn it on)."""
    monkeypatch.setattr(MainWindow, "warn_about_temporary_folders", False)


@pytest.fixture(autouse=True)
def no_windows_left_behind(qt_app):
    """Destroy every window, dialog and menu a test leaves behind.

    Left alone they pile up, and each one makes every later change of the
    style sheet slower: the whole suite ended up taking twice as long.
    """
    yield
    for _round in range(3):  # closing a window can leave a dialog of its own
        left = qt_app.topLevelWidgets()
        if not left:
            break
        for widget in left:
            if isinstance(widget, MainWindow):
                widget.unsaved_answer = "discard"
                widget.shutdown_documents()
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


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
