"""Tests for sending pages to a printer (here, a printer that writes a PDF file)."""

import pymupdf
import pytest
from PySide6.QtGui import QPageSize
from PySide6.QtPrintSupport import QPrinter

from app.core import render_service
from app.core.document import PdfDocument
from app.core.printing import Scaling
from app.ui.pdf_view import PdfView
from app.ui.print_run import PrintRun


@pytest.fixture
def view(qt_app):
    made = PdfView()
    made.resize(800, 600)
    made.show()
    yield made
    made.service.shutdown()
    made.close()
    made.deleteLater()


def file_printer(path) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    return printer


def run_to_the_end(run, wait_until):
    ended = []
    steps = []
    run.finished.connect(lambda failed, cancelled: ended.append((failed, cancelled)))
    run.progress.connect(lambda done, total: steps.append((done, total)))
    assert run.start()
    wait_until(lambda: ended)
    return ended[0], steps


def ink(page) -> float:
    """Share of the sheet that is not white."""
    pixmap = page.get_pixmap(dpi=20, colorspace=pymupdf.csGRAY)
    dark = sum(1 for value in pixmap.samples if value < 200)
    return dark / len(pixmap.samples)


def test_the_chosen_pages_come_out_in_order(view, sample, tmp_path, wait_until):
    view.set_document(PdfDocument(sample("boe.pdf")))
    out = tmp_path / "impreso.pdf"
    run = PrintRun(view, file_printer(out), [4, 0, 1, 2, 9])
    (failed, cancelled), steps = run_to_the_end(run, wait_until)
    assert (failed, cancelled) == ([], False)
    assert steps[0] == (0, 5) and steps[-1] == (5, 5)
    with pymupdf.open(out) as printed:
        assert printed.page_count == 5
        assert all(ink(page) > 0.005 for page in printed), "no sheet may come out blank"
        # A4 sheets, upright.
        assert round(printed[0].rect.width) == 595 and round(printed[0].rect.height) == 842


def test_what_is_printed_is_the_page_itself(view, tmp_path, wait_until):
    """Each sheet carries the picture of its own page, not of another one."""
    source = tmp_path / "bloques.pdf"
    with pymupdf.open() as doc:
        for number in range(4):  # page N has a black block in the Nth quarter, top to bottom
            page = doc.new_page(width=595, height=842)
            top = 60 + number * 190
            page.draw_rect(pymupdf.Rect(100, top, 495, top + 120), fill=(0, 0, 0))
        doc.save(source)
    view.set_document(PdfDocument(source))
    out = tmp_path / "impreso.pdf"
    run_to_the_end(PrintRun(view, file_printer(out), [2, 0, 3]), wait_until)

    def darkest_quarter(page) -> int:
        pixmap = page.get_pixmap(dpi=20, colorspace=pymupdf.csGRAY)
        rows = pixmap.height // 4
        dark = []
        for quarter in range(4):
            chunk = pixmap.samples[
                quarter * rows * pixmap.stride : (quarter + 1) * rows * pixmap.stride
            ]
            dark.append(sum(1 for value in chunk if value < 100))
        return dark.index(max(dark))

    with pymupdf.open(out) as printed:
        assert [darkest_quarter(page) for page in printed] == [2, 0, 3]


def test_a_landscape_page_gets_a_landscape_sheet(view, tmp_path, wait_until):
    source = tmp_path / "mixto.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=595, height=842).insert_text((72, 100), "De pie", fontsize=40)
        doc.new_page(width=842, height=595).insert_text((72, 100), "Tumbada", fontsize=40)
        doc.new_page(width=595, height=842).insert_text((72, 100), "De pie", fontsize=40)
        doc.save(source)
    view.set_document(PdfDocument(source))
    out = tmp_path / "impreso.pdf"
    run_to_the_end(PrintRun(view, file_printer(out), [0, 1, 2]), wait_until)
    with pymupdf.open(out) as printed:
        shapes = [page.rect.width > page.rect.height for page in printed]
    assert shapes == [False, True, False]


def test_real_size_and_fit_place_a_small_page_differently(view, tmp_path, wait_until):
    source = tmp_path / "pequeno.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=300)
        page.draw_rect(page.rect, color=(0, 0, 0), fill=(0, 0, 0))
        doc.save(source)
    view.set_document(PdfDocument(source))
    shares = {}
    for scaling in (Scaling.FIT, Scaling.ACTUAL):
        out = tmp_path / f"{scaling.value}.pdf"
        run_to_the_end(PrintRun(view, file_printer(out), [0], scaling), wait_until)
        with pymupdf.open(out) as printed:
            shares[scaling] = ink(printed[0])
    assert shares[Scaling.FIT] > 0.6  # grows to fill the sheet
    assert 0.05 < shares[Scaling.ACTUAL] < 0.2  # 200x300 points on an A4 sheet: about 12 %


def test_a_damaged_page_is_left_out_and_reported(view, sample, tmp_path, wait_until, monkeypatch):
    monkeypatch.setenv(render_service.TEST_CRASH_PAGES, "2")
    view.set_document(PdfDocument(sample("boe.pdf")))
    out = tmp_path / "impreso.pdf"
    run = PrintRun(view, file_printer(out), [0, 1, 2, 3, 4, 5, 6])
    (failed, cancelled), _steps = run_to_the_end(run, wait_until)
    assert (failed, cancelled) == ([2], False)
    with pymupdf.open(out) as printed:
        assert printed.page_count == 6


def test_cancelling_stops_the_job(view, sample, tmp_path, wait_until):
    view.set_document(PdfDocument(sample("largo.pdf")))
    run = PrintRun(view, file_printer(tmp_path / "impreso.pdf"), list(range(300)))
    ended = []
    run.finished.connect(lambda failed, cancelled: ended.append(cancelled))
    run.progress.connect(lambda done, total: run.cancel() if done == 2 else None)
    assert run.start()
    wait_until(lambda: ended)
    assert ended == [True]
    assert not run.running


def test_nothing_to_print_does_not_start(view, sample, tmp_path):
    view.set_document(PdfDocument(sample("boe.pdf")))
    assert not PrintRun(view, file_printer(tmp_path / "impreso.pdf"), []).start()


def test_reading_goes_on_while_printing(view, sample, tmp_path, wait_until):
    view.set_document(PdfDocument(sample("largo.pdf")))
    run = PrintRun(view, file_printer(tmp_path / "impreso.pdf"), list(range(40)))
    ended = []
    run.finished.connect(lambda failed, cancelled: ended.append(cancelled))
    assert run.start()
    view.scroll_to_page(200)
    wait_until(lambda: 200 in view.cached_pages())
    assert not ended, "the page on screen is drawn before the printing ends"
    wait_until(lambda: ended)
