"""Tests for «Comprimir» and «Contraseña»: the copies, and signing them after."""

import io
import random

import pymupdf
import pytest
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from app.core.combine import NeedsPassword, Source
from app.core.compress import STRONG, NotSmaller, compress, size_text
from app.core.protection import (
    ProtectionError,
    protect,
    protection_apart,
    state_of,
    unprotect,
)
from app.core.signing import load_p12_signer, sign_pdf


def test_the_state_of_each_kind_of_document(sample):
    assert state_of(sample("boe.pdf")) == "none"
    assert state_of(sample("con-contrasena.pdf")) == "password"
    assert state_of(sample("restringido.pdf")) == "restricted"


def test_a_protected_copy_asks_for_its_password(sample, tmp_path):
    before = sample("boe.pdf").read_bytes()
    target = protect(Source(sample("boe.pdf")), tmp_path / "cerrado.pdf", "clave1")
    assert sample("boe.pdf").read_bytes() == before, "the original stays"
    with pymupdf.open(target) as doc:
        assert doc.needs_pass
        assert not doc.authenticate("otra")
        assert doc.authenticate("clave1")
        assert "Constitución" in doc[0].get_text()
        assert doc.permissions == -1 or doc.permissions & pymupdf.PDF_PERM_PRINT
    assert state_of(target) == "password"


def test_short_passwords_and_the_original_are_refused(sample, tmp_path):
    with pytest.raises(ProtectionError):
        protect(Source(sample("boe.pdf")), tmp_path / "x.pdf", "abc")
    with pytest.raises(ProtectionError):
        protect(Source(sample("boe.pdf")), sample("boe.pdf"), "clave1")
    assert list(tmp_path.iterdir()) == []


def test_taking_the_password_off(sample, tmp_path):
    with pytest.raises(NeedsPassword):
        unprotect(Source(sample("con-contrasena.pdf")), tmp_path / "abierto.pdf")
    target = unprotect(Source(sample("con-contrasena.pdf"), "lector"), tmp_path / "abierto.pdf")
    assert state_of(target) == "none"


def test_a_restricted_document_is_not_changed(sample, tmp_path):
    with pytest.raises(ProtectionError):
        protect(Source(sample("restringido.pdf")), tmp_path / "x.pdf", "clave1")
    assert list(tmp_path.iterdir()) == []


def test_a_document_protected_here_can_be_signed(sample, tmp_path):
    protected = protect(Source(sample("formulario.pdf")), tmp_path / "cerrado.pdf", "clave1")
    signer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    signed = sign_pdf(protected, tmp_path / "firmado.pdf", signer, password="clave1")
    reader = PdfFileReader(io.BytesIO(signed.read_bytes()), strict=False)
    reader.decrypt("clave1")
    (signature,) = reader.embedded_signatures
    status = validate_pdf_signature(signature, ValidationContext(trust_roots=[signer.signing_cert]))
    assert status.intact and status.valid
    with pymupdf.open(signed) as doc:
        assert doc.needs_pass and doc.authenticate("clave1")
        assert not doc.is_repaired


def test_saving_a_protected_document_keeps_it_signable(sample, tmp_path):
    from app.core.saving import write_copy

    protected = protect(Source(sample("formulario.pdf")), tmp_path / "cerrado.pdf", "clave1")
    with pymupdf.open(protected) as doc:
        doc.authenticate("clave1")
        doc[0].add_text_annot((50, 50), "una nota")
        written = write_copy(doc, tmp_path / "guardado.pdf", "clave1")
    signer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    signed = sign_pdf(written, tmp_path / "firmado.pdf", signer, password="clave1")
    assert signed.exists()


def test_the_protection_is_put_apart_only_once(sample, tmp_path):
    protected = protect(Source(sample("formulario.pdf")), tmp_path / "cerrado.pdf", "clave1")
    assert not protection_apart(protected, "clave1"), "it is already apart"
    assert not protection_apart(sample("boe.pdf")), "nothing to do without protection"


def picture_document(path):
    """A page with a photo of about 200 points per inch (noise, so that it weighs)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    width, height = 1700, 2400
    noise = random.Random(1).randbytes(width * height * 3)
    picture = pymupdf.Pixmap(pymupdf.csRGB, width, height, noise, False)
    page.insert_image(page.rect, pixmap=picture)
    page.insert_text((50, 50), "Foto de prueba")
    doc.save(path)
    doc.close()
    return path


def test_strong_compression_makes_pictures_lighter(tmp_path):
    source = picture_document(tmp_path / "foto.pdf")
    result = compress(Source(source), tmp_path / "pequeño.pdf", STRONG)
    assert result.after < result.before / 2
    with pymupdf.open(result.target) as doc:
        assert "Foto de prueba" in doc[0].get_text()
        (info,) = doc[0].get_image_info()
        assert info["width"] < 1700


def test_a_document_already_small_is_not_copied(sample, tmp_path):
    with pytest.raises(NotSmaller) as caught:
        compress(Source(sample("escaneado.pdf")), tmp_path / "x.pdf")
    assert caught.value.after > 0
    assert list(tmp_path.iterdir()) == [], "no copy and no temporary file left"


def test_a_protected_document_stays_protected_and_signable(sample, tmp_path):
    source = picture_document(tmp_path / "foto.pdf")
    protected = protect(Source(source), tmp_path / "cerrado.pdf", "clave1")
    result = compress(Source(protected, "clave1"), tmp_path / "pequeño.pdf", STRONG)
    assert state_of(result.target) == "password"
    signer = load_p12_signer(sample("certificado-prueba.p12"), "prueba")
    assert sign_pdf(result.target, tmp_path / "firmado.pdf", signer, password="clave1").exists()


def test_sizes_as_people_say_them():
    assert size_text(300) == "1 KB"
    assert size_text(850 * 1024) == "850 KB"
    assert size_text(int(12.4 * 1024 * 1024)) == "12,4 MB"
