"""Tests for saving the document from the helper process that has it open."""

import os
import threading
from pathlib import Path

import pymupdf
import pytest

from app.core import saving
from app.core.render_service import (
    RenderRequest,
    RenderService,
    _save_document,
    _SaveFailed,
)

WAIT_SECONDS = 30


class Saver:
    """A service with a document open, that lets a test wait for the answers."""

    def __init__(self):
        self.saved: list[tuple[int, Path]] = []
        self.failed: list[tuple[int, str, str]] = []
        self.pages = []
        self._changed = threading.Condition()
        self.service = RenderService(
            on_page=lambda page: self._add(self.pages, page),
            on_saved=lambda number, path: self._add(self.saved, (number, path)),
            on_save_failed=lambda *failure: self._add(self.failed, failure),
        )

    def _add(self, where, item):
        with self._changed:
            where.append(item)
            self._changed.notify_all()

    def wait(self, condition):
        with self._changed:
            assert self._changed.wait_for(condition, WAIT_SECONDS), "timed out"


@pytest.fixture
def saver():
    made = Saver()
    yield made
    made.service.shutdown()


@pytest.fixture
def copy_of(sample, tmp_path):
    def make(name: str = "boe.pdf") -> Path:
        target = tmp_path / name
        target.write_bytes(Path(sample(name)).read_bytes())
        return target

    return make


def highlight(doc) -> None:
    doc[0].add_highlight_annot(pymupdf.Rect(60, 60, 200, 80))


def highlights(path, password=None) -> int:
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            assert doc.authenticate(password)
        return sum(1 for annot in doc[0].annots() or [] if annot.type[1] == "Highlight")


# ---- the saving itself, with a changed document ---------------------------------


def test_saving_over_its_own_file_keeps_the_document_open(copy_of):
    path = copy_of()
    doc = pymupdf.open(path)
    highlight(doc)
    doc = _save_document(doc, str(path), None, str(path))
    try:
        assert highlights(path) == 1
        assert not saving.temp_path_for(path).exists()
        assert len(doc[0].get_text("words")) > 0  # goes on from the saved file
        highlight(doc)
        doc = _save_document(doc, str(path), None, str(path))  # and can be saved again
        assert highlights(path) == 2
    finally:
        doc.close()


def test_save_as_moves_the_document_to_the_new_file(copy_of, tmp_path):
    path = copy_of()
    before = path.read_bytes()
    target = tmp_path / "con subrayado.pdf"
    doc = pymupdf.open(path)
    highlight(doc)
    doc = _save_document(doc, str(path), None, str(target))
    try:
        assert highlights(target) == 1
        assert path.read_bytes() == before, "the first file stays as it was"
        assert Path(doc.name) == target
    finally:
        doc.close()


def test_a_held_file_fails_and_the_changes_stay_in_the_open_document(copy_of, monkeypatch):
    path = copy_of()
    before = path.read_bytes()
    monkeypatch.setattr(saving, "REPLACE_TRIES", 1)
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, path.name)
    doc = pymupdf.open(path)
    highlight(doc)
    with pytest.raises(_SaveFailed) as failure:
        _save_document(doc, str(path), None, str(path))
    kept = failure.value.doc
    try:
        assert failure.value.error.kind == saving.LOCKED
        assert path.read_bytes() == before, "the file on disk is the old one, whole"
        assert not saving.temp_path_for(path).exists()
        assert sum(1 for _ in kept[0].annots()) == 1, "the change is still there"
        # The other program lets go: saving again works and has the change.
        monkeypatch.delenv(saving.TEST_LOCKED_FILES)
        kept = _save_document(kept, str(path), None, str(path))
        assert highlights(path) == 1
    finally:
        kept.close()


def test_save_as_to_a_held_file_leaves_the_document_as_it_was(copy_of, tmp_path, monkeypatch):
    path = copy_of()
    target = tmp_path / "otro.pdf"
    target.write_bytes(b"something else")
    monkeypatch.setattr(saving, "REPLACE_TRIES", 1)
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, target.name)
    doc = pymupdf.open(path)
    highlight(doc)
    with pytest.raises(_SaveFailed) as failure:
        _save_document(doc, str(path), None, str(target))
    try:
        assert failure.value.doc is doc and not doc.is_closed
        assert target.read_bytes() == b"something else"
        assert not saving.temp_path_for(target).exists()
    finally:
        doc.close()


def test_a_protected_document_is_saved_and_goes_on_open(copy_of):
    path = copy_of("con-contrasena.pdf")
    doc = pymupdf.open(path)
    assert doc.authenticate("lector")
    highlight(doc)
    doc = _save_document(doc, str(path), "lector", str(path))
    try:
        assert len(doc[0].get_text("words")) > 0  # opened again with its password
        assert highlights(path, "lector") == 1
    finally:
        doc.close()


# ---- through the helper process -------------------------------------------------


def test_the_helper_saves_in_the_same_file_and_goes_on_drawing(saver, copy_of):
    path = copy_of()
    saver.service.open(path)
    number = saver.service.save()
    saver.wait(lambda: saver.saved or saver.failed)
    assert saver.saved == [(number, path)] and saver.failed == []
    with pymupdf.open(path) as doc:
        assert doc.page_count > 0 and not doc.is_repaired
    saver.service.want([RenderRequest(0, 1.0)])
    saver.wait(lambda: saver.pages)
    assert saver.pages[0].page == 0


def test_the_helper_saves_as_another_file_and_lets_go_of_the_first(saver, copy_of, tmp_path):
    path = copy_of()
    target = tmp_path / "copia.pdf"
    saver.service.open(path)
    number = saver.service.save(target)
    saver.wait(lambda: saver.saved or saver.failed)
    assert saver.saved == [(number, target)]
    with pymupdf.open(target) as doc:
        assert doc.page_count > 0
    # The first file is free: it can be removed even on Windows.
    os.remove(path)
    saver.service.want([RenderRequest(1, 1.0)])
    saver.wait(lambda: saver.pages)
    # Saving again goes to the new file.
    again = saver.service.save()
    saver.wait(lambda: len(saver.saved) == 2 or saver.failed)
    assert saver.saved[1] == (again, target)


def test_the_helper_reports_a_file_it_cannot_write(saver, copy_of, tmp_path):
    path = copy_of()
    saver.service.open(path)
    number = saver.service.save(tmp_path / "no-existe" / "copia.pdf")
    saver.wait(lambda: saver.saved or saver.failed)
    assert saver.saved == [] and saver.failed[0][0] == number
    saver.service.want([RenderRequest(0, 1.0)])  # the document is still open
    saver.wait(lambda: saver.pages)


@pytest.mark.skipif(os.name != "nt", reason="only Windows refuses to replace a file in use")
def test_the_helper_cannot_replace_a_file_another_program_holds(saver, copy_of):
    path = copy_of()
    before = path.read_bytes()
    saver.service.open(path)
    saver.service.want([RenderRequest(0, 1.0)])
    saver.wait(lambda: saver.pages)
    with open(path, "rb"):
        saver.service.save()
        saver.wait(lambda: saver.saved or saver.failed)
        assert saver.failed and saver.failed[0][1] == saving.LOCKED
    assert path.read_bytes() == before
    saver.service.save()  # the other program closed it
    saver.wait(lambda: saver.saved)
    assert saver.saved[0][1] == path


def test_saving_with_nothing_open_fails_at_once(saver):
    number = saver.service.save()
    assert saver.failed == [(number, saving.FAILED, "no document is open")]
