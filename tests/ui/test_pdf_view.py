"""Tests for the continuous page view and opening documents in the window."""

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from app.core.document import PdfDocument
from app.main import AUTOCLOSE_FLAG, EXIT_PAGE_NOT_SHOWN, main
from app.ui import pdf_view
from app.ui.pdf_view import PdfView


@pytest.fixture
def view(qt_app):
    made = PdfView()
    made.resize(800, 600)
    made.show()
    qt_app.processEvents()
    yield made
    made.shutdown()
    made.close()


def show(view, path, wait_until):
    view.set_document(PdfDocument(path))
    wait_until(lambda: view.current_page in view.cached_pages())


def fills_the_width(view) -> bool:
    available = view.viewport().width() - 2 * pdf_view.SIDE_MARGIN
    return abs(view._widths[0] - available) <= 1


def wheel(view, steps: int) -> None:
    event = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, 120 * steps),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    view.wheelEvent(event)


def test_empty_view_has_no_pages_and_starts_no_helper(view):
    assert view.page_count == 0
    assert view.current_page == -1
    assert not view.service.is_running()


def test_shows_the_first_page_fitted_to_the_width(view, sample, wait_until):
    shown = []
    view.first_page_shown.connect(lambda: shown.append(True))
    show(view, sample("boe.pdf"), wait_until)
    wait_until(lambda: shown)
    assert view.page_count == 39
    assert view.current_page == 0
    # The page takes the whole width, minus the margins: no sideways scrolling.
    assert fills_the_width(view)
    assert view.horizontalScrollBar().maximum() == 0
    assert view.verticalScrollBar().maximum() > 0


def test_draws_only_the_pages_around_the_one_being_read(view, sample, wait_until):
    show(view, sample("largo.pdf"), wait_until)
    view.scroll_to_page(300)
    wait_until(lambda: 300 in view.cached_pages() and 303 in view.cached_pages())
    assert view.current_page == 300
    cached = view.cached_pages()
    assert all(page < 10 or 295 <= page <= 306 for page in cached), sorted(cached)


def test_page_changed_tells_page_and_total(view, sample, wait_until):
    seen = []
    view.page_changed.connect(lambda page, total: seen.append((page, total)))
    show(view, sample("boe.pdf"), wait_until)
    view.scroll_to_page(9)
    assert seen[0] == (1, 39)
    assert seen[-1] == (10, 39)


def test_zoom_in_and_out_keep_the_page_and_redraw_sharp(view, sample, wait_until):
    show(view, sample("boe.pdf"), wait_until)
    view.scroll_to_page(4)
    before = view.zoom
    view.zoom_in()
    assert view.zoom == pytest.approx(before * pdf_view.ZOOM_STEP)
    assert view.current_page == 4
    wait_until(lambda: view.cached_pages().get(4) == view._render_zoom())
    view.zoom_out()
    assert view.zoom == pytest.approx(before)
    assert view.current_page == 4


def test_zoom_has_limits(view, sample, wait_until):
    show(view, sample("escaneado.pdf"), wait_until)
    view.set_zoom(1000)
    assert view._zoom == pdf_view.MAX_ZOOM
    view.set_zoom(0.0001)
    assert view._zoom == pdf_view.MIN_ZOOM


def test_set_zoom_100_percent_means_real_size(view, sample, wait_until):
    show(view, sample("boe.pdf"), wait_until)
    view.set_zoom(1.0)
    # A4 is 595 points wide; at 100 % and 96 dots per inch that is 794 pixels.
    assert view._widths[0] == 794


def test_fit_width_follows_the_window_size(view, sample, wait_until, qt_app):
    show(view, sample("boe.pdf"), wait_until)
    view.resize(500, 600)
    qt_app.processEvents()
    assert fills_the_width(view)
    view.set_zoom(2.0)
    view.resize(700, 600)
    qt_app.processEvents()
    assert view.zoom == pytest.approx(2.0), "a zoom chosen by hand must not change on resize"
    view.fit_width()
    assert fills_the_width(view)


def test_ctrl_wheel_zooms(view, sample, wait_until):
    show(view, sample("boe.pdf"), wait_until)
    before = view.zoom
    wheel(view, 1)
    assert view.zoom > before
    wheel(view, -1)
    assert view.zoom == pytest.approx(before)


def test_keyboard_moves_through_the_document(view, sample, wait_until, qt_app):
    from PySide6.QtTest import QTest

    show(view, sample("boe.pdf"), wait_until)
    QTest.keyClick(view, Qt.Key.Key_End)
    assert view.current_page == 38
    QTest.keyClick(view, Qt.Key.Key_Home)
    assert view.current_page == 0
    QTest.keyClick(view, Qt.Key.Key_PageDown)
    assert view.verticalScrollBar().value() > 0


def test_cache_forgets_the_farthest_pages(view, sample, wait_until, monkeypatch):
    monkeypatch.setattr(pdf_view, "CACHE_BYTES", 6 * 1024 * 1024)
    show(view, sample("largo.pdf"), wait_until)
    for page in (50, 100, 150):
        view.scroll_to_page(page)
        wait_until(lambda page=page: page in view.cached_pages())
    assert view._cache_bytes <= 6 * 1024 * 1024
    assert 0 not in view.cached_pages()
    assert 150 in view.cached_pages()


def test_another_document_replaces_the_first(view, sample, wait_until):
    show(view, sample("largo.pdf"), wait_until)
    view.scroll_to_page(200)
    show(view, sample("escaneado.pdf"), wait_until)
    assert view.page_count == 3
    assert view.current_page == 0
    assert all(page < 3 for page in view.cached_pages())


def test_pages_come_back_after_the_helper_crashes(view, sample, wait_until):
    show(view, sample("largo.pdf"), wait_until)
    view.service._process.kill()
    wait_until(lambda: view.service.restarts == 1)
    view.scroll_to_page(40)
    wait_until(lambda: 40 in view.cached_pages())


def test_close_document_empties_the_view(view, sample, wait_until):
    show(view, sample("boe.pdf"), wait_until)
    view.close_document()
    assert view.page_count == 0
    assert view.cached_pages() == {}
    assert view.verticalScrollBar().maximum() == 0


# ---- in the main window ----------------------------------------------------


def test_window_opens_a_document_and_tells_where_you_are(window, sample, wait_until):
    window.show_problem_dialogs = False
    assert window.pages.currentWidget() is window.welcome
    assert window.open_document(sample("boe.pdf"))
    assert window.pages.currentWidget() is window.current_document
    assert "boe.pdf" in window.windowTitle()
    assert window.page_box.edit.text() == "1"
    assert window.page_box.total.text() == "de 39"
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
    assert "ms" in window.speed_label.text()
    window.pdf_view.scroll_to_page(11)
    assert window.page_box.edit.text() == "12"


def test_window_zoom_buttons_work(window, sample, wait_until):
    window.show_problem_dialogs = False
    window.open_document(sample("boe.pdf"))
    before = window.pdf_view.zoom
    window.feature_actions["zoom_in"].trigger()
    assert window.pdf_view.zoom > before
    assert window.zoom_control.figure.text() == f"{round(window.pdf_view.zoom * 100)} %"
    window.feature_actions["zoom_out"].trigger()
    window.feature_actions["zoom_out"].trigger()
    assert window.pdf_view.zoom < before
    window.feature_actions["fit_width"].trigger()
    assert fills_the_width(window.pdf_view)


@pytest.mark.parametrize("name", ["no-existe.pdf", "roto.pdf"])
def test_window_survives_files_it_cannot_open(window, tmp_path, name):
    window.show_problem_dialogs = False
    (tmp_path / "roto.pdf").write_bytes(b"not a pdf")
    assert not window.open_document(tmp_path / name)
    assert window.pages.currentWidget() is window.welcome
    assert "No se puede abrir" in window.statusBar().currentMessage()


def test_window_explains_password_documents(window, sample):
    window.show_problem_dialogs = False
    assert not window.open_document(sample("con-contrasena.pdf"))
    assert "contraseña" in window.statusBar().currentMessage()


def test_closing_the_window_stops_the_helper(qt_app, settings, sample, wait_until):
    from app.ui.main_window import MainWindow

    window = MainWindow(settings)
    window.show_problem_dialogs = False
    window.show()
    window.open_document(sample("boe.pdf"))
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
    process = window.pdf_view.service._process
    window.close()
    assert not process.is_alive()


# ---- from the command line -------------------------------------------------


def test_program_opens_the_file_it_is_given_and_shows_its_first_page(sample):
    assert main(["lector-pdf", AUTOCLOSE_FLAG, str(sample("largo.pdf"))]) == 0


def test_program_reports_a_file_it_cannot_show(tmp_path):
    assert main(["lector-pdf", AUTOCLOSE_FLAG, str(tmp_path / "nada.pdf")]) == EXIT_PAGE_NOT_SHOWN


# ---- turning the view, full screen and going to a page ----------------------


def test_rotating_the_view_turns_the_pages_and_keeps_the_place(view, sample, wait_until):
    show(view, sample("boe.pdf"), wait_until)
    view.scroll_to_page(5)
    upright = (view._widths[0], view._heights[0])
    seen = []
    view.rotation_changed.connect(seen.append)
    view.rotate_view()
    assert view.rotation == 90
    assert seen == [90]
    assert view.current_page == 5
    assert view._widths[0] > view._heights[0]  # the page now lies on its side
    wait_until(lambda: 5 in view.cached_pages())
    for _ in range(3):
        view.rotate_view()
    assert view.rotation == 0
    assert (view._widths[0], view._heights[0]) == upright


def test_a_new_document_starts_upright(view, sample, wait_until):
    show(view, sample("boe.pdf"), wait_until)
    view.rotate_view()
    show(view, sample("boe.pdf"), wait_until)
    assert view.rotation == 0


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_marks_follow_the_turned_page(view, tmp_path, wait_until, rotation):
    # A page with one black square: the turned mark must land on the turned square.
    import pymupdf

    path = tmp_path / "square.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=300)
        page.draw_rect(pymupdf.Rect(20, 40, 60, 70), color=(0, 0, 0), fill=(0, 0, 0))
        doc.save(path)
    show(view, path, wait_until)
    view.set_rotation(rotation)
    x0, y0, x1, y1 = view._shown_rect(0, (20, 40, 60, 70))
    with pymupdf.open(path) as doc:
        pixmap = doc[0].get_pixmap(matrix=pymupdf.Matrix(1, 1).prerotate(rotation))
    middle = pixmap.pixel(round((x0 + x1) / 2), round((y0 + y1) / 2))
    outside = pixmap.pixel(round(x0) - 5, round(y0) - 5)
    assert middle == (0, 0, 0)
    assert outside == (255, 255, 255)


def test_typing_a_page_number_goes_there(window, sample, wait_until, qt_app):
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    window.go_to_page_action.trigger()
    box = window.page_box
    box.edit.setText("20")
    box.edit.returnPressed.emit()
    assert window.pdf_view.current_page == 19
    box.edit.setText("999")  # further than the last page: go to the last one
    box.edit.returnPressed.emit()
    assert window.pdf_view.current_page == 38
    assert box.edit.text() == "39"


def test_page_box_is_hidden_without_a_document(window):
    assert not window.page_box.isVisible()
    window.go_to_page()  # must not fail
    assert "Abre primero" in window.statusBar().currentMessage()


def test_full_screen_shows_only_the_document(window, sample, qt_app):
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    window.full_screen_action.trigger()
    qt_app.processEvents()
    assert window.full_screen
    assert window.isFullScreen()
    assert not window.menu_button.isVisible()
    assert not window.statusBar().isVisible()
    assert not window.mode_bar.isVisible()
    assert not any(bar.isVisible() for bar in window.mode_toolbars.values())
    QTest.keyClick(window.pdf_view, Qt.Key.Key_Escape)
    qt_app.processEvents()
    assert not window.full_screen
    assert window.menu_button.isVisible()
    assert not window.menuBar().isVisible()  # its menus live behind the button
    assert window.statusBar().isVisible()
    assert window.mode_toolbars[window.mode].isVisible()


def test_rotate_button_turns_the_view(window, sample):
    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    window.feature_actions["rotate_view"].trigger()
    assert window.pdf_view.rotation == 90
    window.rotate_view_action.trigger()
    assert window.pdf_view.rotation == 180


def test_resizing_the_window_keeps_the_page_being_read(view, sample, wait_until, qt_app):
    show(view, sample("largo.pdf"), wait_until)
    view.fit_width()
    view.scroll_to_page(300)
    assert view.current_page == 300
    view.resize(500, 600)  # narrower: with "fit to width" every page gets smaller
    qt_app.processEvents()
    assert view.current_page == 300
    view.resize(1100, 600)
    qt_app.processEvents()
    assert view.current_page == 300


def test_huge_pages_are_not_drawn_again_and_again(view, sample, wait_until, monkeypatch, qt_app):
    # With a lot of zoom, the pages ahead do not fit in memory next to the ones
    # being read. They used to be asked for, thrown away and asked for again.
    monkeypatch.setattr(pdf_view, "CACHE_BYTES", 50 * 1024 * 1024)
    show(view, sample("boe.pdf"), wait_until)
    view.set_zoom(4.0)
    zoom = view._render_zoom()
    wait_until(lambda: view.cached_pages().get(view.current_page) == zoom)
    for _ in range(3):
        view.verticalScrollBar().setValue(view.verticalScrollBar().value() + 20)
        qt_app.processEvents()
        assert view._wanted == []
    assert view.current_page in view.cached_pages()


def test_a_page_number_past_the_end_can_be_typed_and_goes_to_the_last(window, sample, qt_app):
    """Typed on the keyboard, as a person does: Enter must not be swallowed."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    window.go_to_page_action.trigger()
    box = window.page_box
    box.edit.selectAll()
    QTest.keyClicks(box.edit, "500")
    QTest.keyClick(box.edit, Qt.Key.Key_Return)
    assert window.pdf_view.current_page == 38
    assert box.edit.text() == "39"
    box.edit.selectAll()
    QTest.keyClicks(box.edit, "0")
    QTest.keyClick(box.edit, Qt.Key.Key_Return)
    assert window.pdf_view.current_page == 0


def test_initial_size_brings_back_the_size_of_opening(window, sample, wait_until):
    from app.ui.pdf_view import Fit

    window.show_problem_dialogs = False
    assert window.open_document(sample("boe.pdf"))
    opened_at = window.pdf_view.zoom
    assert window.zoom_control.fit_comfortable_action.isChecked()
    window.feature_actions["zoom_in"].trigger()
    window.feature_actions["zoom_in"].trigger()
    assert window.pdf_view.zoom > opened_at
    assert not window.zoom_control.fit_comfortable_action.isChecked()
    window.feature_actions["fit_comfortable"].trigger()
    assert window.pdf_view.zoom == opened_at and window.pdf_view.fit is Fit.COMFORTABLE
    assert window.zoom_control.fit_comfortable_action.isChecked()
    window.feature_actions["fit_page"].trigger()
    window.initial_size_action.trigger()  # Ctrl+0
    assert window.pdf_view.zoom == opened_at
    window.feature_actions["fit_width"].trigger()
    window.zoom_control.fit_comfortable_action.trigger()
    assert window.pdf_view.zoom == opened_at
