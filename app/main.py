"""Program entry point: creates the Qt application and shows the main window."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app import APP_NAME, __version__
from app.ui.main_window import MainWindow
from app.ui.theme import prepare_application

# Hidden option used by the automatic builds: open the window, then quit. With
# a PDF it quits when the first page is on screen. It checks that the packaged
# program really starts and draws, and measures how long it takes.
AUTOCLOSE_FLAG = "--autoclose"
AUTOCLOSE_TIMEOUT_MS = 60_000
EXIT_PAGE_NOT_SHOWN = 3


def main(argv: list[str] | None = None) -> int:
    """Start the program and return its exit code."""
    args = list(sys.argv if argv is None else argv)
    autoclose = AUTOCLOSE_FLAG in args
    if autoclose:
        args.remove(AUTOCLOSE_FLAG)

    qt_app = QApplication.instance() or QApplication(args)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setApplicationVersion(__version__)
    prepare_application(qt_app)

    window = MainWindow()
    window.reporter.install(window)
    window.show()

    # A file given on the command line ("Abrir con…", double click) is opened.
    files = [arg for arg in args[1:] if not arg.startswith("-")]
    if autoclose:
        window.show_problem_dialogs = False
    opened = bool(files) and window.open_document(files[0])

    if autoclose and opened:
        window.pdf_view.first_page_shown.connect(qt_app.quit)
        QTimer.singleShot(AUTOCLOSE_TIMEOUT_MS, lambda: qt_app.exit(EXIT_PAGE_NOT_SHOWN))
    elif autoclose:
        code = EXIT_PAGE_NOT_SHOWN if files else 0
        QTimer.singleShot(0, lambda: qt_app.exit(code))
    try:
        return qt_app.exec()
    finally:
        window.pdf_view.shutdown()
        window.reporter.uninstall()


if __name__ == "__main__":
    sys.exit(main())
