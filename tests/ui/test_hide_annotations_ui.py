"""Tests for seeing the document clean: hiding and showing the annotations."""

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtTest import QTest

from app.core.drawing import DRAW, ERASER
from app.ui.features import Mode
from app.ui.print_dialog import PrintDialog
from app.ui.print_run import PrintRun

LEFT, NO_KEYS = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
WAY = [(100, 100), (140, 120), (180, 100), (220, 160)]


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
        return view, path

    return open_it


def place(view, page: int, x: float, y: float) -> QPoint:
    zoom = view._render_zoom()
    return QPoint(
        view._to_units(view._page_left(page) + x * zoom),
        view._to_units(view._tops[page] - view._scroll_y() + y * zoom),
    )


def drag(view, page: int, *points) -> None:
    spots = [place(view, page, x, y) for x, y in points]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    for spot in spots[1:]:
        QTest.mouseMove(view.viewport(), spot)
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spots[-1])


def settle(view, wait_until) -> None:
    wait_until(
        lambda: (
            not view._changing
            and not view._asked_notes
            and not view._stale.intersection(view._visible_pages())
        )
    )


def red_at(view, page: int, x: float, y: float) -> bool:
    """Whether the picture of the window is red at a point of a page."""
    picture = view.viewport().grab().toImage()
    spot = place(view, page, x, y) * picture.devicePixelRatio()
    colour = picture.pixelColor(spot)
    return colour.red() > 150 and colour.green() < 110


def drawn(window, view, wait_until) -> None:
    window.use_writing_tool(DRAW)
    view.draw_color, view.draw_width = (0.9, 0.0, 0.0), 6.0
    drag(view, 0, *WAY)
    view.set_markup_tool("")
    settle(view, wait_until)
    assert red_at(view, 0, 140, 120)


def test_hiding_shows_the_page_clean_and_showing_brings_everything_back(
    window, opened, wait_until, capsys
):
    view, path = opened()
    drawn(window, view, wait_until)
    window.set_mode(Mode.STUDY)
    action = window.feature_actions["hide_annotations"]
    assert not action.isChecked()
    action.trigger()
    settle(view, wait_until)
    assert not view.annotations_shown and action.isChecked()
    assert not red_at(view, 0, 140, 120)
    assert "no se ha borrado nada" in window.statusBar().currentMessage()
    assert len(view.drawings_of(0)) == 1, "it is still in the document"
    action.trigger()
    settle(view, wait_until)
    assert view.annotations_shown and not action.isChecked()
    assert red_at(view, 0, 140, 120)
    assert "Traceback" not in capsys.readouterr().err


def test_hidden_annotations_are_saved_all_the_same(window, opened, wait_until):
    view, path = opened()
    drawn(window, view, wait_until)
    window.toggle_annotations()
    assert window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    with pymupdf.open(path) as doc:
        page = doc[0]
        assert [annotation.type[1] for annotation in page.annots()] == ["Ink"]
    assert not view.annotations_shown, "saving does not bring them back to sight"


def test_what_is_hidden_cannot_be_picked_or_erased(window, opened, wait_until):
    view, _ = opened()
    drawn(window, view, wait_until)
    spot = place(view, 0, 140, 120)
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, spot)
    assert view.picked_item() is not None
    window.toggle_annotations()
    settle(view, wait_until)
    assert view.picked_item() is None, "hiding lets go of what was picked"
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, spot)
    assert view.picked_item() is None and view.item_under(spot) is None
    window.use_writing_tool(ERASER)
    drag(view, 0, (140, 110), (140, 120), (140, 130))
    settle(view, wait_until)
    assert len(view.drawings_of(0)) == 1 and not view.annotations_shown


def test_putting_something_new_brings_them_all_back(window, opened, wait_until):
    view, _ = opened()
    drawn(window, view, wait_until)
    window.toggle_annotations()
    settle(view, wait_until)
    window.use_writing_tool(DRAW)
    drag(view, 0, (100, 300), (200, 300))
    settle(view, wait_until)
    assert view.annotations_shown and len(view.drawings_of(0)) == 2
    assert red_at(view, 0, 140, 120) and red_at(view, 0, 150, 300)
    assert not window.feature_actions["hide_annotations"].isChecked()


def test_undoing_brings_them_back_too(window, opened, wait_until):
    view, _ = opened()
    drawn(window, view, wait_until)
    drag_again = [(100, 300), (200, 300)]
    window.use_writing_tool(DRAW)
    drag(view, 0, *drag_again)
    settle(view, wait_until)
    window.toggle_annotations()
    window.undo()
    settle(view, wait_until)
    assert view.annotations_shown and red_at(view, 0, 140, 120)


def test_each_document_hides_its_own(window, opened, wait_until):
    first, _ = opened("boe.pdf")
    window.toggle_annotations()
    second, _ = opened("largo.pdf")
    assert second is not first and second.annotations_shown
    assert not window.feature_actions["hide_annotations"].isChecked()
    window.document_tabs.setCurrentIndex(0)
    assert window.feature_actions["hide_annotations"].isChecked()


def test_a_document_opens_with_everything_in_sight(window, opened, wait_until):
    view, path = opened()
    window.toggle_annotations()
    assert window.close_document(window.document_tabs.currentIndex()) is not False
    again, _ = opened()
    assert again.annotations_shown


def test_without_a_document_it_says_so(window):
    window.toggle_annotations()
    assert "Abre primero" in window.statusBar().currentMessage()
    assert not window.feature_actions["hide_annotations"].isChecked()


def test_it_is_in_the_view_menu_and_in_the_function_finder(window):
    action = window.feature_actions["hide_annotations"]
    menus = [menu for menu in window.menuBar().actions() if action in menu.menu().actions()]
    assert menus and not action.icon().isNull()
    assert "hide_annotations" in window.feature_handlers


# ---- printing ----------------------------------------------------------------------


def file_printer(path) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    return printer


def printed_red(path) -> bool:
    with pymupdf.open(path) as doc:
        pixmap = doc[0].get_pixmap(dpi=40)
    return any(
        pixmap.pixel(x, y)[0] > 150 and pixmap.pixel(x, y)[1] < 110
        for x in range(pixmap.width)
        for y in range(pixmap.height)
    )


@pytest.mark.parametrize("annotations", [True, False])
def test_the_pages_are_printed_with_or_without_annotations(
    window, opened, wait_until, tmp_path, annotations
):
    view, _ = opened()
    drawn(window, view, wait_until)
    out = tmp_path / "impreso.pdf"
    run = PrintRun(view, file_printer(out), [0], annotations=annotations)
    ended = []
    run.finished.connect(lambda failed, cancelled: ended.append((failed, cancelled)))
    assert run.start()
    wait_until(lambda: ended)
    assert ended == [([], False)]
    assert printed_red(out) is annotations
    assert view.annotations_shown, "printing clean does not hide them on the screen"


def test_the_print_window_follows_what_is_seen_and_lets_choose(settings, qt_app):
    printers = ["Una impresora"]
    as_seen = PrintDialog(printers, printers[0], 5, 0, settings)
    assert as_seen.annotations_box.isChecked()
    as_seen.accept()
    assert as_seen.choices.annotations is True
    hidden = PrintDialog(printers, printers[0], 5, 0, settings, annotations=False)
    assert not hidden.annotations_box.isChecked()
    hidden.annotations_box.setChecked(True)
    hidden.accept()
    assert hidden.choices.annotations is True
    clean = PrintDialog(printers, printers[0], 5, 0, settings, annotations=False)
    clean.accept()
    assert clean.choices.annotations is False
