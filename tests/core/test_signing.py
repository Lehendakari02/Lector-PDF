"""Tests for signing PDFs with a certificate (task 0.8)."""

import shutil

import pytest
from asn1crypto import x509 as asn1_x509
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from app.core import signing
from app.core.signing import (
    PasswordProtected,
    SigningError,
    build_chain,
    load_p12_signer,
    sign_pdf,
)
from tests import certificates


def check_signatures(path, trusted):
    """Every signature in the file, checked against the trusted certificate."""
    results = []
    with path.open("rb") as handle:
        reader = PdfFileReader(handle, strict=False)
        for signature in reader.embedded_signatures:
            status = validate_pdf_signature(signature, ValidationContext(trust_roots=[trusted]))
            results.append((signature, status))
    return results


@pytest.fixture
def signer(sample):
    return load_p12_signer(sample("certificado-prueba.p12"), "prueba")


@pytest.mark.parametrize("name", ["formulario.pdf", "largo.pdf", "escaneado.pdf"])
def test_signed_copy_is_valid_and_the_original_is_untouched(sample, signer, tmp_path, name):
    before = sample(name).read_bytes()
    target = sign_pdf(sample(name), tmp_path / "firmado.pdf", signer)
    assert sample(name).read_bytes() == before
    ((signature, status),) = check_signatures(target, signer.signing_cert)
    assert status.intact and status.valid and status.trusted
    assert signature.field_name == "Firma1"
    assert signature.sig_object["/SubFilter"] == "/ETSI.CAdES.detached", "PAdES signature"
    assert status.md_algorithm == "sha256"
    # The signature is added at the end: the original is still there, byte for byte.
    assert target.read_bytes().startswith(before)


def test_a_real_boe_document_can_be_signed(sample, signer, tmp_path):
    """The BOE's PDFs have a detail the signing library cannot read as it is."""
    target = sign_pdf(sample("boe.pdf"), tmp_path / "boe-firmado.pdf", signer)
    ((_signature, status),) = check_signatures(target, signer.signing_cert)
    assert status.intact and status.valid
    import pymupdf

    with pymupdf.open(target) as doc:
        assert doc.page_count == 39
        assert "Constitución" in doc.metadata["title"]


def test_signing_a_signed_document_keeps_the_first_signature(sample, signer, tmp_path):
    target = sign_pdf(sample("firmado.pdf"), tmp_path / "dos-firmas.pdf", signer)
    results = check_signatures(target, signer.signing_cert)
    assert [signature.field_name for signature, _status in results] == ["Firma1", "Firma2"]
    assert all(status.intact and status.valid for _signature, status in results)


def test_password_protected_documents_are_refused_clearly(sample, signer, tmp_path):
    with pytest.raises(PasswordProtected):
        sign_pdf(sample("con-contrasena.pdf"), tmp_path / "no.pdf", signer)
    assert list(tmp_path.iterdir()) == [], "no half-written file is left behind"


def test_a_file_that_is_not_a_pdf_fails_cleanly(signer, tmp_path):
    bad = tmp_path / "roto.pdf"
    bad.write_bytes(b"this is not a PDF")
    with pytest.raises(SigningError):
        sign_pdf(bad, tmp_path / "salida.pdf", signer)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["roto.pdf"]


def test_a_failure_while_signing_leaves_no_file(sample, tmp_path):
    class BrokenSigner(type(load_p12_signer(sample("certificado-prueba.p12"), "prueba"))):
        async def async_sign_raw(self, data, digest_algorithm, dry_run=False):
            raise RuntimeError("the card was pulled out")

    good = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    broken = BrokenSigner(
        signing_cert=good.signing_cert, signing_key=good.signing_key, cert_registry=None
    )
    existing = tmp_path / "salida.pdf"
    existing.write_bytes(b"what was there before")
    with pytest.raises(SigningError):
        sign_pdf(sample("formulario.pdf"), existing, broken)
    assert existing.read_bytes() == b"what was there before"
    assert [path.name for path in tmp_path.iterdir()] == ["salida.pdf"]


def test_wrong_p12_password_and_wrong_file(sample, tmp_path):
    with pytest.raises(SigningError):
        load_p12_signer(sample("certificado-prueba.p12"), "otra")
    with pytest.raises(SigningError):
        load_p12_signer(sample("boe.pdf"), "prueba")
    with pytest.raises(SigningError):
        load_p12_signer(tmp_path / "no-existe.p12", "prueba")


def test_p12_with_its_authorities_embeds_the_chain(sample, tmp_path):
    root_key, middle_key, key = (certificates.new_key() for _ in range(3))
    root = certificates.make_certificate("Raíz de prueba", root_key, authority=True)
    middle = certificates.make_certificate(
        "Intermedia de prueba", middle_key, root, root_key, authority=True
    )
    leaf = certificates.make_certificate("Persona de Prueba", key, middle, middle_key)
    p12 = tmp_path / "con-cadena.p12"
    p12.write_bytes(certificates.make_p12("persona", key, leaf, [middle, root]))

    signer = load_p12_signer(p12, certificates.PASSWORD)
    target = sign_pdf(sample("formulario.pdf"), tmp_path / "firmado.pdf", signer)
    trusted = asn1_x509.Certificate.load(certificates.der(root))
    ((signature, status),) = check_signatures(target, trusted)
    assert status.intact and status.valid and status.trusted
    embedded = {cert.subject.native["common_name"] for cert in signature.other_embedded_certs}
    assert "Intermedia de prueba" in embedded


# ---- finding the authorities of a certificate ---------------------------------


@pytest.fixture(scope="module")
def family():
    """Root -> intermediate -> person, plus unrelated certificates."""
    root_key, middle_key, key, other_key = (certificates.new_key() for _ in range(4))
    root = certificates.make_certificate("Raíz", root_key, authority=True)
    middle = certificates.make_certificate("Intermedia", middle_key, root, root_key, authority=True)
    leaf = certificates.make_certificate("Persona", key, middle, middle_key)
    # Same name as the intermediate, but another key: must not be taken for it.
    impostor = certificates.make_certificate("Intermedia", other_key, root, root_key, True)
    other = certificates.make_certificate("Otra raíz", other_key, authority=True)

    def load(certificate):
        return asn1_x509.Certificate.load(certificates.der(certificate))

    return {
        "root": load(root),
        "middle": load(middle),
        "leaf": load(leaf),
        "impostor": load(impostor),
        "other": load(other),
    }


def test_chain_goes_from_the_person_up_to_the_root(family):
    pool = [family["other"], family["impostor"], family["root"], family["middle"]]
    chain = build_chain(family["leaf"], pool)
    assert [c.subject.native["common_name"] for c in chain] == ["Intermedia", "Raíz"]
    assert chain[0].key_identifier == family["middle"].key_identifier


def test_chain_stops_where_an_authority_is_missing(family):
    assert build_chain(family["leaf"], [family["root"], family["other"]]) == []
    assert build_chain(family["leaf"], [family["middle"]]) == [family["middle"]]


def test_a_self_signed_certificate_has_no_chain(family):
    assert build_chain(family["root"], list(family.values())) == []


def test_field_names_do_not_repeat(sample, signer, tmp_path):
    first = sign_pdf(sample("formulario.pdf"), tmp_path / "1.pdf", signer)
    second = sign_pdf(first, tmp_path / "2.pdf", signer)
    third = sign_pdf(second, tmp_path / "3.pdf", signer)
    with third.open("rb") as handle:
        assert signing.next_field_name(PdfFileReader(handle)) == "Firma4"
    assert len(check_signatures(third, signer.signing_cert)) == 3
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.mark.parametrize(
    ("made", "refused"),
    [
        ({"days_valid": -1, "started_days_ago": 30}, signing.CertificateExpired),
        ({"started_days_ago": -5}, signing.CertificateExpired),
        ({"for_signing": False}, signing.NotForSigning),
    ],
)
def test_a_certificate_file_validators_would_refuse_is_refused_now(tmp_path, made, refused):
    key = certificates.new_key()
    certificate = certificates.make_certificate("PRUEBA CADUCADA", key, **made)
    p12 = tmp_path / "viejo.p12"
    p12.write_bytes(certificates.make_p12("viejo", key, certificate))
    with pytest.raises(refused):
        load_p12_signer(p12, certificates.PASSWORD)


# Task 4.3: visible signature and timestamp.


def blank_page(path, rotation=0, crop=None):
    import pymupdf

    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        if crop is not None:
            page.set_cropbox(pymupdf.Rect(crop))
        page.set_rotation(rotation)
        doc.save(path)
    return path


@pytest.fixture
def handwritten() -> bytes:
    """A blue line with a red end at its left, like the picture tests."""
    import pymupdf

    from app.core import my_signature

    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1200, 800), 0)
    pix.clear_with(215)
    pix.set_rect(pymupdf.IRect(300, 400, 900, 430), (20, 30, 120))
    pix.set_rect(pymupdf.IRect(300, 400, 330, 438), (200, 0, 0))
    return my_signature.clean(pix.tobytes("png"))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_visible_signature_is_where_it_was_put_and_upright(
    signer, handwritten, tmp_path, rotation
):
    import pymupdf

    source = blank_page(tmp_path / "hoja.pdf", rotation)
    rect = (100.0, 100.0, 270.0, 156.0)
    target = sign_pdf(
        source, tmp_path / "firmado.pdf", signer, signing.Visible(0, rect, handwritten)
    )
    ((_signature, status),) = check_signatures(target, signer.signing_cert)
    assert status.intact and status.valid and status.trusted
    with pymupdf.open(target) as doc:
        page = doc[0]
        (widget,) = page.widgets()
        shown = widget.rect * page.rotation_matrix
        assert all(abs(a - b) < 0.6 for a, b in zip(shown, rect, strict=True))
        picture = page.get_pixmap(dpi=72)
        red = picture.pixel(104, 128)
        assert red[0] > 150 and red[2] < 100, "the handwritten signature, red end at the left"
        assert picture.pixel(140, 128)[2] > 80, "its blue line goes right"
        inked = [picture.pixel(x, y) for x in range(180, 268) for y in range(102, 154)]
        assert any(max(pixel) < 120 for pixel in inked), "the name and date at the right"


def test_a_visible_signature_on_a_cropped_page_and_without_handwriting(signer, tmp_path):
    import pymupdf

    source = blank_page(tmp_path / "recortada.pdf", crop=(40, 60, 555, 800))
    rect = (20.0, 30.0, 190.0, 86.0)
    target = sign_pdf(source, tmp_path / "firmado.pdf", signer, signing.Visible(0, rect))
    with pymupdf.open(target) as doc:
        (widget,) = doc[0].widgets()
        assert all(abs(a - b) < 0.6 for a, b in zip(widget.rect, rect, strict=True))
        inked = doc[0].get_pixmap(dpi=72, clip=pymupdf.Rect(rect), annots=True)
        assert any(min(inked.pixel(x, y)) < 120 for x in range(5, 60) for y in range(5, 50)), (
            "without handwriting, the text starts at the left"
        )


def test_the_box_says_who_signs_and_when():
    import pymupdf

    picture = signing.appearance(170, 56, "MUÑOZ ÁLVAREZ ÍÑIGO", "22/11/2026 10:30", None)
    with pymupdf.open(stream=picture, filetype="pdf") as doc:
        text = doc[0].get_text()
    assert "Firmado digitalmente por" in text
    assert "MUÑOZ ÁLVAREZ ÍÑIGO" in text
    assert "22/11/2026 10:30" in text


def test_a_box_outside_the_page_is_refused(signer, tmp_path):
    source = blank_page(tmp_path / "hoja.pdf")
    with pytest.raises(SigningError):
        sign_pdf(source, tmp_path / "a.pdf", signer, signing.Visible(0, (700, 900, 800, 950)))
    with pytest.raises(SigningError):
        sign_pdf(source, tmp_path / "b.pdf", signer, signing.Visible(3, (10, 10, 100, 50)))
    assert not list(tmp_path.glob("*.tmp")) and not (tmp_path / "a.pdf").exists()


@pytest.fixture
def timestamp_server():
    """A timestamping server on this computer, as the real ones answer."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from asn1crypto import keys, tsp
    from cryptography.hazmat.primitives import serialization
    from pyhanko.sign.timestamps import DummyTimeStamper

    key = certificates.new_key()
    certificate = certificates.make_certificate("SELLO DE TIEMPO DE PRUEBA", key)
    stamper = DummyTimeStamper(
        tsa_cert=asn1_x509.Certificate.load(certificates.der(certificate)),
        tsa_key=keys.PrivateKeyInfo.load(
            key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        ),
    )
    asked = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            asked.append(self.headers["Content-Type"])
            answer = stamper.request_tsa_response(tsp.TimeStampReq.load(body)).dump()
            self.send_response(200)
            self.send_header("Content-Type", "application/timestamp-reply")
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/tsa", asked
    server.shutdown()


def test_a_timestamp_is_added_when_asked(sample, signer, tmp_path, timestamp_server):
    url, asked = timestamp_server
    target = sign_pdf(sample("formulario.pdf"), tmp_path / "f.pdf", signer, timestamp_server=url)
    assert asked and set(asked) == {"application/timestamp-query"}
    ((_signature, status),) = check_signatures(target, signer.signing_cert)
    assert status.intact and status.valid
    assert status.timestamp_validity is not None


def test_no_timestamp_unless_asked(sample, signer, tmp_path):
    target = sign_pdf(sample("formulario.pdf"), tmp_path / "f.pdf", signer)
    ((_signature, status),) = check_signatures(target, signer.signing_cert)
    assert status.timestamp_validity is None


def test_an_unreachable_timestamp_server_fails_clearly_and_leaves_nothing(sample, signer, tmp_path):
    with pytest.raises(signing.TimestampFailed):
        sign_pdf(
            sample("formulario.pdf"),
            tmp_path / "f.pdf",
            signer,
            timestamp_server="http://127.0.0.1:9/tsa",
        )
    assert list(tmp_path.iterdir()) == []


def test_the_visible_signature_is_a_white_card():
    """Put over printed text, the signature must not mix with it."""
    import pymupdf

    picture = signing.appearance(170, 56, "MUÑOZ ÁLVAREZ ÍÑIGO", "22/11/2026 10:30", None)
    with pymupdf.open(stream=picture, filetype="pdf") as doc:
        pixmap = doc[0].get_pixmap(alpha=True)
    # A spot inside the box with no letters: white and not see-through.
    assert pixmap.pixel(pixmap.width - 8, pixmap.height - 6) == (255, 255, 255, 255)
