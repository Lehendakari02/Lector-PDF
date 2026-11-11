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
