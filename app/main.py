"""Program entry point: creates the Qt application and shows the main window."""

import os
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from app import APP_NAME, __version__
from app.core.interface_size import NORMAL_SIZE, apply_before_start
from app.core.restart import relaunch
from app.core.settings import Settings
from app.core.single_instance import InstanceServer, send_to_running_copy
from app.ui.icons import logo_icon
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


class _OtherCopies(QObject):
    """Brings to the window the files another copy of the program was asked to open.

    The listening happens in a background thread; the signal carries the files
    safely to the thread of the interface.
    """

    files_arrived = Signal(list)


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

    # A file given on the command line ("Abrir con…", double click) is opened.
    files = [arg for arg in args[1:] if not arg.startswith("-")]
    # If the program is already open, its window opens the files in new tabs.
    if not autoclose and QApplication.instance() is None and send_to_running_copy(files):
        return 0

    # The size of the interface must be known before the application exists.
    settings = Settings()
    interface_size = NORMAL_SIZE
    if QApplication.instance() is None:
        interface_size = apply_before_start(settings, os.environ)
    qt_app = QApplication.instance() or QApplication(args)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setApplicationVersion(__version__)
    prepare_application(qt_app)
    qt_app.setWindowIcon(logo_icon())

    window = MainWindow(settings)
    window.interface_size = interface_size
    window.reporter.install(window)
    window.show()

    other_copies = _OtherCopies()
    other_copies.files_arrived.connect(window.open_from_another_copy)
    listening = None
    if not autoclose:
        listening = InstanceServer(other_copies.files_arrived.emit)
        listening.start()

    if autoclose:
        window.show_problem_dialogs = False
    opened = False
    if not autoclose:
        window.restore_session()  # the tabs of the last time, each on its page
    for file in files:  # each one in its own tab
        opened = window.open_document(file) or opened
    if not autoclose:
        window.warm_up()  # the next document will open without waiting

    if autoclose and opened:
        window.pdf_view.first_page_shown.connect(qt_app.quit)
        QTimer.singleShot(AUTOCLOSE_TIMEOUT_MS, lambda: qt_app.exit(EXIT_PAGE_NOT_SHOWN))
    elif autoclose:
        code = EXIT_PAGE_NOT_SHOWN if files else 0
        QTimer.singleShot(0, lambda: qt_app.exit(code))
    try:
        code = qt_app.exec()
    finally:
        if listening is not None:
            listening.close()  # from now on, a new copy is the main one
        window.shutdown_documents()
        window.reporter.uninstall()
    if window.restart_wanted:
        relaunch()  # everything is saved and the helpers are stopped
    return code


if __name__ == "__main__":
    sys.exit(main())
