"""Tests for the earlier versions of a PDF."""

import os
from pathlib import Path

import pytest

from app.core.versions import NOTE_NAME, VersionError, Versions


@pytest.fixture
def versions(tmp_path) -> Versions:
    return Versions(tmp_path / "versiones")


@pytest.fixture
def pdf(tmp_path) -> Path:
    path = tmp_path / "tema 5 – año.pdf"
    path.write_bytes(b"%PDF-1.7 as it was this morning")
    return path


def test_nothing_is_kept_at_first(versions, pdf):
    assert versions.of(pdf) == [] and versions.all() == []
    assert not versions.folder.exists()


def test_a_copy_of_the_file_as_it_is_is_kept(versions, pdf):
    before = pdf.read_bytes()
    version = versions.keep(pdf, now=1000.0)
    assert version.file.read_bytes() == before
    assert version.document == pdf and version.when == 1000.0 and version.size == len(before)
    assert versions.of(pdf) == [version]
    assert pdf.read_bytes() == before, "the document itself is not touched"
    assert version.file.parent.parent == versions.folder


def test_the_newest_comes_first(versions, pdf):
    first = versions.keep(pdf, now=1000.0)
    pdf.write_bytes(b"%PDF second")
    second = versions.keep(pdf, now=2000.0)
    pdf.write_bytes(b"%PDF third")
    third = versions.keep(pdf, now=3000.0)
    assert versions.of(pdf) == [third, second, first]
    assert [v.file.read_bytes() for v in versions.of(pdf)][2] == b"%PDF-1.7 as it was this morning"


def test_the_same_content_is_not_kept_twice(versions, pdf):
    assert versions.keep(pdf, now=1000.0) is not None
    assert versions.keep(pdf, now=2000.0) is None
    assert len(versions.of(pdf)) == 1
    pdf.write_bytes(b"%PDF-1.7 as it was this evening")  # same length, other content
    assert versions.keep(pdf, now=3000.0) is not None


def test_a_file_that_does_not_exist_yet_has_nothing_to_keep(versions, tmp_path):
    assert versions.keep(tmp_path / "nuevo.pdf") is None
    assert versions.all() == []


def test_each_document_has_its_own_versions(versions, pdf, tmp_path):
    other = tmp_path / "ley.pdf"
    other.write_bytes(b"%PDF law")
    versions.keep(pdf, now=1000.0)
    versions.keep(other, now=2000.0)
    assert [v.document for v in versions.of(pdf)] == [pdf]
    assert [v.document for v in versions.of(other)] == [other]
    assert [v.document for v in versions.all()] == [other, pdf]
    assert versions.total_bytes() == pdf.stat().st_size + other.stat().st_size


def test_two_copies_in_the_same_instant_do_not_step_on_each_other(versions, pdf):
    versions.keep(pdf, now=1000.0)
    pdf.write_bytes(b"%PDF second")
    versions.keep(pdf, now=1000.0)
    assert len(versions.of(pdf)) == 2


def test_no_temporary_files_are_left(versions, pdf):
    version = versions.keep(pdf)
    names = sorted(file.name for file in version.file.parent.iterdir())
    assert names == sorted([version.file.name, NOTE_NAME])


# ---- putting back ----------------------------------------------------------


def test_restoring_puts_the_version_back_and_keeps_how_it_was(versions, pdf):
    morning = versions.keep(pdf, now=1000.0)
    pdf.write_bytes(b"%PDF with marks I did not want")
    versions.restore(morning)
    assert pdf.read_bytes() == b"%PDF-1.7 as it was this morning"
    contents = [v.file.read_bytes() for v in versions.of(pdf)]
    assert b"%PDF with marks I did not want" in contents, "restoring can be undone too"
    assert not [f for f in pdf.parent.iterdir() if "restaurando" in f.name]


def test_restoring_a_version_that_is_gone_fails_and_touches_nothing(versions, pdf):
    morning = versions.keep(pdf, now=1000.0)
    pdf.write_bytes(b"%PDF now")
    morning.file.unlink()
    with pytest.raises(VersionError):
        versions.restore(morning)
    assert pdf.read_bytes() == b"%PDF now"


def test_restoring_where_it_cannot_be_written_fails_and_loses_nothing(versions, pdf, tmp_path):
    morning = versions.keep(pdf, now=1000.0)
    blocked = tmp_path / "archivo"
    blocked.write_text("a file, not a folder")
    with pytest.raises(VersionError):
        versions.restore(morning, blocked / "tema.pdf")
    assert morning.file.exists() and pdf.exists()


def test_a_version_can_be_put_in_another_file(versions, pdf, tmp_path):
    morning = versions.keep(pdf, now=1000.0)
    copy = tmp_path / "otra carpeta" / "copia.pdf"
    assert versions.restore(morning, copy) == copy
    assert copy.read_bytes() == morning.file.read_bytes()


def test_keeping_fails_cleanly_when_there_is_no_room(tmp_path, pdf):
    blocked = tmp_path / "archivo"
    blocked.write_text("a file, not a folder")
    with pytest.raises(VersionError):
        Versions(blocked / "versiones").keep(pdf)


# ---- limits ----------------------------------------------------------------


def test_only_so_many_versions_of_each_document_are_kept(tmp_path, pdf):
    versions = Versions(tmp_path / "versiones", max_per_document=3)
    for number in range(6):
        pdf.write_bytes(f"%PDF number {number}".encode())
        versions.keep(pdf, now=1000.0 + number)
    kept = [v.file.read_bytes() for v in versions.of(pdf)]
    assert kept == [b"%PDF number 5", b"%PDF number 4", b"%PDF number 3"]


def test_the_oldest_go_when_they_take_too_much_room(tmp_path):
    versions = Versions(tmp_path / "versiones", max_total_bytes=250)
    files = []
    for number in range(4):
        file = tmp_path / f"tema-{number}.pdf"
        file.write_bytes(bytes([65 + number]) * 100)
        files.append(file)
        versions.keep(file, now=1000.0 + number)
    assert [v.document.name for v in versions.all()] == ["tema-3.pdf", "tema-2.pdf"]
    assert versions.total_bytes() <= 250
    assert len(list(versions.folder.iterdir())) == 2, "empty folders are cleared away"


def test_the_version_just_made_is_never_deleted_for_lack_of_room(tmp_path, pdf):
    versions = Versions(tmp_path / "versiones", max_total_bytes=5)
    version = versions.keep(pdf)
    assert version is not None and versions.of(pdf) == [version]


def test_forgetting_a_version(versions, pdf):
    version = versions.keep(pdf)
    versions.forget(version)
    assert versions.of(pdf) == [] and not version.file.parent.exists()


def test_strange_files_in_the_folder_are_ignored(versions, pdf):
    version = versions.keep(pdf, now=1000.0)
    (version.file.parent / "notas.pdf").write_bytes(b"x")
    (versions.folder / "suelto.txt").write_text("x")
    (versions.folder / "sin-nota").mkdir()
    (versions.folder / "sin-nota" / "0000000001000.pdf").write_bytes(b"x")
    assert versions.of(pdf) == [version]
    assert versions.all() == [version]


@pytest.mark.skipif(os.name == "nt", reason="capitals only differ on other systems")
def test_capitals_make_different_documents_where_the_system_says_so(versions, pdf):
    other = pdf.with_name(pdf.name.upper())
    other.write_bytes(b"%PDF other")
    versions.keep(pdf)
    assert versions.of(other) == []
