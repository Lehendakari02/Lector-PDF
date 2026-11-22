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


def test_certificates_of_the_computer_are_set_apart(qt_app):
    """Windows keeps its own certificates among the personal ones; they name nobody."""
    key = certificates.new_key()
    authority = certificates.make_certificate("MS-Organization-Access", key, authority=True)
    made = [
        certificates.make_certificate("686ad455-b8bd-4c96-93a0-67df57b22300", key),
        certificates.make_certificate("Portátil de Ana", key, issuer=authority, issuer_key=key),
        certificates.make_certificate("PRUEBA PRUEBA ANA - 00000000T", key),
    ]
    store = [describe(certificates.der(certificate)) for certificate in made]
    assert [certificate.personal for certificate in store] == [False, False, True]
    assert [certificate.usable for certificate in store] == [False, False, True]

    dialog = CertificateDialog(certificates=store)
    assert dialog.selected() is store[2]
    assert "no identifica a una persona" in dialog.list.item(0).text()
    dialog.list.setCurrentRow(0)
    assert dialog.selected() is None
    assert not dialog.sign_button.isEnabled()


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


def test_the_open_document_is_signed_in_its_place_and_shown_again(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    copy = tmp_path / "doc-firmado.pdf"
    copy.write_bytes(sample("boe.pdf").read_bytes())
    assert window.open_document(copy)
    view = window.pdf_view
    wait_until(lambda: view.page_count > 2)
    view.scroll_to_page(2)
    wait_until(lambda: view.current_page == 2)
    window.signer_answer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    asked = []
    window.sign_target_answer = lambda suggested: asked.append(suggested) or str(suggested)
    assert window.sign_with_certificate()
    assert asked == [copy], "already a «-firmado» document: signed in its place"
    with copy.open("rb") as handle:
        assert len(PdfFileReader(handle).embedded_signatures) == 1
    assert len(window.documents) == 1 and window.current_document.path == copy
    wait_until(lambda: window.pdf_view.page_count > 2 and window.pdf_view.current_page == 2)
    assert window.versions.of(copy), "how it was is kept among the earlier versions"
    assert not list(tmp_path.glob(".firmado-*"))
    assert "PRUEBA" in window.statusBar().currentMessage()


def test_changes_not_saved_are_saved_first_then_signed_into_a_copy(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    copy = tmp_path / "contrato.pdf"
    copy.write_bytes(sample("formulario.pdf").read_bytes())
    assert window.open_document(copy)
    view = window.pdf_view
    wait_until(lambda: 0 in view._notes)
    assert view.put_text_box(0, 100, 100, "Acepto")
    wait_until(lambda: view.modified)
    window.signer_answer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    window.sign_target_answer = str

    window.sign_save_answer = False
    assert not window.sign_with_certificate()
    assert view.modified, "nothing saved nor signed"

    window.sign_save_answer = True
    assert window.sign_with_certificate()
    target = tmp_path / "contrato-firmado.pdf"
    wait_until(lambda: target.exists())
    with target.open("rb") as handle:
        assert len(PdfFileReader(handle).embedded_signatures) == 1
    import pymupdf

    with pymupdf.open(target) as doc:
        assert "Acepto" in [a.info["content"] for a in doc[0].annots()], "the change is signed"
    wait_until(lambda: window.current_document.path == target)
    assert len(window.documents) == 2, "the signed copy opens beside the original"


def test_the_certificate_used_last_comes_first(qt_app, store):
    dialog = CertificateDialog(certificates=[store[1], store[1]], preferred="nada")
    assert dialog.list.currentRow() == 0
    other = describe(
        certificates.der(certificates.make_certificate("PRUEBA OTRA", certificates.new_key()))
    )
    dialog = CertificateDialog(certificates=[store[1], other], preferred=other.thumbprint)
    assert dialog.selected() is other


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


def test_the_certificate_file_used_last_is_offered_and_bad_ones_explained(qt_app, sample, tmp_path):
    p12 = tmp_path / "mio.pfx"
    p12.write_bytes(sample("certificado-prueba.p12").read_bytes())
    dialog = CertificateDialog(certificates=[], last_file=str(tmp_path / "no-esta.p12"))
    assert dialog.last_file_button.isHidden(), "a file that is gone is not offered"
    dialog = CertificateDialog(certificates=[], last_file=str(p12))
    assert not dialog.last_file_button.isHidden()
    assert "mio.pfx" in dialog.last_file_button.text()
    dialog.password_answer = "prueba"
    dialog.last_file_button.click()
    assert dialog.signer is not None and dialog.chosen_file == str(p12)

    key = certificates.new_key()
    old = certificates.make_certificate("VIEJO", key, days_valid=-1, started_days_ago=30)
    expired = tmp_path / "viejo.p12"
    expired.write_bytes(certificates.make_p12("viejo", key, old))
    dialog = CertificateDialog(certificates=[])
    assert not dialog.use_file(str(expired), certificates.PASSWORD)
    assert "caducado" in dialog.explanation.text() and dialog.signer is None


def test_the_window_remembers_where_the_file_is_but_not_its_password(
    window, sample, tmp_path, monkeypatch
):
    p12 = tmp_path / "mio.p12"
    p12.write_bytes(sample("certificado-prueba.p12").read_bytes())

    def answered(self):
        self.use_file(str(p12), "prueba")
        return self.result()

    monkeypatch.setattr(CertificateDialog, "exec", answered)
    assert window._choose_signer() is not None
    assert window.settings.get("firma/archivo") == str(p12)
    assert "prueba" not in window.settings.path.read_text(encoding="utf-8")
