"""Tests for writing PDFs safely: never half written, nothing lost on failure."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pymupdf
import pytest

from app.core import saving
from app.core.saving import SaveError, put_in_place, save_to, temp_path_for, write_copy


@pytest.fixture
def copy_of(sample, tmp_path):
    """A copy of a sample PDF in a temporary folder, free to be changed."""

    def make(name: str = "boe.pdf") -> Path:
        target = tmp_path / name
        target.write_bytes(Path(sample(name)).read_bytes())
        return target

    return make


def highlight_first_word(doc) -> None:
    page = doc[0]
    x0, y0, x1, y1 = page.get_text("words")[0][:4]
    page.add_highlight_annot(pymupdf.Rect(x0, y0, x1, y1))


def highlights(path: Path, password: str | None = None) -> int:
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            assert doc.authenticate(password)
        return sum(1 for annot in doc[0].annots() or [] if annot.type[1] == "Highlight")


def test_the_temporary_file_sits_next_to_the_target(tmp_path):
    temp = temp_path_for(tmp_path / "tema.pdf")
    assert temp.parent == tmp_path and temp.name != "tema.pdf"
    assert temp.name.endswith(saving.TEMP_SUFFIX)


def test_a_change_is_saved_in_another_file(copy_of, tmp_path):
    original = copy_of()
    before = original.read_bytes()
    target = tmp_path / "copia.pdf"
    with pymupdf.open(original) as doc:
        highlight_first_word(doc)
        save_to(doc, target)
    assert highlights(target) == 1
    assert original.read_bytes() == before, "the original is not touched"
    assert not temp_path_for(target).exists()


def test_writing_the_copy_does_not_touch_the_target(copy_of):
    target = copy_of()
    before = target.read_bytes()
    with pymupdf.open(stream=before, filetype="pdf") as doc:
        highlight_first_word(doc)
        temp = write_copy(doc, target)
        assert target.read_bytes() == before
        assert highlights(temp) == 1
        put_in_place(temp, target)
    assert highlights(target) == 1 and not temp.exists()


def test_a_leftover_of_a_save_cut_short_does_not_get_in_the_way(copy_of):
    target = copy_of()
    temp_path_for(target).write_bytes(b"half a PDF")
    with pymupdf.open(stream=target.read_bytes(), filetype="pdf") as doc:
        highlight_first_word(doc)
        save_to(doc, target)
    assert highlights(target) == 1 and not temp_path_for(target).exists()


def test_a_protected_document_keeps_its_password(copy_of):
    target = copy_of("con-contrasena.pdf")
    with pymupdf.open(stream=target.read_bytes(), filetype="pdf") as doc:
        assert doc.authenticate("lector")
        highlight_first_word(doc)
        save_to(doc, target, "lector")
    with pymupdf.open(target) as saved:
        assert saved.needs_pass, "still protected"
    assert highlights(target, "lector") == 1


def test_a_file_held_by_another_program_is_reported_and_nothing_is_lost(copy_of, monkeypatch):
    target = copy_of()
    before = target.read_bytes()
    monkeypatch.setenv(saving.TEST_LOCKED_FILES, target.name)
    with pymupdf.open(stream=before, filetype="pdf") as doc:
        highlight_first_word(doc)
        started = time.monotonic()
        with pytest.raises(SaveError) as failure:
            save_to(doc, target)
        assert failure.value.kind == saving.LOCKED
        assert time.monotonic() - started >= saving.REPLACE_PAUSE, "it was tried again"
        assert len(doc[0].get_text("words")) > 0  # the document is still usable
    assert target.read_bytes() == before
    assert not temp_path_for(target).exists()


@pytest.mark.skipif(os.name != "nt", reason="only Windows refuses to replace a file in use")
def test_a_file_really_open_in_another_program_cannot_be_replaced(copy_of):
    target = copy_of()
    before = target.read_bytes()
    with pymupdf.open(stream=before, filetype="pdf") as doc:
        highlight_first_word(doc)
        with open(target, "rb"):  # another program has it open
            with pytest.raises(SaveError) as failure:
                save_to(doc, target)
            assert failure.value.kind == saving.LOCKED
        assert target.read_bytes() == before
        save_to(doc, target)  # the other program closed it: now it works
    assert highlights(target) == 1


def test_a_file_let_go_in_a_moment_is_saved_at_the_next_try(copy_of, monkeypatch):
    target = copy_of()
    real = os.replace
    calls = []

    def busy_once(source, destination):
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError(13, "in use")
        return real(source, destination)

    monkeypatch.setattr(saving.os, "replace", busy_once)
    with pymupdf.open(stream=target.read_bytes(), filetype="pdf") as doc:
        highlight_first_word(doc)
        temp = write_copy(doc, target)
        put_in_place(temp, target, pause=0.01)
    assert len(calls) == 2 and highlights(target) == 1


def test_a_full_disk_is_told_apart(copy_of, monkeypatch):
    target = copy_of()
    before = target.read_bytes()

    def full(source, destination):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(saving.os, "replace", full)
    with pymupdf.open(stream=before, filetype="pdf") as doc, pytest.raises(SaveError) as failure:
        save_to(doc, target)
    assert failure.value.kind == saving.NO_SPACE
    assert target.read_bytes() == before


def test_a_folder_that_does_not_exist_fails_cleanly(copy_of, tmp_path):
    source = copy_of()
    with pymupdf.open(source) as doc, pytest.raises(SaveError):
        save_to(doc, tmp_path / "no-existe" / "copia.pdf")


KILLED_SAVER = """
import sys
import pymupdf
from app.core.saving import save_to

target = sys.argv[1]
data = open(target, "rb").read()
print("ready", flush=True)
while True:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc[0]
        page.add_highlight_annot(pymupdf.Rect(50, 50, 200, 70))
        save_to(doc, target)
        data = open(target, "rb").read()
"""


@pytest.mark.parametrize("wait", [0.0, 0.03, 0.08, 0.15, 0.25, 0.4])
def test_killing_the_program_while_it_saves_never_corrupts_the_file(copy_of, tmp_path, wait):
    """Obligatory (CLAUDE.md, section 5.9): a forced close in the middle of saving."""
    target = copy_of("largo.pdf")
    with pymupdf.open(target) as doc:
        pages = doc.page_count
    script = tmp_path / "saver.py"
    script.write_text(KILLED_SAVER, encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root))
    saver = subprocess.Popen(
        [sys.executable, str(script), str(target)], stdout=subprocess.PIPE, env=env, cwd=root
    )
    try:
        assert saver.stdout.readline().strip() == b"ready"
        time.sleep(wait)
    finally:
        saver.kill()
        saver.wait(30)
    with pymupdf.open(target) as doc:  # opens, whole, whatever the moment
        assert doc.page_count == pages
        assert not doc.is_repaired
        assert len(doc[pages - 1].get_text("words")) > 0
