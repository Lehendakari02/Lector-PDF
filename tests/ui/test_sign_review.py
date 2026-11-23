"""Tests for the fixes of the Phase 4 code review in the window (task 4.8)."""

import shutil

from pyhanko.pdf_utils.reader import PdfFileReader
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.core import batch_signing, certificate_settings
from app.core.document import PdfDocument
from app.core.signing import WindowsStoreSigner, load_p12_signer
from app.core.windows_store import WrongPin, describe
from app.ui import main_window as module
from app.ui import sign_dialog
from app.ui.pdf_view import PLACE_TOOL
from app.ui.sign_dialog import CertificateDialog
from tests import certificates
from tests.core.test_signing_review import FailingKey


def _signer(sample):
    return load_p12_signer(sample("certificado-prueba.p12"), "prueba")


def _open(window, path, wait_until):
    assert window.open_document(path)
    wait_until(lambda: window.pdf_view.page_count > 0)


def test_a_wrong_pin_is_told_in_plain_words(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False
    copy = shutil.copy(sample("formulario.pdf"), tmp_path / "carta.pdf")
    _open(window, copy, wait_until)
    key = FailingKey(_signer(sample), WrongPin("wrong PIN"))
    assert not window.sign_document(window.pdf_view.document_path, tmp_path / "f.pdf", key)
    message = window.statusBar().currentMessage()
    assert "PIN" in message and "bloquean" in message
    assert not (tmp_path / "f.pdf").exists()


def test_a_wrong_pin_stops_the_batch_and_says_how_far_it_went(window, sample, tmp_path):
    window.show_problem_dialogs = False
    paths = [shutil.copy(sample("formulario.pdf"), tmp_path / f"{n}.pdf") for n in "abc"]
    window.signer_answer = FailingKey(_signer(sample), WrongPin("wrong PIN"), good=1)
    window.sign_many_answer = (list(map(type(tmp_path), paths)), None)
    shown = []
    window._show_problem = lambda title, text: shown.append(text)
    window.sign_many()
    assert window.signer_answer.used == 2
    assert "Firmados 1 de 3" in window.batch_summary
    assert "Se paró" in window.batch_summary
    assert any("PIN" in text for text in shown)


def test_the_pin_window_of_windows_goes_over_the_main_window(
    window, sample, tmp_path, wait_until, monkeypatch
):
    """Not over the window where the certificate was chosen: it is closed by then."""
    window.show_problem_dialogs = False
    _open(window, shutil.copy(sample("formulario.pdf"), tmp_path / "a.pdf"), wait_until)
    key = certificates.new_key()
    chosen = describe(certificates.der(certificates.make_certificate("ANA", key)))
    signer = WindowsStoreSigner(chosen, window_handle=12345, chain_candidates=[])
    seen = []
    monkeypatch.setattr(
        module,
        "sign_pdf",
        lambda source, target, signer, *rest, **named: seen.append(signer.window_handle),
    )
    window.sign_document(window.pdf_view.document_path, tmp_path / "f.pdf", signer)
    assert seen == [int(window.winId())]


def test_signing_several_blocks_the_window_meanwhile(window, sample, tmp_path, monkeypatch):
    window.show_problem_dialogs = False
    paths = [shutil.copy(sample("formulario.pdf"), tmp_path / f"{n}.pdf") for n in "ab"]
    window.signer_answer = _signer(sample)
    window.sign_many_answer = (list(map(type(tmp_path), paths)), None)
    modality = []

    def watching(*args, **named):
        dialogs = [
            w for w in QApplication.topLevelWidgets() if type(w).__name__ == "QProgressDialog"
        ]
        modality.extend(dialog.windowModality() for dialog in dialogs if dialog.parent() is window)
        return real(*args, **named)

    real = batch_signing.sign_many
    monkeypatch.setattr(batch_signing, "sign_many", watching)
    assert window.sign_many()
    assert modality and set(modality) == {Qt.WindowModality.WindowModal}


def test_open_documents_with_a_password_are_signed_in_the_batch(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    locked = shutil.copy(sample("contrasena-firmable.pdf"), tmp_path / "cerrado.pdf")
    window.ask_password = lambda path: PdfDocument(path, "lector")
    _open(window, locked, wait_until)
    window.signer_answer = _signer(sample)
    window.sign_many_answer = ([type(tmp_path)(locked)], batch_signing.Placement())
    assert window.sign_many()
    assert "Firmados 1 de 1" in window.batch_summary


def test_an_open_document_with_a_password_is_signed(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False
    locked = shutil.copy(sample("contrasena-firmable.pdf"), tmp_path / "cerrado.pdf")
    window.ask_password = lambda path: PdfDocument(path, "lector")
    _open(window, locked, wait_until)
    target = tmp_path / "cerrado-firmado.pdf"
    assert window.sign_document(window.pdf_view.document_path, target, _signer(sample))
    with target.open("rb") as handle:
        reader = PdfFileReader(handle, strict=False)
        reader.decrypt("lector")
        assert len(reader.embedded_signatures) == 1


def test_a_document_its_author_protects_from_signing_is_explained(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    _open(window, shutil.copy(sample("no-se-firma.pdf"), tmp_path / "n.pdf"), wait_until)
    assert not window.sign_document(
        window.pdf_view.document_path, tmp_path / "f.pdf", _signer(sample)
    )
    assert "no se pueda rellenar ni firmar" in window.statusBar().currentMessage()


def test_signing_over_another_open_document_with_changes_is_refused(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    other = tmp_path / "otro.pdf"
    shutil.copy(sample("formulario.pdf"), other)
    _open(window, other, wait_until)
    view = window.pdf_view
    wait_until(lambda: 0 in view._notes)
    assert view.put_text_box(0, 100, 100, "Mis cambios")
    wait_until(lambda: view.modified)
    before = other.read_bytes()
    source = tmp_path / "carta.pdf"
    shutil.copy(sample("formulario.pdf"), source)
    _open(window, source, wait_until)
    assert not window.sign_document(source, other, _signer(sample))
    assert "cambios sin guardar" in window.statusBar().currentMessage()
    assert other.read_bytes() == before
    assert len(window.documents) == 2 and view.modified, "its changes are still there"


def test_signing_in_place_in_a_folder_that_cannot_be_written_is_explained(
    window, sample, tmp_path, wait_until, monkeypatch
):
    window.show_problem_dialogs = False
    copy = shutil.copy(sample("formulario.pdf"), tmp_path / "doc-firmado.pdf")
    _open(window, copy, wait_until)

    def refused(*_args, **_named):
        raise PermissionError(13, "denied")

    monkeypatch.setattr(module.tempfile, "mkstemp", refused)
    assert not window.sign_document(type(tmp_path)(copy), type(tmp_path)(copy), _signer(sample))
    assert "No se puede escribir" in window.statusBar().currentMessage()


def test_double_click_prepares_the_certificate_once(qt_app, monkeypatch):
    key = certificates.new_key()
    chosen = describe(certificates.der(certificates.make_certificate("ANA", key)))
    made = []
    monkeypatch.setattr(
        sign_dialog, "WindowsStoreSigner", lambda certificate, window_handle: made.append(1) or 1
    )
    dialog = CertificateDialog(certificates=[chosen])
    dialog.list.itemDoubleClicked.emit(dialog.list.item(0))
    assert made == [1]


def test_the_timestamp_server_typed_is_kept_when_closing_with_escape(window):
    from app.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(window)
    window.settings.set(certificate_settings.TIMESTAMP_SETTING, True)
    dialog.server_edit.setText("http://sello.example.es/tsa")
    dialog.reject()
    assert certificate_settings.timestamp_server(window.settings) == "http://sello.example.es/tsa"


def test_enter_puts_the_visible_signature_at_the_bottom_right(window, sample, wait_until):
    _open(window, sample("formulario.pdf"), wait_until)
    view = window.pdf_view
    placed = []
    view.certificate_place.disconnect()
    view.certificate_place.connect(lambda page, rect: placed.append((page, rect)))
    view.choose_certificate_place()
    assert view.markup_tool == PLACE_TOOL
    view.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    )
    ((page, rect),) = placed
    size = view._sizes[page]
    assert rect[2] == size.width - batch_signing.MARGIN
    assert rect[3] == size.height - batch_signing.MARGIN
    assert view.markup_tool != PLACE_TOOL


# ---- Idea 1: signing inside the empty signature field the document has ----


def test_a_click_in_the_empty_field_signs_inside_it(window, sample, tmp_path, wait_until):
    from tests.core.test_signing_review import with_signature_field

    window.show_problem_dialogs = False
    source = with_signature_field(tmp_path / "contrato.pdf")
    _open(window, source, wait_until)
    view = window.pdf_view
    window.signer_answer = _signer(sample)
    window.sign_target_answer = lambda suggested: tmp_path / "f.pdf"
    asked = []
    real = window.sign_document
    window.sign_document = lambda *args: asked.append(args[3]) or real(*args)
    assert window.sign_with_certificate()
    assert view.markup_tool == PLACE_TOOL
    assert view.signature_fields == {0: [("Firma del trabajador", (50.0, 600.0, 250.0, 660.0))]}
    assert view.put_certificate_place(0, 100, 630)  # inside the field
    (visible,) = asked
    assert visible.field == "Firma del trabajador"
    assert visible.rect == (50.0, 600.0, 250.0, 660.0)
    with (tmp_path / "f.pdf").open("rb") as handle:
        (signature,) = PdfFileReader(handle, strict=False).embedded_signatures
        assert signature.field_name == "Firma del trabajador"


def test_a_click_elsewhere_makes_a_new_signature(window, tmp_path, wait_until):
    from tests.core.test_signing_review import with_signature_field

    _open(window, with_signature_field(tmp_path / "contrato.pdf"), wait_until)
    view = window.pdf_view
    placed = []
    view.certificate_place.disconnect()
    view.certificate_place.connect(lambda page, rect: placed.append(rect))
    view.choose_certificate_place(fields=[("Firma del trabajador", 0, (50, 600, 250, 660))])
    assert view.put_certificate_place(0, 300, 200)
    assert view.placed_field == "" and placed[0] != (50, 600, 250, 660)


def test_enter_goes_to_the_empty_field(window, tmp_path, wait_until):
    from tests.core.test_signing_review import with_signature_field

    _open(window, with_signature_field(tmp_path / "contrato.pdf"), wait_until)
    view = window.pdf_view
    placed = []
    view.certificate_place.disconnect()
    view.certificate_place.connect(lambda page, rect: placed.append((page, rect)))
    view.choose_certificate_place(fields=[("Firma del trabajador", 0, (50, 600, 250, 660))])
    view.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    )
    assert placed == [(0, (50, 600, 250, 660))]
    assert view.placed_field == "Firma del trabajador"
