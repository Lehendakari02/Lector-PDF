"""Program entry point: creates the Qt application and shows the main window."""

import sys

from PySide6.QtWidgets import QApplication

from app import APP_NAME, __version__
from app.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    """Start the program and return its exit code."""
    qt_app = QApplication(sys.argv if argv is None else argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
