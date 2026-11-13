"""Tests for the print window and for printing from the main window."""

import pymupdf
import pytest
from PySide6.QtGui import QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from app.core.printing import Scaling
from app.ui.print_dialog import PRINT_SETTING, PrintChoices, PrintDialog

PRINTERS = ["Impresora del salón", "Microsoft Print to PDF"]


@pytest.fixture
def dialog(qt_app, settings):
    made = PrintDialog(PRINTERS, "Microsoft Print to PDF", 39, 6, settings)
    made.show()
    yield made
    made.close()
    made.deleteLater()


def file_printer(path) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    return printer


# ---- the print window ----


def test_it_starts_with_sensible_choices(dialog):
    assert dialog.printer_box.currentText() == "Microsoft Print to PDF"  # the Windows default
    assert dialog.all_button.isChecked()
    assert dialog.copies_box.value() == 1
    assert dialog.scaling_box.currentData() is Scaling.FIT
    assert not dialog.both_sides_box.isChecked() and not dialog.grey_box.isChecked()
    assert "39" in dialog.pages_note.text()
    assert dialog.print_button.isEnabled()


def test_the_page_being_read_can_be_printed_alone(dialog):
    assert "7" in dialog.current_button.text()
    dialog.current_button.setChecked(True)
    assert dialog.pages() == [6]
    assert "1 página" in dialog.pages_note.text()


def test_typing_pages_chooses_them_and_counts_them(dialog):
    dialog.pages_edit.setText("1-3, 10")
    dialog.pages_edit.textEdited.emit("1-3, 10")
    assert dialog.some_button.isChecked()
    assert dialog.pages() == [0, 1, 2, 9]
    assert "4 páginas" in dialog.pages_note.text()
    assert dialog.print_button.isEnabled()


@pytest.mark.parametrize(("typed", "said"), [("40", "se sale"), ("uno", "No entiendo")])
def test_pages_that_make_no_sense_are_explained_and_cannot_be_printed(dialog, typed, said):
    dialog.pages_edit.setText(typed)
    dialog.pages_edit.textEdited.emit(typed)
    assert said in dialog.pages_note.text()
    assert not dialog.print_button.isEnabled()
    dialog.accept()
    assert dialog.choices is None and dialog.isVisible()


def test_accepting_gives_the_choices(dialog):
    dialog.printer_box.setCurrentIndex(0)
    dialog.pages_edit.setText("2-4")
    dialog.pages_edit.textEdited.emit("2-4")
    dialog.copies_box.setValue(3)
    dialog.scaling_box.setCurrentIndex(dialog.scaling_box.findData(Scaling.ACTUAL))
    dialog.both_sides_box.setChecked(True)
    dialog.grey_box.setChecked(True)
    dialog.print_button.click()
    assert dialog.choices == PrintChoices(
        "Impresora del salón", [1, 2, 3], 3, Scaling.ACTUAL, both_sides=True, grey=True
    )


def test_the_printer_and_the_way_are_remembered_but_not_the_pages(qt_app, settings):
    first = PrintDialog(PRINTERS, PRINTERS[1], 39, 0, settings)
    first.printer_box.setCurrentIndex(0)
    first.scaling_box.setCurrentIndex(first.scaling_box.findData(Scaling.ACTUAL))
    first.grey_box.setChecked(True)
    first.copies_box.setValue(5)
    first.pages_edit.setText("3")
    first.some_button.setChecked(True)
    first.accept()
    assert settings.get(PRINT_SETTING)["impresora"] == "Impresora del salón"

    second = PrintDialog(PRINTERS, PRINTERS[1], 39, 0, settings)
    assert second.printer_box.currentText() == "Impresora del salón"
    assert second.scaling_box.currentData() is Scaling.ACTUAL
    assert second.grey_box.isChecked()
    assert second.copies_box.value() == 1
    assert second.all_button.isChecked()
    for made in (first, second):
        made.deleteLater()


def test_a_remembered_printer_that_is_gone_falls_back_to_the_default(qt_app, settings):
    settings.set(PRINT_SETTING, {"impresora": "La de la oficina"})
    made = PrintDialog(PRINTERS, PRINTERS[1], 5, 0, settings)
    assert made.printer_box.currentText() == PRINTERS[1]
    made.deleteLater()


def test_strange_stored_choices_are_ignored(qt_app, settings):
    settings.set(PRINT_SETTING, "roto")
    made = PrintDialog(PRINTERS, PRINTERS[0], 5, 0, settings)
    assert made.scaling_box.currentData() is Scaling.FIT
    made.deleteLater()


# ---- printing from the main window ----


@pytest.fixture
def quiet(window):
    window.show_problem_dialogs = False
    return window


def test_print_is_a_working_function_with_its_shortcut(quiet):
    assert "print" in quiet.feature_handlers
    assert "todavía no" not in quiet.feature_actions["print"].toolTip()
    assert quiet.print_action.shortcut().toString() == "Ctrl+P"


def test_without_a_document_there_is_nothing_to_print(quiet):
    quiet.print_document()
    assert "Abre primero" in quiet.statusBar().currentMessage()


def test_without_printers_it_says_so(quiet, sample, monkeypatch):
    quiet.open_document(sample("boe.pdf"))
    monkeypatch.setattr(QPrinterInfo, "availablePrinterNames", staticmethod(lambda: []))
    quiet.print_document()
    assert "impresora" in quiet.statusBar().currentMessage()


def test_printing_some_pages_of_the_open_document(quiet, sample, tmp_path, wait_until):
    quiet.open_document(sample("boe.pdf"))
    out = tmp_path / "impreso.pdf"
    choices = PrintChoices("", [0, 2, 4], grey=True)
    assert quiet.start_printing(file_printer(out), choices)
    wait_until(lambda: quiet._print_run is None)
    assert "3 páginas enviadas" in quiet.statusBar().currentMessage()
    with pymupdf.open(out) as printed:
        assert printed.page_count == 3


def test_a_second_job_waits_for_the_first(quiet, sample, tmp_path, wait_until):
    quiet.open_document(sample("largo.pdf"))
    assert quiet.start_printing(file_printer(tmp_path / "a.pdf"), PrintChoices("", list(range(30))))
    quiet.print_document()
    assert "Espera" in quiet.statusBar().currentMessage()
    wait_until(lambda: quiet._print_run is None)


def test_the_dialog_answer_is_what_gets_printed(quiet, sample, tmp_path, wait_until, monkeypatch):
    quiet.open_document(sample("boe.pdf"))
    out = tmp_path / "impreso.pdf"
    monkeypatch.setattr(QPrinterInfo, "availablePrinterNames", staticmethod(lambda: PRINTERS))
    monkeypatch.setattr(QPrinterInfo, "defaultPrinterName", staticmethod(lambda: PRINTERS[0]))

    def choose(dialog):
        dialog.pages_edit.setText("38-39")
        dialog.pages_edit.textEdited.emit("38-39")
        dialog.print_button.click()
        return dialog.result()

    monkeypatch.setattr(PrintDialog, "exec", choose)
    started = []

    def start(printer, choices):
        started.append(choices)
        return type(quiet).start_printing(quiet, file_printer(out), choices)

    monkeypatch.setattr(quiet, "start_printing", start)
    quiet.print_document()
    wait_until(lambda: started and quiet._print_run is None)
    assert started[0].printer == PRINTERS[0]
    assert started[0].pages == [37, 38]
    with pymupdf.open(out) as printed:
        assert printed.page_count == 2


def test_cancelling_the_dialog_prints_nothing(quiet, sample, monkeypatch):
    quiet.open_document(sample("boe.pdf"))
    monkeypatch.setattr(QPrinterInfo, "availablePrinterNames", staticmethod(lambda: PRINTERS))
    monkeypatch.setattr(PrintDialog, "exec", lambda dialog: PrintDialog.DialogCode.Rejected)
    quiet.print_document()
    assert quiet._print_run is None


def test_damaged_pages_are_named_when_the_job_ends(quiet, sample, tmp_path, wait_until):
    quiet.open_document(sample("boe.pdf"))
    assert quiet.start_printing(file_printer(tmp_path / "a.pdf"), PrintChoices("", [0, 1]))
    run = quiet._print_run
    wait_until(lambda: quiet._print_run is None)
    # The same ending, with two pages that could not be drawn.
    from PySide6.QtWidgets import QProgressDialog

    progress = QProgressDialog(quiet)
    progress.canceled.connect(run.cancel)
    quiet._printing_finished(run, progress, [4, 8], False)
    message = quiet.statusBar().currentMessage()
    assert "5, 9" in message and "no se han impreso" in message


def test_closing_the_program_while_printing_cancels_cleanly(quiet, sample, tmp_path):
    quiet.open_document(sample("largo.pdf"))
    assert quiet.start_printing(
        file_printer(tmp_path / "a.pdf"), PrintChoices("", list(range(200)))
    )
    quiet.close()
    assert quiet._print_run is None
