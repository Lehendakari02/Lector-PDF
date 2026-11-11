"""Tests for the "sign with certificate" proof of concept in the window."""

import pytest
from pyhanko.pdf_utils.reader import PdfFileReader

from app.core.signing import load_p12_signer
from app.core.windows_store import describe
from app.ui.sign_dialog import CertificateDialog
from tests import certificates


@pytest.fixture(scope="module")
def store():
    """What a Windows store could hold: one good, one expired, one not for signing."""
    key = certificates.new_key()
    made = [
        certificates.make_certificate("Caducado", key, days_valid=-1, started_days_ago=30),
        certificates.make_certificate("PRUEBA PRUEBA ANA - 00000000T", key),
        certificates.make_certificate("Solo cifrado", key, for_signing=False),
    ]
    return [describe(certificates.der(certificate)) for certificate in made]


def test_dialog_lists_certificates_and_preselects_the_first_usable(qt_app, store):
    dialog = CertificateDialog(certificates=store)
    assert dialog.list.count() == 3
    assert dialog.list.currentRow() == 1
    assert dialog.selected() is store[1]
    assert dialog.sign_button.isEnabled()
    assert "PRUEBA PRUEBA ANA" in dialog.list.item(1).text()
    assert "Caduca el" in dialog.list.item(1).text()
    assert "CADUCADO" in dialog.list.item(0).text()
    assert "No sirve para firmar" in dialog.list.item(2).text()


def test_expired_certificates_cannot_be_chosen(qt_app, store):
    dialog = CertificateDialog(certificates=store)
    dialog.list.setCurrentRow(0)
    assert dialog.selected() is None
    assert not dialog.sign_button.isEnabled()
    dialog.use_selected()
    assert dialog.signer is None


def test_without_certificates_the_dialog_offers_a_file(qt_app):
    dialog = CertificateDialog(certificates=[])
    assert dialog.list.isHidden()
    assert not dialog.sign_button.isEnabled()
    assert ".p12" in dialog.explanation.text()
    assert dialog.file_button.isEnabled()


def test_certificate_file_with_right_and_wrong_password(qt_app, sample):
    dialog = CertificateDialog(certificates=[])
    assert not dialog.use_file(str(sample("certificado-prueba.p12")), "mala")
    assert dialog.signer is None
    assert "contraseña" in dialog.explanation.text()
    assert dialog.use_file(str(sample("certificado-prueba.p12")), "prueba")
    assert dialog.signer is not None
    assert dialog.result() == CertificateDialog.DialogCode.Accepted


def test_signing_needs_an_open_document(window):
    window.feature_actions["sign_certificate"].trigger()
    assert "Abre el documento" in window.statusBar().currentMessage()


def test_window_signs_the_open_document_into_a_copy(window, sample, tmp_path):
    window.show_problem_dialogs = False
    window.open_document(sample("formulario.pdf"))
    signer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    target = tmp_path / "formulario-firmado.pdf"
    assert window.sign_document(window.pdf_view.document_path, target, signer)
    assert "firmado" in window.statusBar().currentMessage().lower()
    with target.open("rb") as handle:
        assert len(PdfFileReader(handle).embedded_signatures) == 1


def test_window_refuses_to_overwrite_the_open_document(window, sample, tmp_path):
    window.show_problem_dialogs = False
    copy = tmp_path / "doc.pdf"
    copy.write_bytes(sample("formulario.pdf").read_bytes())
    window.open_document(copy)
    signer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    assert not window.sign_document(copy, copy, signer)
    assert copy.read_bytes() == sample("formulario.pdf").read_bytes()


def test_window_reports_a_document_that_cannot_be_signed(window, sample, tmp_path, settings):
    window.show_problem_dialogs = False
    window.reporter.show_dialogs = False
    signer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    broken = tmp_path / "roto.pdf"
    broken.write_bytes(b"not a pdf")
    assert not window.sign_document(broken, tmp_path / "salida.pdf", signer)
    assert "No se ha podido firmar" in window.statusBar().currentMessage()
    assert not (tmp_path / "salida.pdf").exists()
    assert not window.sign_document(sample("con-contrasena.pdf"), tmp_path / "salida.pdf", signer)
    assert "contraseña" in window.statusBar().currentMessage()
