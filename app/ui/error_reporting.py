"""Catches unexpected errors, records them and tells the user without closing."""

import sys
import threading
from types import TracebackType

from PySide6.QtCore import QObject, Signal, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from app.core.error_log import ErrorLog


class ProvokedError(RuntimeError):
    """The harmless error raised by "Provocar un error de prueba"."""


class ErrorReporter(QObject):
    """Connects Python's "unexpected error" hooks to the log and the window."""

    # Emitted in the interface thread after an error has been recorded.
    error_recorded = Signal(str)

    def __init__(self, log: ErrorLog | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.log = log if log is not None else ErrorLog()
        self.show_dialogs = True
        self._dialog: QMessageBox | None = None
        self._window: QWidget | None = None
        self._previous_hook = None
        self._previous_thread_hook = None
        self.error_recorded.connect(self._show_notice)

    def install(self, window: QWidget | None = None) -> None:
        """Start catching errors. ``window`` is where notices are shown."""
        self._window = window
        self._previous_hook = sys.excepthook
        self._previous_thread_hook = threading.excepthook
        sys.excepthook = self.handle
        threading.excepthook = self._handle_thread

    def uninstall(self) -> None:
        if self._previous_hook is not None:
            sys.excepthook = self._previous_hook
            threading.excepthook = self._previous_thread_hook
            self._previous_hook = None

    def handle(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
        where: str = "",
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        entry = self.log.record(exc_type, exc, tb, where)
        if sys.stderr is not None:  # there is none in the packaged Windows program
            print(entry.details, file=sys.stderr)
        # A signal, so errors from background threads reach the interface safely.
        self.error_recorded.emit(f"{exc_type.__name__}: {exc}")

    def _handle_thread(self, args: threading.ExceptHookArgs) -> None:
        name = args.thread.name if args.thread is not None else "?"
        self.handle(args.exc_type, args.exc_value, args.exc_traceback, f"hilo {name}")

    def report_text(self) -> str:
        return self.log.build_report([f"Qt: {qVersion()}"])

    def copy_report(self) -> str:
        """Put the report on the clipboard and return it."""
        text = self.report_text()
        QGuiApplication.clipboard().setText(text)
        return text

    def _show_notice(self, summary: str) -> None:
        if not self.show_dialogs or self._dialog is not None:
            return  # one notice at a time, however many errors arrive
        dialog = QMessageBox(self._window)
        dialog.setObjectName("errorNotice")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(self.tr("Ha ocurrido un error"))
        dialog.setText(self.tr("Algo ha fallado, pero el programa sigue abierto."))
        dialog.setInformativeText(
            self.tr(
                "El error se ha apuntado en este ordenador y no se envía a ningún sitio. "
                "Si quieres avisar del fallo, copia el informe y pégalo donde prefieras."
            )
        )
        dialog.setDetailedText(summary)
        copy_button = dialog.addButton(
            self.tr("Copiar informe de error"), QMessageBox.ButtonRole.ActionRole
        )
        dialog.addButton(self.tr("Cerrar"), QMessageBox.ButtonRole.RejectRole)
        copy_button.clicked.connect(self.copy_report)
        dialog.finished.connect(self._notice_closed)
        self._dialog = dialog
        dialog.open()

    def _notice_closed(self, _result: int) -> None:
        if self._dialog is not None:
            self._dialog.deleteLater()
            self._dialog = None
