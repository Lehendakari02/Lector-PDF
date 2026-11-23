"""Tests for the "sign with certificate" proof of concept in the window."""

import pytest
from pyhanko.pdf_utils.reader import PdfFileReader

from app.core import certificate_settings
from app.core.signing import load_p12_signer
from app.core.windows_store import describe
from app.ui.pdf_view import PLACE_TOOL
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
    assert view.markup_tool == PLACE_TOOL, "first, where the signature goes"
    assert "Haz clic" in window.statusBar().currentMessage()
    assert view.put_certificate_place(2, 300, 400)
    assert asked == [copy], "already a «-firmado» document: signed in its place"
    with copy.open("rb") as handle:
        assert len(PdfFileReader(handle).embedded_signatures) == 1
    import pymupdf

    with pymupdf.open(copy) as doc:
        (box,) = doc[2].widgets()
        middle = (box.rect * doc[2].rotation_matrix).tl + (85, 28)
        assert abs(middle.x - 300) < 1 and abs(middle.y - 400) < 1, "visible where clicked"
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
    window.settings.set(certificate_settings.VISIBLE_SETTING, False)  # straight away

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


def test_choosing_the_place_can_be_left_with_escape(window, sample, tmp_path, wait_until):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    copy = tmp_path / "carta.pdf"
    copy.write_bytes(sample("formulario.pdf").read_bytes())
    assert window.open_document(copy)
    view = window.pdf_view
    wait_until(lambda: view.page_count > 0)
    window.signer_answer = "never asked"
    assert window.sign_with_certificate()
    assert view.markup_tool == PLACE_TOOL
    x0, y0, x1, y1 = view.certificate_box(0, 2, 2)
    assert (x0, y0) == (0, 0) and (x1, y1) == (170, 56), "kept inside the page"
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert view.markup_tool == ""
    assert not view.put_certificate_place(0, 100, 100), "nothing to place any more"
    assert not list(tmp_path.glob("*firmado*"))


def test_the_handwritten_signature_goes_in_the_box_unless_not_wanted(
    window, sample, tmp_path, wait_until, monkeypatch
):
    from app.ui import main_window as module

    window.show_problem_dialogs = False
    copy = tmp_path / "carta.pdf"
    copy.write_bytes(sample("formulario.pdf").read_bytes())
    assert window.open_document(copy)
    wait_until(lambda: window.pdf_view.page_count > 0)
    window.signer_answer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    window.sign_target_answer = str
    asked = []
    monkeypatch.setattr(
        module,
        "sign_pdf",
        lambda source, target, signer, visible=None, server="": (
            asked.append((visible, server)) or target.write_bytes(source.read_bytes())
        ),
    )
    monkeypatch.setattr(window, "saved_signature", lambda kind: b"PNG")
    view = window.pdf_view
    assert window.sign_with_certificate() and view.put_certificate_place(0, 200, 300)
    ((visible, server),) = asked
    assert visible.page == 0 and visible.png == b"PNG" and server == ""

    window.settings.set(certificate_settings.HANDWRITTEN_SETTING, False)
    window.settings.set(certificate_settings.TIMESTAMP_SETTING, True)
    window.sign_target_answer = lambda suggested: str(tmp_path / "otra.pdf")
    view = window.pdf_view  # the signed copy, opened in its own tab
    wait_until(lambda: view.page_count > 0)
    assert window.sign_with_certificate() and view.put_certificate_place(0, 200, 300)
    visible, server = asked[-1]
    assert visible.png is None
    assert server == certificate_settings.timestamp_server(window.settings)


def test_without_the_timestamp_server_signing_without_it_is_offered(
    window, sample, tmp_path, wait_until, monkeypatch
):
    from app.core.signing import TimestampFailed

    window.show_problem_dialogs = False
    window.reporter.show_dialogs = False
    window.settings.set(certificate_settings.VISIBLE_SETTING, False)
    window.settings.set(certificate_settings.TIMESTAMP_SETTING, True)
    window.settings.set(certificate_settings.TIMESTAMP_SERVER_SETTING, "http://127.0.0.1:9/tsa")
    copy = tmp_path / "carta.pdf"
    copy.write_bytes(sample("formulario.pdf").read_bytes())
    assert window.open_document(copy)
    wait_until(lambda: window.pdf_view.page_count > 0)
    window.signer_answer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    window.sign_target_answer = str
    target = tmp_path / "carta-firmado.pdf"

    window.timestamp_failed_answer = False
    assert not window.sign_with_certificate()
    assert not target.exists()
    assert "cancelada" in window.statusBar().currentMessage()

    window.timestamp_failed_answer = True
    assert window.sign_with_certificate()
    with target.open("rb") as handle:
        assert len(PdfFileReader(handle).embedded_signatures) == 1
    assert TimestampFailed  # the kind of failure that offers it


# ---- signing several documents at once (task 4.4) ----


def test_several_documents_are_signed_with_one_choice_of_certificate(window, sample, tmp_path):
    import shutil

    from app.core.batch_signing import BOTTOM_LEFT, FIRST, Placement

    window.show_problem_dialogs = False
    paths = []
    for number in range(3):
        path = tmp_path / f"nómina {number + 1}.pdf"
        shutil.copy(sample("formulario.pdf"), path)
        paths.append(path)
    locked = tmp_path / "cerrado.pdf"
    shutil.copy(sample("con-contrasena.pdf"), locked)
    chosen = []
    window.signer_answer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    original = window._choose_signer
    window._choose_signer = lambda: chosen.append(1) or original()
    window.sign_many_answer = ([*paths, locked], Placement(FIRST, BOTTOM_LEFT))
    assert window.feature_actions["sign_many"].isEnabled()
    window.feature_actions["sign_many"].trigger()
    assert chosen == [1], "the certificate is chosen once"
    for path in paths:
        with path.with_name(f"{path.stem}-firmado.pdf").open("rb") as handle:
            assert len(PdfFileReader(handle).embedded_signatures) == 1
    assert "Firmados 3 de 4" in window.batch_summary
    assert "«cerrado.pdf»: tiene contraseña" in window.batch_summary
    assert window.settings.get(certificate_settings.BATCH_PAGE_SETTING) == FIRST
    assert window.settings.get(certificate_settings.BATCH_CORNER_SETTING) == BOTTOM_LEFT
    assert len(window.documents) <= 1, "the signed copies are not all opened"


def test_the_batch_window_lists_documents_once_and_tells_unsaved_ones(qt_app, tmp_path):
    from app.core.batch_signing import FIRST, TOP_RIGHT
    from app.ui.batch_sign_dialog import BatchSignDialog

    one, two = tmp_path / "uno.pdf", tmp_path / "dos.pdf"
    dialog = BatchSignDialog(
        open_documents=[(one, False), (two, True)], page=FIRST, corner=TOP_RIGHT
    )
    assert not dialog.sign_button.isEnabled()
    dialog.add_open()
    dialog.add([one, tmp_path / "foto.jpg"])
    assert dialog.paths == [one, two], "each once, only PDFs"
    assert dialog.sign_button.text() == "Firmar 2 documentos"
    assert "cambios sin guardar" in dialog.list.item(1).text()
    assert dialog.note.isVisibleTo(dialog)
    assert dialog.placement.page == FIRST and dialog.placement.corner == TOP_RIGHT
    dialog.where_box.setCurrentIndex(dialog.where_box.findData("invisible"))
    assert dialog.placement is None and not dialog.corner_box.isEnabled()
    dialog.list.item(1).setSelected(True)
    dialog.remove_selected()
    assert dialog.paths == [one] and dialog.sign_button.text() == "Firmar"
    assert not dialog.note.isVisibleTo(dialog)
    remembered_invisible = BatchSignDialog(visible=False)
    assert remembered_invisible.placement is None
