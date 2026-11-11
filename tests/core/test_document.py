"""Tests for app.core.document."""

from pathlib import Path

import pymupdf
import pytest

from app.core.document import PdfDocument, PdfOpenError, engine_version, read_document_info


def make_pdf(path: Path, pages: int = 1, password: str | None = None) -> Path:
    """Create a small PDF with ``pages`` pages, optionally password-protected."""
    doc = pymupdf.open()
    for number in range(1, pages + 1):
        page = doc.new_page()
        page.insert_text((72, 72), f"Página {number}")
    if password:
        doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password)
    else:
        doc.save(path)
    doc.close()
    return path


def test_reads_page_count(tmp_path):
    info = read_document_info(make_pdf(tmp_path / "three.pdf", pages=3))
    assert info.page_count == 3
    assert info.needs_password is False
    assert info.path == tmp_path / "three.pdf"


def test_accepts_path_as_text_with_spanish_characters(tmp_path):
    path = make_pdf(tmp_path / "Constitución española (año 1978).pdf")
    assert read_document_info(str(path)).page_count == 1


def test_detects_password_protected_pdf(tmp_path):
    info = read_document_info(make_pdf(tmp_path / "locked.pdf", password="secreto"))
    assert info.needs_password is True


def test_missing_file_raises_friendly_error(tmp_path):
    with pytest.raises(PdfOpenError):
        read_document_info(tmp_path / "does-not-exist.pdf")


def test_folder_raises_friendly_error(tmp_path):
    with pytest.raises(PdfOpenError):
        read_document_info(tmp_path)


@pytest.mark.parametrize("content", [b"", b"this is not a PDF", b"%PDF-1.7\nbroken"])
def test_damaged_file_raises_friendly_error(tmp_path, content):
    path = tmp_path / "damaged.pdf"
    path.write_bytes(content)
    with pytest.raises(PdfOpenError):
        read_document_info(path)


def test_does_not_keep_the_file_locked(tmp_path):
    # On Windows an open file cannot be deleted; this must not happen after reading.
    path = make_pdf(tmp_path / "temporary.pdf")
    read_document_info(path)
    path.unlink()
    assert not path.exists()


def test_engine_version_is_reported():
    assert engine_version()


def test_pdf_document_gives_page_count_and_sizes(sample):
    with PdfDocument(sample("boe.pdf")) as document:
        assert document.page_count == 39
        sizes = document.page_sizes()
        assert len(sizes) == 39
        assert round(sizes[0].width) == 595 and round(sizes[0].height) == 842
        assert not document.needs_password


def test_pdf_document_reads_520_page_sizes_quickly(sample):
    import time

    started = time.perf_counter()
    with PdfDocument(sample("largo.pdf")) as document:
        assert len(document.page_sizes()) == 520
    assert time.perf_counter() - started < 2  # measured: about 10 ms


def test_pdf_document_says_when_a_password_is_needed(sample):
    with PdfDocument(sample("con-contrasena.pdf")) as document:
        assert document.needs_password


def test_pdf_document_rejects_missing_and_broken_files(tmp_path):
    with pytest.raises(PdfOpenError):
        PdfDocument(tmp_path / "no-existe.pdf")
    broken = tmp_path / "roto.pdf"
    broken.write_bytes(b"not a pdf at all")
    with pytest.raises(PdfOpenError):
        PdfDocument(broken)


def test_pdf_document_can_be_closed_twice(sample):
    document = PdfDocument(sample("boe.pdf"))
    document.close()
    document.close()
