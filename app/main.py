"""Program entry point: creates the Qt application and shows the main window."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app import APP_NAME, __version__
from app.ui.main_window import MainWindow
from app.ui.theme import prepare_application

# Hidden option used by the automatic builds: open the window, then quit. It
# checks that the packaged program really starts and measures how long it takes.
AUTOCLOSE_FLAG = "--autoclose"


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
    if autoclose:
        QTimer.singleShot(0, qt_app.quit)
    try:
        return qt_app.exec()
    finally:
        window.reporter.uninstall()


if __name__ == "__main__":
    sys.exit(main())
