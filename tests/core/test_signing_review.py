"""Tests for the fixes of the Phase 4 code review (task 4.8)."""

import shutil
from pathlib import Path

import pymupdf
import pytest
from asn1crypto import x509 as asn1_x509
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from app.core import batch_signing, signature_check, signing, windows_store
from app.core.batch_signing import NOT_ALLOWED, PASSWORD, SIGNED, sign_many
from app.core.signing import (
    NotAllowed,
    PasswordProtected,
    SigningError,
    Visible,
    load_p12_signer,
    sign_pdf,
)
from app.core.windows_store import CardBlocked, NoCard, SigningCancelled, StoreError, WrongPin
from tests import certificates


@pytest.fixture
def signer(sample):
    return load_p12_signer(sample("certificado-prueba.p12"), "prueba")


class FailingKey(signers.SimpleSigner):
    """A key that signs ``good`` times and then answers like Windows with ``problem``."""

    def __init__(self, base, problem: Exception, good: int = 0) -> None:
        super().__init__(
            signing_cert=base.signing_cert,
            signing_key=base.signing_key,
            cert_registry=base.cert_registry,
        )
        self.problem, self.good, self.used = problem, good, 0

    async def async_sign_raw(self, data, digest_algorithm, dry_run=False):
        if not dry_run:
            self.used += 1
            if self.used > self.good:
                raise self.problem
        return await super().async_sign_raw(data, digest_algorithm, dry_run)


def valid_signatures(path: Path, trusted, password: str = "") -> list:
    with path.open("rb") as handle:
        reader = PdfFileReader(handle, strict=False)
        if reader.encrypted:
            reader.decrypt(password)
        return [
            validate_pdf_signature(signature, ValidationContext(trust_roots=[trusted])).intact
            for signature in reader.embedded_signatures
        ]


# ---- A1: a problem with the key stops, and says what it is ----


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        (0x8010006B, WrongPin),
        (0x8010006C, CardBlocked),
        (0x80100069, NoCard),
        (0x8010000C, NoCard),
        (0x8010006E, SigningCancelled),
        (0x80090016, StoreError),
    ],
)
def test_the_answers_of_windows_are_told_apart(code, kind):
    with pytest.raises(StoreError) as raised:
        windows_store._fail("Windows refused to sign", code)
    assert type(raised.value) is kind


def test_a_wrong_pin_is_a_problem_of_the_key_not_of_the_document(signer, sample, tmp_path):
    key = FailingKey(signer, WrongPin("wrong PIN (0x8010006B)"))
    with pytest.raises(WrongPin):
        sign_pdf(sample("formulario.pdf"), tmp_path / "f.pdf", key)
    assert list(tmp_path.iterdir()) == [], "nothing half written"


def test_a_wrong_pin_stops_the_batch_at_once(signer, sample, tmp_path):
    """The DNIe locks itself after three wrong PINs: never ask again and again."""
    documents = []
    for number in range(4):
        path = tmp_path / f"nómina {number}.pdf"
        shutil.copy(sample("formulario.pdf"), path)
        documents.append(path)
    key = FailingKey(signer, WrongPin("wrong PIN"), good=1)
    with pytest.raises(WrongPin) as raised:
        sign_many(documents, key)
    assert key.used == 2, "the PIN is not asked for the other documents"
    assert [outcome.result for outcome in raised.value.outcomes] == [SIGNED]
    assert documents[0].with_name("nómina 0-firmado.pdf").exists()
    assert not documents[2].with_name("nómina 2-firmado.pdf").exists()


def test_a_card_out_of_its_reader_stops_the_batch_too(signer, sample, tmp_path):
    documents = [shutil.copy(sample("formulario.pdf"), tmp_path / f"{n}.pdf") for n in "ab"]
    key = FailingKey(signer, NoCard("no card"))
    with pytest.raises(NoCard) as raised:
        sign_many(map(Path, documents), key)
    assert raised.value.outcomes == [] and key.used == 1


# ---- A2: documents with permissions or a password ----


def test_a_document_with_permissions_only_is_signed_and_stays_protected(signer, sample, tmp_path):
    target = sign_pdf(
        sample("restringido.pdf"), tmp_path / "f.pdf", signer, Visible(0, (40, 40, 210, 96))
    )
    assert valid_signatures(target, signer.signing_cert) == [True]
    with pymupdf.open(target) as doc:
        assert not doc.needs_pass and doc.metadata["encryption"], "still protected"
        assert doc.permissions == pymupdf.open(sample("restringido.pdf")).permissions
        assert "Documento protegido" in doc[0].get_text()
        assert doc.get_sigflags() == 3


def test_a_document_its_author_does_not_let_sign_is_refused(signer, sample, tmp_path):
    with pytest.raises(NotAllowed):
        sign_pdf(sample("no-se-firma.pdf"), tmp_path / "f.pdf", signer)
    assert list(tmp_path.iterdir()) == []


def test_a_document_with_a_password_is_signed_with_it(signer, sample, tmp_path):
    source = sample("contrasena-firmable.pdf")
    for wrong in (None, "mala"):
        with pytest.raises(PasswordProtected):
            sign_pdf(source, tmp_path / "f.pdf", signer, password=wrong)
    target = sign_pdf(source, tmp_path / "f.pdf", signer, password="lector")
    assert valid_signatures(target, signer.signing_cert, "lector") == [True]
    with pymupdf.open(target) as doc:
        assert doc.needs_pass, "it still asks for the password"
        assert doc.authenticate("lector")
        assert "Documento protegido" in doc[0].get_text()


def test_a_document_protected_by_pymupdf_without_password_is_signed(signer, tmp_path):
    source = tmp_path / "permisos.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "hola")
        doc.save(
            source,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="propietario",
            permissions=pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_FORM,
        )
    target = sign_pdf(source, tmp_path / "f.pdf", signer)
    assert valid_signatures(target, signer.signing_cert) == [True]
    with pymupdf.open(target) as doc:
        assert doc[0].get_text().strip() == "hola" and doc.get_sigflags() == 3


def test_a_document_protected_by_pymupdf_with_password_fails_cleanly(signer, sample, tmp_path):
    """Signing it would leave a file PyMuPDF cannot read: refused, untouched."""
    with pytest.raises(SigningError):
        sign_pdf(sample("con-contrasena.pdf"), tmp_path / "f.pdf", signer, password="lector")
    assert list(tmp_path.iterdir()) == []


def test_the_batch_uses_the_passwords_it_is_given(signer, sample, tmp_path):
    documents = [
        shutil.copy(sample(name), tmp_path / name)
        for name in ("contrasena-firmable.pdf", "no-se-firma.pdf", "restringido.pdf")
    ]
    documents = list(map(Path, documents))
    outcomes = sign_many(
        documents,
        signer,
        batch_signing.Placement(),
        passwords={documents[0]: "lector"},
    )
    assert [outcome.result for outcome in outcomes] == [SIGNED, NOT_ALLOWED, SIGNED]
    outcomes = sign_many(documents[:1], signer, batch_signing.Placement())
    assert [outcome.result for outcome in outcomes] == [PASSWORD]


# ---- A3: the visible box where it was asked, on turned and cropped pages ----


def drawn_box(path: Path) -> tuple[int, int, int, int]:
    """Where something is painted on the first page, as shown."""
    with pymupdf.open(path) as doc:
        pix = doc[0].get_pixmap(dpi=72, annots=True)
    xs, ys = [], []
    for y in range(pix.height):
        for x in range(pix.width):
            if pix.pixel(x, y)[0] < 250:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop", [None, (50, 80, 550, 780)])
def test_the_visible_box_goes_where_it_was_asked(signer, tmp_path, rotation, crop):
    source = tmp_path / "pagina.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        if crop:
            page.set_cropbox(pymupdf.Rect(crop))
        page.set_rotation(rotation)
        doc.save(source)
    wanted = (40, 60, 210, 116)
    target = sign_pdf(source, tmp_path / "f.pdf", signer, Visible(0, wanted))
    got = drawn_box(target)
    assert all(abs(a - b) <= 1 for a, b in zip(got, wanted, strict=True)), got


# ---- M2: a text field called «Firma1» ----


def test_a_text_field_called_like_the_signature_does_not_stop_it(signer, tmp_path):
    source = tmp_path / "campo.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = "Firma1"
        widget.rect = pymupdf.Rect(50, 50, 200, 80)
        page.add_widget(widget)
        doc.save(source)
    for visible in (None, Visible(0, (300, 300, 470, 356))):
        target = sign_pdf(source, tmp_path / "f.pdf", signer, visible)
        with target.open("rb") as handle:
            (signature,) = PdfFileReader(handle, strict=False).embedded_signatures
            assert signature.field_name == "Firma2"


# ---- M5 and B1: checking and completing the chain ----


def test_a_certificate_marked_only_for_digital_signature_is_good(tmp_path, sample):
    root_key = certificates.new_key()
    root = certificates.make_certificate("RAIZ", root_key, authority=True, days_valid=300)
    key = certificates.new_key()
    person = certificates.make_certificate(
        "PERSONA", key, issuer=root, issuer_key=root_key, only="autenticacion"
    )
    p12 = tmp_path / "p.p12"
    p12.write_bytes(certificates.make_p12("p", key, person, [root]))
    target = sign_pdf(
        sample("formulario.pdf"), tmp_path / "f.pdf", load_p12_signer(p12, certificates.PASSWORD)
    )
    (report,) = signature_check.check_signatures(
        target, roots=[asn1_x509.Certificate.load(certificates.der(root))]
    )
    assert report.good and report.trusted


def test_authorities_of_windows_complete_a_chain_not_carried_inside(tmp_path, sample, monkeypatch):
    root_key, middle_key, key = (certificates.new_key() for _ in range(3))
    root = certificates.make_certificate("RAIZ", root_key, authority=True, days_valid=300)
    middle = certificates.make_certificate(
        "INTERMEDIA", middle_key, issuer=root, issuer_key=root_key, authority=True
    )
    person = certificates.make_certificate("PERSONA", key, issuer=middle, issuer_key=middle_key)
    p12 = tmp_path / "p.p12"
    p12.write_bytes(certificates.make_p12("p", key, person))  # without its authorities
    target = sign_pdf(
        sample("formulario.pdf"), tmp_path / "f.pdf", load_p12_signer(p12, certificates.PASSWORD)
    )
    roots = [asn1_x509.Certificate.load(certificates.der(root))]
    known = [asn1_x509.Certificate.load(certificates.der(middle))]
    (alone,) = signature_check.check_signatures(target, roots=roots, intermediates=[])
    (helped,) = signature_check.check_signatures(target, roots=roots, intermediates=known)
    assert not alone.trusted and helped.trusted

    # And on Windows the program puts them in its own signatures (.p12 too).
    monkeypatch.setattr(windows_store, "is_available", lambda: True)
    monkeypatch.setattr(
        windows_store,
        "chain_candidates",
        lambda: [certificates.der(middle), certificates.der(root)],
    )
    complete = load_p12_signer(p12, certificates.PASSWORD)
    target = sign_pdf(sample("formulario.pdf"), tmp_path / "g.pdf", complete)
    (inside,) = signature_check.check_signatures(target, roots=roots, intermediates=[])
    assert inside.trusted


# ---- B7: preparing a document with an empty signature field ----


def test_a_document_with_an_empty_signature_field_can_be_prepared(tmp_path):
    with pymupdf.open() as doc:
        page = doc.new_page()
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
        widget.field_name = "Firma del trabajador"
        widget.rect = pymupdf.Rect(50, 600, 250, 660)
        page.add_widget(widget)
        data = doc.tobytes()
    assert signing._rewritten(data)


def test_a_protected_document_is_never_prepared_by_writing_it_again(sample):
    with pytest.raises(SigningError):
        signing._rewritten(sample("restringido.pdf").read_bytes())


def test_a_signed_document_is_never_prepared_by_writing_it_again(sample):
    with pytest.raises(SigningError):
        signing._rewritten(sample("firmado.pdf").read_bytes())


# ---- Idea 1: signing inside the empty signature field the document has ----


def with_signature_field(path: Path, rotation: int = 0, box=(50, 600, 250, 660)) -> Path:
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
        widget.field_name = "Firma del trabajador"
        widget.rect = pymupdf.Rect(box)
        page.add_widget(widget)
        page.set_rotation(rotation)
        doc.save(path)
    return path


def test_the_empty_signature_fields_are_found(tmp_path, sample):
    source = with_signature_field(tmp_path / "contrato.pdf")
    assert signing.empty_signature_fields(source) == [
        ("Firma del trabajador", 0, (50.0, 600.0, 250.0, 660.0))
    ]
    assert signing.empty_signature_fields(sample("formulario.pdf")) == []
    assert signing.empty_signature_fields(tmp_path / "no-existe.pdf") == []


def test_a_signed_field_is_not_offered_again(signer, tmp_path):
    source = with_signature_field(tmp_path / "contrato.pdf")
    (name, page, box) = signing.empty_signature_fields(source)[0]
    target = sign_pdf(source, tmp_path / "f.pdf", signer, Visible(page, box, field=name))
    assert signing.empty_signature_fields(target) == []


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_signing_inside_the_field_uses_it_and_its_place(signer, tmp_path, rotation):
    source = with_signature_field(tmp_path / "contrato.pdf", rotation)
    ((name, page, box),) = signing.empty_signature_fields(source)
    target = sign_pdf(source, tmp_path / "f.pdf", signer, Visible(page, box, field=name))
    with target.open("rb") as handle:
        reader = PdfFileReader(handle, strict=False)
        (signature,) = reader.embedded_signatures
        assert signature.field_name == "Firma del trabajador"
        names = [field.get_object()["/T"] for field in reader.root["/AcroForm"]["/Fields"]]
    assert names == ["Firma del trabajador"], "no second field is made"
    got = drawn_box(target)
    assert all(abs(a - b) <= 1 for a, b in zip(got, box, strict=True)), (got, box)


def test_signing_inside_the_field_of_a_protected_document(signer, tmp_path):
    source = with_signature_field(tmp_path / "contrato.pdf")
    with pymupdf.open(source) as doc:
        doc.save(tmp_path / "p.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="dueno")
    ((name, page, box),) = signing.empty_signature_fields(tmp_path / "p.pdf")
    target = sign_pdf(
        tmp_path / "p.pdf", tmp_path / "f.pdf", signer, Visible(page, box, field=name)
    )
    assert signing.empty_signature_fields(target) == []


# ---- Idea 2: a signed PDF is saved adding the changes at the end ----


def signed_form(signer, sample, tmp_path) -> Path:
    return sign_pdf(sample("formulario.pdf"), tmp_path / "firmado.pdf", signer)


def saved_with(path: Path, change) -> Path:
    from app.core.saving import save_to

    with pymupdf.open(path) as doc:
        change(doc)
        save_to(doc, path)
    return path


def note(doc) -> None:
    doc[0].add_text_annot((100, 100), "Repasar")


def highlight(doc) -> None:
    doc[0].add_highlight_annot(pymupdf.Rect(72, 72, 200, 90))


def ink(doc) -> None:
    doc[0].add_ink_annot([[(100, 300), (150, 320), (200, 300)]])


def fill(doc) -> None:
    page = doc[0]
    widget = next(w for w in page.widgets() if w.field_type == pymupdf.PDF_WIDGET_TYPE_TEXT)
    widget.field_value = "Ana Pérez"
    widget.update()


@pytest.mark.parametrize(
    ("change", "after"),
    [
        (note, signature_check.ANNOTATED),
        (highlight, signature_check.ANNOTATED),
        (ink, signature_check.ANNOTATED),
        (fill, signature_check.FORM_FILLED),
    ],
)
def test_light_changes_keep_the_signature(signer, sample, tmp_path, change, after):
    path = signed_form(signer, sample, tmp_path)
    signed = path.read_bytes()
    saved_with(path, change)
    assert path.read_bytes().startswith(signed), "what was signed stays as it was"
    (report,) = signature_check.check_signatures(path, roots=[], intermediates=[])
    assert report.intact and report.after == after


def test_a_change_of_the_page_is_told(signer, sample, tmp_path):
    path = signed_form(signer, sample, tmp_path)

    def margin(doc) -> None:
        page = doc[0]
        page.set_mediabox(pymupdf.Rect(0, 0, page.rect.width + 100, page.rect.height))

    saved_with(path, margin)
    (report,) = signature_check.check_signatures(path, roots=[], intermediates=[])
    assert report.after == signature_check.CHANGED and not report.good


def test_a_document_without_signatures_is_written_whole(sample):
    with pymupdf.open(sample("formulario.pdf")) as doc:
        assert not saving_keeps(doc)


def test_a_repaired_signed_document_is_written_whole(signer, sample, tmp_path):
    path = signed_form(signer, sample, tmp_path)
    with pymupdf.open(path) as doc:
        assert saving_keeps(doc)
    broken = path.read_bytes().replace(b"startxref", b"startxrof")
    with pymupdf.open(stream=broken, filetype="pdf") as doc:
        assert doc.is_repaired and not saving_keeps(doc)


def saving_keeps(doc) -> bool:
    from app.core.saving import keeps_signatures

    return keeps_signatures(doc)
