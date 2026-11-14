"""Tests for what is looked at before saving over a PDF."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app.core.save_checks import (
    CHANGED_OUTSIDE,
    SIGNED,
    TEMPORARY,
    changed_outside,
    in_temporary_folder,
    is_signed,
    stamp_of,
    warnings_for,
)

SAMPLES = Path(__file__).resolve().parents[1] / "ejemplos"
HOME = Path.home()


def test_a_signed_pdf_is_noticed():
    assert is_signed(SAMPLES / "firmado.pdf")


@pytest.mark.parametrize("name", ["boe.pdf", "formulario.pdf", "escaneado.pdf"])
def test_pdfs_without_signature_are_not_signed(name):
    assert not is_signed(SAMPLES / name)


def test_an_empty_signature_field_is_not_a_signature(tmp_path):
    import pymupdf

    path = tmp_path / "por-firmar.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
    widget.field_name = "firma"
    widget.rect = pymupdf.Rect(50, 50, 250, 120)
    page.add_widget(widget)
    doc.save(path)
    doc.close()
    assert not is_signed(path)


def test_what_cannot_be_read_is_not_signed(tmp_path):
    broken = tmp_path / "roto.pdf"
    broken.write_bytes(b"this is not a PDF")
    assert not is_signed(broken)
    assert not is_signed(tmp_path / "no-existe.pdf")
    assert not is_signed(SAMPLES / "con-contrasena.pdf"), "without its password"


def test_a_file_untouched_has_not_changed(tmp_path):
    path = tmp_path / "tema.pdf"
    path.write_bytes(b"%PDF one")
    known = stamp_of(path)
    assert known is not None and not changed_outside(path, known)


def test_a_file_written_by_somebody_else_has_changed(tmp_path):
    path = tmp_path / "tema.pdf"
    path.write_bytes(b"%PDF one")
    known = stamp_of(path)
    path.write_bytes(b"%PDF two, longer")
    assert changed_outside(path, known)


def test_the_same_size_written_later_has_changed_too(tmp_path):
    path = tmp_path / "tema.pdf"
    path.write_bytes(b"%PDF one")
    known = stamp_of(path)
    path.write_bytes(b"%PDF two")
    os.utime(path, ns=(known.modified + 2_000_000_000, known.modified + 2_000_000_000))
    assert changed_outside(path, known)


def test_a_file_that_is_gone_counts_as_changed(tmp_path):
    path = tmp_path / "tema.pdf"
    path.write_bytes(b"%PDF one")
    known = stamp_of(path)
    path.unlink()
    assert stamp_of(path) is None and changed_outside(path, known)


def test_with_nothing_known_nothing_has_changed(tmp_path):
    assert not changed_outside(tmp_path / "tema.pdf", None)


def test_files_in_the_temporary_folder_are_noticed():
    assert in_temporary_folder(Path(tempfile.gettempdir()) / "adjunto.pdf")
    assert in_temporary_folder(Path(tempfile.gettempdir()) / "zip1234" / "adjunto.pdf")


def test_files_in_the_users_folders_are_not_temporary():
    assert not in_temporary_folder(HOME / "Documentos" / "Oposición" / "tema.pdf", "/tmp")
    assert not in_temporary_folder("/tmpotra/tema.pdf", "/tmp"), "only a name that starts alike"


@pytest.mark.parametrize(
    "folder",
    [
        "C:/Users/julia/AppData/Local/Microsoft/Windows/INetCache/Content.Outlook/AB12CD/",
        "C:/Users/julia/AppData/Local/Temp/7zO4A1B/",
        "C:/Users/julia/AppData/Local/Microsoft/Windows/Temporary Internet Files/",
    ],
)
def test_where_mail_programs_leave_attachments_is_temporary(folder):
    assert in_temporary_folder(folder + "nomina.pdf", "Z:/otra")


def test_every_reason_is_told_the_gravest_first(tmp_path):
    path = tmp_path / "contrato.pdf"
    shutil.copy(SAMPLES / "firmado.pdf", path)
    known = stamp_of(path)
    assert warnings_for(path, known, temp_dir=tmp_path / "otra") == [SIGNED]
    assert warnings_for(path, known, temp_dir=tmp_path) == [SIGNED, TEMPORARY]
    os.utime(path, ns=(known.modified + 5_000_000_000, known.modified + 5_000_000_000))
    assert warnings_for(path, known, temp_dir=tmp_path) == [CHANGED_OUTSIDE, SIGNED, TEMPORARY]


def test_an_ordinary_file_has_no_warnings(tmp_path):
    path = tmp_path / "tema.pdf"
    shutil.copy(SAMPLES / "boe.pdf", path)
    assert warnings_for(path, stamp_of(path), temp_dir=tmp_path / "otra") == []
