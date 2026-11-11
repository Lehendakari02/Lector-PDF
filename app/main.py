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
# Hidden option of the automatic builds: --check-signing PDF P12_FILE PASSWORD
CHECK_SIGNING_FLAG = "--check-signing"
EXIT_SIGNING_FAILED = 4


def check_signing(source: str, certificate_file: str, password: str) -> int:
    """Sign a copy of ``source`` in a temporary folder; 0 if it worked.

    Used by the automatic builds to check that everything signing needs really
    is inside the packaged program.
    """
    import tempfile
    from pathlib import Path

    from app.core.signing import SigningError, load_p12_signer, sign_pdf

    with tempfile.TemporaryDirectory() as folder:
        try:
            signer = load_p12_signer(certificate_file, password)
            signed = sign_pdf(source, Path(folder) / "firmado.pdf", signer)
            return 0 if signed.stat().st_size > Path(source).stat().st_size else EXIT_SIGNING_FAILED
        except SigningError:
            return EXIT_SIGNING_FAILED


def main(argv: list[str] | None = None) -> int:
    """Start the program and return its exit code."""
    args = list(sys.argv if argv is None else argv)
    if CHECK_SIGNING_FLAG in args:
        values = args[args.index(CHECK_SIGNING_FLAG) + 1 :]
        return check_signing(*values[:3]) if len(values) >= 3 else EXIT_SIGNING_FAILED
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
