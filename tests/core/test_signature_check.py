"""Tests for looking at the signatures a PDF has (task 4.6)."""

import shutil

import pymupdf
import pytest

from app.core.signature_check import (
    ANNOTATED,
    CHANGED,
    FORM_FILLED,
    MORE_SIGNATURES,
    UNCHANGED,
    check_signatures,
)
from app.core.signing import Visible, load_p12_signer, sign_pdf


@pytest.fixture
def signer(sample):
    return load_p12_signer(sample("certificado-prueba.p12"), "prueba")


@pytest.fixture
def signed(sample, signer, tmp_path):
    return sign_pdf(sample("formulario.pdf"), tmp_path / "firmado.pdf", signer)


def test_a_document_without_signatures_has_none(sample):
    assert check_signatures(sample("formulario.pdf"), roots=[]) == []


def test_a_good_signature_says_who_and_when(signed, signer):
    (report,) = check_signatures(signed, roots=[signer.signing_cert])
    assert report.good
    assert report.intact and report.trusted and report.after == UNCHANGED
    assert "PERSONA DE PRUEBA" in report.signer
    assert report.signed_at is not None and not report.timestamped
    assert report.page is None, "invisible"


def test_an_unknown_authority_is_told_apart_from_a_broken_signature(signed):
    (report,) = check_signatures(signed, roots=[])
    assert report.intact and not report.trusted and not report.good


def test_a_change_to_the_signed_bytes_breaks_it(signed, signer):
    data = bytearray(signed.read_bytes())
    where = data.index(b"Nombre")
    data[where : where + 6] = b"Nambre"
    signed.write_bytes(bytes(data))
    (report,) = check_signatures(signed, roots=[signer.signing_cert])
    assert not report.intact and not report.good


def test_what_was_added_after_signing_is_told(signed, signer, tmp_path):
    second = sign_pdf(signed, tmp_path / "dos.pdf", signer)
    first, last = check_signatures(second, roots=[signer.signing_cert])
    assert first.after in (MORE_SIGNATURES, FORM_FILLED) and first.good
    assert last.after == UNCHANGED

    annotated = tmp_path / "anotado.pdf"
    shutil.copy(signed, annotated)
    with pymupdf.open(annotated) as doc:
        doc[0].add_text_annot((100, 100), "Una nota")
        doc.saveIncr()
    (report,) = check_signatures(annotated, roots=[signer.signing_cert])
    assert report.intact and report.after in (ANNOTATED, CHANGED)
    assert report.after != UNCHANGED


def test_a_visible_signature_says_its_page(sample, signer, tmp_path):
    target = sign_pdf(
        sample("largo.pdf"), tmp_path / "v.pdf", signer, Visible(2, (50, 50, 220, 106))
    )
    (report,) = check_signatures(target, roots=[signer.signing_cert])
    assert report.page == 2


def test_the_sample_signed_document_can_be_read(sample):
    reports = check_signatures(sample("firmado.pdf"), roots=[])
    assert reports and all(report.signer for report in reports)


def test_a_file_that_is_not_a_pdf_raises_clearly(tmp_path):
    broken = tmp_path / "roto.pdf"
    broken.write_bytes(b"not a pdf")
    with pytest.raises((ValueError, OSError)):
        check_signatures(broken, roots=[])
