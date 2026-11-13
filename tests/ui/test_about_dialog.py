"""Tests for the "Acerca de" window."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app import __version__
from app.core import about
from app.ui.about_dialog import AboutDialog


def test_the_help_menu_opens_the_about_window(window, qt_app):
    assert "Acerca de" in window.about_action.text()
    dialog = window.show_about()
    qt_app.processEvents()
    assert dialog.isVisible()
    assert __version__ in dialog.title.text()
    assert "Affero" in dialog.notices.toPlainText()
    assert dialog.notices.isReadOnly()
    dialog.close()


def test_its_buttons_open_the_source_page_and_the_licences(qt_app, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(QUrl(url)))
    dialog = AboutDialog()
    dialog.source_button.click()
    dialog.licences_button.click()
    assert opened[0].toString() == about.SOURCE_URL
    assert opened[1].toLocalFile() == str(about.licence_folder())
    assert dialog.source_button.toolTip() and dialog.licences_button.toolTip()


def test_it_still_opens_if_the_notices_are_missing(qt_app, monkeypatch):
    monkeypatch.setattr(about, "notices_text", lambda: "")
    dialog = AboutDialog()
    assert "AGPL" in dialog.notices.toPlainText()
    assert about.SOURCE_URL in dialog.notices.toPlainText()
