"""Tests for catching errors in the interface and copying the report."""

import sys
import threading

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox

from app.core.error_log import ErrorLog
from app.core.settings import Settings
from app.ui.error_reporting import ErrorReporter, ProvokedError
from app.ui.main_window import MainWindow


@pytest.fixture
def reporter(qt_app, tmp_path):
    error_reporter = ErrorReporter(ErrorLog(tmp_path / "errores.jsonl"))
    yield error_reporter
    error_reporter.uninstall()
    if error_reporter._dialog is not None:
        error_reporter._dialog.close()


@pytest.fixture
def window_with_reporter(qt_app, tmp_path, reporter):
    window = MainWindow(Settings(tmp_path / "ajustes.json"), reporter)
    window.show()
    yield window
    window.close()


def handle(reporter: ErrorReporter, error: Exception) -> None:
    try:
        raise error
    except Exception:
        reporter.handle(*sys.exc_info())


def test_an_error_is_recorded_and_a_notice_is_shown(qt_app, reporter):
    handle(reporter, RuntimeError("se rompió"))
    qt_app.processEvents()
    assert "RuntimeError: se rompió" in reporter.log.entries()[0].details
    dialog = reporter._dialog
    assert isinstance(dialog, QMessageBox) and dialog.isVisible()
    assert "el programa sigue abierto" in dialog.text()
    assert "no se envía" in dialog.informativeText()


def test_many_errors_show_a_single_notice(qt_app, reporter):
    for number in range(5):
        handle(reporter, RuntimeError(f"error {number}"))
    qt_app.processEvents()
    assert len(reporter.log.entries()) == 5
    notices = [w for w in qt_app.topLevelWidgets() if w.objectName() == "errorNotice"]
    assert len([n for n in notices if n.isVisible()]) == 1


def test_a_new_notice_can_appear_after_closing_the_first(qt_app, reporter):
    handle(reporter, RuntimeError("first"))
    qt_app.processEvents()
    reporter._dialog.close()
    qt_app.processEvents()
    assert reporter._dialog is None
    handle(reporter, RuntimeError("second"))
    qt_app.processEvents()
    assert reporter._dialog is not None


def test_copy_button_puts_the_report_on_the_clipboard(qt_app, reporter):
    handle(reporter, RuntimeError("para copiar"))
    qt_app.processEvents()
    copy_button = next(
        b for b in reporter._dialog.buttons() if b.text() == "Copiar informe de error"
    )
    copy_button.click()
    text = QGuiApplication.clipboard().text()
    assert text.startswith("Informe de error de Lector-PDF")
    assert "RuntimeError: para copiar" in text
    assert "Qt: " in text


def test_installed_hooks_catch_errors_and_are_removed_again(qt_app, reporter):
    reporter.show_dialogs = False
    before = sys.excepthook
    reporter.install()
    try:
        raise RuntimeError("through the hook")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    reporter.uninstall()
    assert sys.excepthook is before
    assert "through the hook" in reporter.log.entries()[0].details


def test_errors_in_background_threads_are_caught(qt_app, reporter):
    reporter.show_dialogs = False
    reporter.install()

    def fail():
        raise RuntimeError("in a thread")

    thread = threading.Thread(target=fail, name="trabajo")
    thread.start()
    thread.join()
    qt_app.processEvents()
    (entry,) = reporter.log.entries()
    assert "in a thread" in entry.details
    assert entry.where == "hilo trabajo"


def test_menu_copies_the_report_even_without_errors(window_with_reporter):
    window = window_with_reporter
    window.copy_report_action.trigger()
    assert "No hay errores registrados." in QGuiApplication.clipboard().text()
    assert "Informe de error copiado" in window.statusBar().currentMessage()


def test_test_error_from_the_menu_is_recorded_and_the_window_stays_open(
    qt_app, window_with_reporter, reporter
):
    window = window_with_reporter
    reporter.show_dialogs = False
    reporter.install(window)
    assert window.test_error_action.isVisible()
    window.test_error_action.trigger()
    qt_app.processEvents()
    assert window.isVisible()
    (entry,) = reporter.log.entries()
    assert ProvokedError.__name__ in entry.details
    window.copy_report_action.trigger()
    assert "Error de prueba provocado" in QGuiApplication.clipboard().text()
