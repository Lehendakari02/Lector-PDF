"""Tests for having several documents open in tabs."""

import shutil

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app import APP_NAME
from app.ui.side_panel import Tab


def open_samples(window, sample, *names):
    window.show_problem_dialogs = False
    for name in names:
        assert window.open_document(sample(name))


def test_no_tabs_until_a_document_is_open(window):
    assert not window.document_tabs.isVisible()
    assert window.documents == []
    assert window.pages.currentWidget() is window.welcome


def test_each_document_opens_in_its_own_tab(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    tabs = window.document_tabs
    assert tabs.isVisible()
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "boe.pdf",
        "largo.pdf",
        "formulario.pdf",
    ]
    assert tabs.currentIndex() == 2  # the one just opened is in front
    assert "formulario.pdf" in window.windowTitle()
    assert window.pdf_view.page_count == 1
    assert str(sample("largo.pdf")) == tabs.tabToolTip(1)


def test_switching_tabs_shows_the_other_document_where_it_was(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    window.pdf_view.scroll_to_page(100)
    window.document_tabs.setCurrentIndex(0)
    assert window.pdf_view.page_count == 39
    assert "boe.pdf" in window.windowTitle()
    assert window.page_box.total.text() == "de 39"
    window.pdf_view.scroll_to_page(7)
    window.document_tabs.setCurrentIndex(1)
    assert window.pdf_view.current_page == 100
    assert window.page_box.edit.text() == "101"
    assert window.page_box.total.text() == "de 520"
    window.document_tabs.setCurrentIndex(0)
    assert window.pdf_view.current_page == 7


def test_each_tab_keeps_its_own_zoom_search_and_panel(window, sample, wait_until):
    open_samples(window, sample, "texto-partido.pdf", "boe.pdf")
    window.pdf_view.set_zoom(2.0)
    window.show_search()
    window.show_side_panel(Tab.OUTLINE)
    window.document_tabs.setCurrentIndex(0)
    assert round(window.pdf_view.zoom, 2) != 2.0
    assert not window.search_panel.isVisible()
    assert not window.side_panel_action.isChecked()
    assert window.zoom_control.figure.text() != "200 %"
    window.show_search()
    panel = window.search_panel
    panel.box.setText("articulo")
    panel.search_now()
    wait_until(lambda: not panel._searching)
    assert panel.results.count() == 2
    window.document_tabs.setCurrentIndex(1)
    assert window.zoom_control.figure.text() == "200 %"
    assert window.search_panel.isVisible()
    assert window.search_panel.results.count() == 0
    assert window.side_panel_action.isChecked()


def test_tools_act_on_the_document_in_front(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    first, second = window.documents
    window.feature_actions["rotate_view"].trigger()
    assert second.view.rotation == 90 and first.view.rotation == 0
    window.document_tabs.setCurrentIndex(0)
    window.feature_actions["zoom_in"].trigger()
    window.zoom_control.bigger.click()
    assert first.view.zoom > second.view.zoom
    window.page_box.edit.setText("5")
    window.page_box.edit.returnPressed.emit()
    assert first.view.current_page == 4 and second.view.current_page == 0


def test_opening_a_document_that_is_already_open_goes_to_its_tab(window, sample, tmp_path):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    assert window.open_document(sample("boe.pdf"))
    assert len(window.documents) == 2
    assert window.document_tabs.currentIndex() == 0
    # The same file written another way is still the same file.
    assert window.open_document(str(sample("largo.pdf").parent / "." / "largo.pdf"))
    assert len(window.documents) == 2
    assert window.document_tabs.currentIndex() == 1
    # A copy with the same name in another folder is another document.
    copy = tmp_path / "boe.pdf"
    shutil.copy(sample("boe.pdf"), copy)
    assert window.open_document(copy)
    assert len(window.documents) == 3


def test_closing_tabs(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    middle = window.documents[1]
    window.document_tabs.tabCloseRequested.emit(1)
    assert len(window.documents) == 2
    assert not middle.view.service.is_running()
    assert [page.title for page in window.documents] == ["boe.pdf", "formulario.pdf"]
    assert "formulario.pdf" in window.windowTitle()
    window.close_tab_action.trigger()  # Ctrl+W closes the one in front
    assert [page.title for page in window.documents] == ["boe.pdf"]
    assert "boe.pdf" in window.windowTitle()
    assert window.pdf_view.page_count == 39
    window.close_tab_action.trigger()
    assert window.documents == []
    assert not window.document_tabs.isVisible()
    assert window.pages.currentWidget() is window.welcome
    assert window.windowTitle() == APP_NAME
    assert not window.page_box.isVisible()
    window.close_tab_action.trigger()  # nothing left: must not fail


def test_a_click_with_the_wheel_closes_a_tab(window, sample, qt_app):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    qt_app.processEvents()
    place = window.document_tabs.tabRect(0).center()
    QTest.mouseClick(window.document_tabs, Qt.MouseButton.MiddleButton, pos=place)
    assert [page.title for page in window.documents] == ["largo.pdf"]


def test_ctrl_tab_walks_through_the_tabs(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    window.next_tab_action.trigger()
    assert window.document_tabs.currentIndex() == 0  # after the last comes the first
    window.previous_tab_action.trigger()
    assert window.document_tabs.currentIndex() == 2
    window.previous_tab_action.trigger()
    assert window.document_tabs.currentIndex() == 1


def test_tabs_can_be_put_in_another_order(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    window.document_tabs.moveTab(2, 0)
    assert [page.title for page in window.documents] == ["formulario.pdf", "boe.pdf", "largo.pdf"]
    window.document_tabs.setCurrentIndex(1)
    assert window.pdf_view.page_count == 39


def test_a_file_that_cannot_be_opened_adds_no_tab(window, sample, tmp_path):
    open_samples(window, sample, "boe.pdf")
    broken = tmp_path / "roto.pdf"
    broken.write_bytes(b"not a pdf")
    assert not window.open_document(broken)
    assert not window.open_document(sample("con-contrasena.pdf"))
    assert len(window.documents) == 1
    assert window.pdf_view.page_count == 39
    assert window.open_document(sample("largo.pdf"))  # and the next one opens fine
    assert window.pdf_view.page_count == 520


def test_every_tab_has_its_own_helper_and_all_stop_on_exit(window, sample, wait_until):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    services = [page.view.service for page in window.documents]
    wait_until(lambda: all(0 in page.view.cached_pages() for page in window.documents))
    assert services[0].process_id != services[1].process_id
    window.close()
    assert not any(service.is_running() for service in services)


def test_the_next_helper_can_be_started_ahead(window, sample, wait_until):
    window.warm_up()
    spare = window.current_document
    assert spare.view.service.is_running()
    open_samples(window, sample, "boe.pdf")
    assert window.current_document is spare  # the page that was ready took the document
    wait_until(lambda: 0 in window.pdf_view.cached_pages())
    assert window._spare.view.service.is_running()  # and another one is getting ready


def test_full_screen_with_several_tabs(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    window.show_side_panel(Tab.THUMBNAILS)
    window.set_full_screen(True)
    assert not window.document_tabs.isVisible()
    assert not window.side_panel.isVisible()
    window.set_full_screen(False)
    assert window.document_tabs.isVisible()
    assert window.side_panel.isVisible()


def test_dropping_two_files_opens_two_tabs(window, sample):
    from PySide6.QtCore import QMimeData, QPointF, QUrl
    from PySide6.QtGui import QDropEvent

    window.show_problem_dialogs = False
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(sample(name))) for name in ("boe.pdf", "largo.pdf")])
    event = QDropEvent(
        QPointF(QPoint(50, 50)),
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(event)
    assert [page.title for page in window.documents] == ["boe.pdf", "largo.pdf"]


def test_the_button_of_a_tab_closes_that_tab(window, sample):
    from PySide6.QtWidgets import QTabBar

    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    button = window.document_tabs.tabButton(1, QTabBar.ButtonPosition.RightSide)
    assert button.accessibleName()
    button.click()
    assert [page.title for page in window.documents] == ["boe.pdf", "formulario.pdf"]
    window.document_tabs.tabButton(0, QTabBar.ButtonPosition.RightSide).click()
    assert [page.title for page in window.documents] == ["formulario.pdf"]
