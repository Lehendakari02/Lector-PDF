"""Tests for protected PDFs (password) and damaged ones, in the window."""

import pytest
from PySide6.QtWidgets import QLineEdit

from app.core import render_service
from app.core.document import PdfDocument
from app.ui.password_dialog import PasswordDialog


@pytest.fixture
def quiet(window):
    window.show_problem_dialogs = False
    return window


def _cut_file(sample, tmp_path):
    whole = sample("boe.pdf").read_bytes()
    cut = tmp_path / "cortado.pdf"
    cut.write_bytes(whole[: len(whole) // 2])
    return cut


# ---- the password window ----


def test_password_dialog_insists_until_the_password_is_right(qt_app):
    tried = []

    def try_password(password):
        tried.append(password)
        return password == "lector"

    dialog = PasswordDialog("tema.pdf", try_password)
    dialog.show()
    assert dialog.password_edit.echoMode() == QLineEdit.EchoMode.Password
    assert not dialog.error_label.isVisibleTo(dialog)

    dialog.password_edit.setText("mala")
    dialog.open_button.click()
    assert dialog.isVisible(), "a wrong password keeps the window open"
    assert dialog.error_label.isVisibleTo(dialog)

    dialog.password_edit.setText("lector")
    dialog.open_button.click()
    assert not dialog.isVisible()
    assert dialog.result() == PasswordDialog.DialogCode.Accepted
    assert tried == ["mala", "lector"]
    dialog.deleteLater()


def test_password_can_be_shown_while_typing(qt_app):
    dialog = PasswordDialog("tema.pdf", lambda password: False)
    dialog.show_box.setChecked(True)
    assert dialog.password_edit.echoMode() == QLineEdit.EchoMode.Normal
    dialog.show_box.setChecked(False)
    assert dialog.password_edit.echoMode() == QLineEdit.EchoMode.Password
    dialog.deleteLater()


# ---- protected documents in the window ----


def test_a_protected_pdf_opens_with_its_password(quiet, sample, wait_until):
    asked = []

    def answer(path):
        asked.append(path.name)
        return PdfDocument(path, "lector")

    quiet.ask_password = answer
    assert quiet.open_document(sample("con-contrasena.pdf"))
    assert asked == ["con-contrasena.pdf"]
    assert quiet.pdf_view.page_count >= 1
    wait_until(lambda: 0 in quiet.pdf_view.cached_pages())  # really drawn, not only listed
    assert not quiet.pdf_view.failed_pages()


def test_giving_up_the_password_opens_nothing(quiet, sample):
    quiet.ask_password = lambda path: None
    assert not quiet.open_document(sample("con-contrasena.pdf"))
    assert quiet.documents == []
    assert quiet.pages.currentWidget() is quiet.welcome


def test_the_real_dialog_is_used_and_its_answer_opens_the_document(
    window, sample, monkeypatch, wait_until
):
    def type_the_password(dialog):
        dialog.password_edit.setText("mala")
        dialog.open_button.click()
        dialog.password_edit.setText("lector")
        dialog.open_button.click()
        return dialog.result()

    monkeypatch.setattr(PasswordDialog, "exec", type_the_password)
    assert window.open_document(sample("con-contrasena.pdf"))
    wait_until(lambda: 0 in window.pdf_view.cached_pages())


def test_cancelling_the_real_dialog_opens_nothing(window, sample, monkeypatch):
    monkeypatch.setattr(PasswordDialog, "exec", lambda dialog: PasswordDialog.DialogCode.Rejected)
    assert not window.open_document(sample("con-contrasena.pdf"))
    assert window.documents == []


def test_the_password_is_never_written_to_the_settings(quiet, sample, settings):
    quiet.ask_password = lambda path: PdfDocument(path, "lector")
    assert quiet.open_document(sample("con-contrasena.pdf"))
    quiet.close()
    assert "lector" not in settings.path.read_text(encoding="utf-8").replace("lector-pdf", "")


def test_coming_back_to_the_last_tabs_asks_for_the_password_again(
    qt_app, tmp_path, sample, monkeypatch
):
    from app.core.settings import Settings
    from app.ui.main_window import MainWindow

    path = tmp_path / "ajustes.json"
    first = MainWindow(Settings(path))
    first.ask_password = lambda file: PdfDocument(file, "lector")
    assert first.open_document(sample("con-contrasena.pdf"))
    first.close()
    first.deleteLater()

    asked = []
    monkeypatch.setattr(
        PasswordDialog, "exec", lambda dialog: asked.append(1) or PasswordDialog.DialogCode.Rejected
    )
    second = MainWindow(Settings(path))
    assert second.restore_session() == 0  # the user gave up: it is simply not opened
    assert asked == [1]
    second.close()
    second.deleteLater()


# ---- damaged documents ----


def test_a_file_cut_short_gives_a_notice_and_no_tab(quiet, sample, tmp_path):
    assert not quiet.open_document(_cut_file(sample, tmp_path))
    assert quiet.documents == []
    assert quiet.pages.currentWidget() is quiet.welcome
    assert "dañado" in quiet.statusBar().currentMessage()


def test_a_damaged_page_says_so_and_the_rest_can_be_read(quiet, sample, wait_until, monkeypatch):
    monkeypatch.setenv(render_service.TEST_CRASH_PAGES, "1")
    # A helper started before would not know about the bad page.
    quiet._spare.view.service.shutdown()
    quiet._spare = quiet._new_page()
    assert quiet.open_document(sample("boe.pdf"))
    view = quiet.pdf_view
    wait_until(lambda: view.failed_pages() == {1})
    wait_until(lambda: {0, 2} <= set(view.cached_pages()))
    assert view.service.restarts == 1
    view.scroll_to_page(1)
    view.viewport().grab()  # painting the notice of the bad page must not fail
    view.scroll_to_page(5)
    wait_until(lambda: 5 in view.cached_pages())
    assert view.service.restarts == 1, "the bad page is not tried again"
    assert len(quiet.documents) == 1  # the document stays open


def test_a_document_that_fails_after_opening_closes_its_tab(quiet, sample, wait_until):
    quiet.open_document(sample("boe.pdf"))
    quiet.open_document(sample("largo.pdf"))
    assert len(quiet.documents) == 2
    quiet.pdf_view.document_failed.emit("the helper process keeps crashing")
    assert [page.title for page in quiet.documents] == ["boe.pdf"]
    assert "largo.pdf" in quiet.statusBar().currentMessage()
    assert quiet.pdf_view.page_count == 39


def test_when_the_only_document_fails_the_welcome_page_comes_back(quiet, sample):
    quiet.open_document(sample("boe.pdf"))
    quiet.pdf_view.document_failed.emit("broken")
    assert quiet.documents == []
    assert quiet.pages.currentWidget() is quiet.welcome
    assert "boe.pdf" not in quiet.windowTitle()
