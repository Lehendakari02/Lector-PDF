"""Tests for coming back to the tabs of the last time and the recent files."""

import shutil

from app.core.history import RESTORE_SETTING
from app.ui.features import Mode
from app.ui.main_window import MainWindow


def open_samples(window, sample, *names):
    window.show_problem_dialogs = False
    for name in names:
        assert window.open_document(sample(name))


def start_again(settings) -> MainWindow:
    """As if the program had been closed and opened again."""
    window = MainWindow(settings)
    window.show_problem_dialogs = False
    window.show()
    return window


def test_tabs_come_back_each_on_its_page(window, sample, settings):
    open_samples(window, sample, "boe.pdf", "largo.pdf", "formulario.pdf")
    window.document_tabs.setCurrentIndex(0)
    window.pdf_view.scroll_to_page(12)
    window.document_tabs.setCurrentIndex(1)
    window.pdf_view.scroll_to_page(333)
    window.close()

    again = start_again(settings)
    try:
        assert again.restore_session() == 3
        assert [page.title for page in again.documents] == [
            "boe.pdf",
            "largo.pdf",
            "formulario.pdf",
        ]
        assert again.document_tabs.currentIndex() == 1  # the one that was in front
        assert again.pdf_view.current_page == 333
        again.document_tabs.setCurrentIndex(0)
        assert again.pdf_view.current_page == 12
    finally:
        again.close()


def test_nothing_to_restore_the_first_time(window):
    assert window.restore_session() == 0
    assert window.pages.currentWidget() is window.welcome


def test_closed_tabs_do_not_come_back(window, sample, settings):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    window.close_document(0)
    window.close()
    again = start_again(settings)
    try:
        assert again.restore_session() == 1
        assert again.documents[0].title == "largo.pdf"
    finally:
        again.close()


def test_a_document_that_is_gone_is_skipped(window, sample, settings, tmp_path):
    moved = tmp_path / "se-va.pdf"
    shutil.copy(sample("formulario.pdf"), moved)
    open_samples(window, sample, "boe.pdf")
    assert window.open_document(moved)
    window.close()
    moved.unlink()
    again = start_again(settings)
    try:
        assert again.restore_session() == 1
        assert again.documents[0].title == "boe.pdf"
        assert "No se han encontrado 1" in again.statusBar().currentMessage()
    finally:
        again.close()


def test_restoring_can_be_turned_off(window, sample, settings):
    open_samples(window, sample, "boe.pdf")
    window.close()
    settings.set(RESTORE_SETTING, False)
    again = start_again(settings)
    try:
        assert again.restore_session() == 0
        assert again.documents == []
    finally:
        again.close()


def test_a_document_reopens_on_the_page_where_it_was_left(window, sample):
    open_samples(window, sample, "largo.pdf")
    window.pdf_view.scroll_to_page(77)
    window.close_document()
    open_samples(window, sample, "largo.pdf")
    assert window.pdf_view.current_page == 77
    assert window.page_box.edit.text() == "78"


def test_every_document_keeps_its_work_mode(window, sample, settings):
    open_samples(window, sample, "boe.pdf", "formulario.pdf")
    window.set_mode(Mode.FILL_SIGN)  # the form is for filling in
    window.document_tabs.setCurrentIndex(0)
    assert window.mode is Mode.READ
    window.set_mode(Mode.STUDY)
    window.document_tabs.setCurrentIndex(1)
    assert window.mode is Mode.FILL_SIGN
    window.close()
    again = start_again(settings)
    try:
        again.restore_session()
        assert again.mode is Mode.FILL_SIGN
        again.document_tabs.setCurrentIndex(0)
        assert again.mode is Mode.STUDY
    finally:
        again.close()


def test_recent_files_menu(window, sample):
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    window.close_document()
    window.close_document()
    window.recent_menu.aboutToShow.emit()
    actions = window.recent_menu.actions()
    assert "largo.pdf" in actions[0].text() and "boe.pdf" in actions[1].text()
    actions[1].trigger()
    assert window.documents[0].title == "boe.pdf"
    window.recent_menu.aboutToShow.emit()
    assert "boe.pdf" in window.recent_menu.actions()[0].text()  # now the newest


def test_recent_files_on_the_welcome_page(window, sample):
    from PySide6.QtWidgets import QPushButton

    assert not window.welcome_recent.isVisible()
    open_samples(window, sample, "boe.pdf", "largo.pdf")
    window.close_document()
    window.close_document()
    assert window.welcome_recent.isVisible()
    buttons = window.welcome_recent.findChildren(QPushButton)
    assert [button.text() for button in buttons] == ["largo.pdf", "boe.pdf"]
    buttons[1].click()
    assert window.documents[0].title == "boe.pdf"


def test_recent_list_can_be_emptied(window, sample):
    open_samples(window, sample, "boe.pdf")
    window.close_document()
    window.forget_recent()
    assert not window.welcome_recent.isVisible()
    window.recent_menu.aboutToShow.emit()
    actions = window.recent_menu.actions()
    assert len(actions) == 1 and not actions[0].isEnabled()
