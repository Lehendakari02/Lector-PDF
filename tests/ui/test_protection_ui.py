"""Tests for «Comprimir» and «Contraseña» in the window."""

import shutil

import pytest

from app.core.compress import STRONG
from app.core.document import PdfDocument
from app.core.protection import state_of
from app.ui.main_window import COMPRESS_SETTING, Mode
from app.ui.organize_dialogs import CompressDialog, ProtectDialog
from tests.core.test_protection import picture_document


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False
    window.organize_target_answer = lambda proposal: proposal

    def open_it(name="boe.pdf", password=None):
        path = tmp_path / name
        if not path.exists():
            shutil.copy(sample(name), path)
        if password:
            window.ask_password = lambda where: PdfDocument(where, password)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages())
        return view, path

    return open_it


def picture_pdf(path):
    picture_document(path)


def test_compressing_makes_a_smaller_copy(window, opened, tmp_path):
    picture_pdf(tmp_path / "foto.pdf")
    view, path = opened("foto.pdf")
    before = path.read_bytes()

    def answer(dialog):
        dialog.strong.setChecked(True)
        return True

    window.compress_answer = answer
    window.save_first_answer = True
    window.set_mode(Mode.ORGANIZE)
    assert not view.modified and not view.saving
    window.feature_actions["compress"].trigger()
    copy = tmp_path / "foto (comprimido).pdf"
    assert window.last_file_work[0] == "done"
    assert copy.stat().st_size < len(before)
    assert path.read_bytes() == before, "the document does not change"
    assert "comprimido" in window.statusBar().currentMessage()
    assert window.settings.get(COMPRESS_SETTING) == STRONG, "remembered for next time"


def test_a_document_already_small_says_so(window, opened, tmp_path):
    opened("escaneado.pdf")
    window.compress_answer = lambda dialog: True
    assert not window.compress_document()
    assert window.last_file_work[0] == "not_smaller"
    assert not (tmp_path / "escaneado (comprimido).pdf").exists()


def test_putting_a_password_on_a_copy(window, opened, tmp_path):
    opened()

    def answer(dialog):
        assert not dialog.take_off.isVisible()
        dialog.first.setText("clave1")
        dialog.second.setText("clave1")
        return True

    window.protect_answer = answer
    window.feature_actions["password"].trigger()
    copy = tmp_path / "boe (con contraseña).pdf"
    assert state_of(copy) == "password"
    assert state_of(tmp_path / "boe.pdf") == "none"


def test_taking_the_password_off(window, opened, tmp_path):
    opened("con-contrasena.pdf", "lector")
    window.protect_answer = lambda dialog: dialog.removing
    assert window.change_password()
    assert state_of(tmp_path / "con-contrasena (sin contraseña).pdf") == "none"


def test_a_restricted_document_is_explained(window, opened):
    opened("restringido.pdf")
    window.protect_answer = lambda dialog: pytest.fail("no window to choose")
    assert not window.change_password()


def test_the_password_has_to_be_written_twice(qt_app):
    dialog = ProtectDialog(None, False, False)
    dialog.first.setText("clave1")
    dialog.second.setText("clave2")
    dialog.accept()
    assert dialog.result() != ProtectDialog.DialogCode.Accepted
    assert "no son iguales" in dialog.problem.text()
    dialog.first.setText("abc")
    dialog.second.setText("abc")
    dialog.accept()
    assert "al menos" in dialog.problem.text()
    dialog.deleteLater()


def test_a_signed_document_warns(qt_app):
    dialog = CompressDialog(None, "1 MB", True)
    assert not dialog.signed_note.isHidden()
    dialog.deleteLater()
    dialog = ProtectDialog(None, False, False)
    assert dialog.signed_note.isHidden()
    dialog.deleteLater()
