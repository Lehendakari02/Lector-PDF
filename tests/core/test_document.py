"""Tests for app.core.document."""

from pathlib import Path

import pymupdf
import pytest

from app.core.document import PdfOpenError, engine_version, read_document_info


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
