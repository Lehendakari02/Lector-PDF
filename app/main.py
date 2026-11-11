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
# Hidden option of the automatic builds: --check-ocr PDF WORD_IT_MUST_READ
CHECK_OCR_FLAG = "--check-ocr"
EXIT_OCR_FAILED = 5


def check_signing(source: str, certificate_file: str, password: str) -> int:
    """Sign a copy of ``source`` in a temporary folder; 0 if it worked.

    Used by the automatic builds to check that everything signing needs really
    is inside the packaged program.
    """
    import tempfile
    from pathlib import Path

    from app.core.signing import load_p12_signer, sign_pdf

    with tempfile.TemporaryDirectory() as folder:
        signer = load_p12_signer(certificate_file, password)
        signed = sign_pdf(source, Path(folder) / "firmado.pdf", signer)
        return 0 if signed.stat().st_size > Path(source).stat().st_size else EXIT_SIGNING_FAILED


def _run_check(check, failure_code: int) -> int:
    """Run a self-check so that it always ends with an exit code.

    The packaged program has no console: an error that escaped would open a
    message box and wait there for ever. The details go to the file named in
    ``LECTOR_PDF_CHECK_LOG``, if set.
    """
    import os
    import traceback

    try:
        return check()
    except BaseException:
        log = os.environ.get("LECTOR_PDF_CHECK_LOG")
        if log:
            with open(log, "a", encoding="utf-8") as out:
                out.write(traceback.format_exc())
        return failure_code


def check_ocr(source: str, expected_word: str) -> int:
    """Recognise the first page of ``source``; 0 if ``expected_word`` is read.

    Used by the automatic builds to check that text recognition works inside
    the packaged program, with nothing else installed.
    """
    from app.core.ocr import recognize_file_page

    text = recognize_file_page(source, 0).text
    return 0 if expected_word in text else EXIT_OCR_FAILED


def main(argv: list[str] | None = None) -> int:
    """Start the program and return its exit code."""
    args = list(sys.argv if argv is None else argv)
    if CHECK_OCR_FLAG in args:
        values = args[args.index(CHECK_OCR_FLAG) + 1 :]
        if len(values) < 2:
            return EXIT_OCR_FAILED
        return _run_check(lambda: check_ocr(*values[:2]), EXIT_OCR_FAILED)
    if CHECK_SIGNING_FLAG in args:
        values = args[args.index(CHECK_SIGNING_FLAG) + 1 :]
        if len(values) < 3:
            return EXIT_SIGNING_FAILED
        return _run_check(lambda: check_signing(*values[:3]), EXIT_SIGNING_FAILED)
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
