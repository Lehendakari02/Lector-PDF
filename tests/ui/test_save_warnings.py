"""Tests for the warnings that always come up before saving."""

import os
import shutil

import pymupdf
import pytest

from app.core.save_checks import stamp_of
from app.ui.main_window import SAVE_AS, SAVE_HERE
from app.ui.unsaved_dialog import CANCEL, SAVE


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    def open_copy(name: str = "texto-partido.pdf"):
        window.show_problem_dialogs = False
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        return path

    return open_copy


def asked(window) -> list:
    """Note every warning shown before saving; answered with ``save_warning_answer``."""
    noted = []
    ask = window._ask_save_warning

    def noting(page, reason):
        noted.append(reason)
        return ask(page, reason)

    window._ask_save_warning = noting
    return noted


def touch_from_outside(path) -> None:
    """Another program writes the file."""
    known = stamp_of(path)
    later = known.modified + 3_000_000_000
    os.utime(path, ns=(later, later))


def save_and_wait(window, wait_until) -> bool:
    started = window.save_document()
    wait_until(lambda: not window.pdf_view.saving)
    return started


def test_an_ordinary_document_is_saved_without_questions(window, opened, wait_until):
    opened()
    questions = asked(window)
    window.pdf_view.mark_modified()
    assert save_and_wait(window, wait_until)
    assert questions == [] and not window.pdf_view.modified


# ---- a signed PDF -----------------------------------------------------------


def test_a_signed_pdf_is_never_saved_without_asking(window, opened, wait_until):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    questions = asked(window)
    window.pdf_view.mark_modified()
    assert window.save_document() is False, "nobody to ask: not saved"
    assert questions == ["signed"]
    assert path.read_bytes() == before and window.pdf_view.modified
    assert "firmado" in window.statusBar().currentMessage()


def test_cancel_leaves_the_signed_pdf_alone(window, opened):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    window.save_warning_answer = CANCEL
    window.pdf_view.mark_modified()
    assert window.save_document() is False
    assert path.read_bytes() == before


def test_save_here_anyway_saves_and_does_not_ask_again(window, opened, wait_until):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    questions = asked(window)
    window.save_warning_answer = SAVE_HERE
    window.pdf_view.mark_modified()
    assert save_and_wait(window, wait_until)
    assert path.read_bytes() != before
    window.pdf_view.mark_modified()
    assert save_and_wait(window, wait_until)
    assert questions == ["signed"], "asked once for this document"


def test_save_as_keeps_the_signed_original(window, opened, wait_until, tmp_path, monkeypatch):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    copy = tmp_path / "contrato - copia.pdf"
    monkeypatch.setattr(
        "app.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (str(copy), "")
    )
    window.save_warning_answer = SAVE_AS
    window.pdf_view.mark_modified()
    assert save_and_wait(window, wait_until)
    assert path.read_bytes() == before, "the signed one is as it was"
    assert copy.exists() and window.current_document.path == copy
    assert not window.pdf_view.modified


def test_save_as_cancelled_saves_nothing(window, opened, monkeypatch):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    monkeypatch.setattr("app.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: ("", ""))
    window.save_warning_answer = SAVE_AS
    window.pdf_view.mark_modified()
    assert window.save_document() is False
    assert path.read_bytes() == before and window.pdf_view.modified


def test_closing_and_choosing_save_does_not_save_a_signed_pdf_by_itself(window, opened):
    path = opened("firmado.pdf")
    before = path.read_bytes()
    window.pdf_view.mark_modified()
    window.unsaved_answer = SAVE
    window.save_warning_answer = CANCEL
    window.close_document()
    assert len(window.documents) == 1, "the tab stays, with its changes"
    assert path.read_bytes() == before and not window._saving_to_close
    window.close()
    assert window.isVisible(), "and the program does not close either"


# ---- changed by another program ---------------------------------------------


def test_a_file_changed_by_another_program_is_noticed(window, opened, wait_until):
    path = opened()
    touch_from_outside(path)
    questions = asked(window)
    window.save_warning_answer = CANCEL
    window.pdf_view.mark_modified()
    assert window.save_document() is False
    assert questions == ["changed_outside"]


def test_saving_here_anyway_keeps_what_the_other_program_left(window, opened, wait_until):
    path = opened()
    with pymupdf.open(path) as doc:  # the other program adds a page and saves
        doc.new_page()
        doc.saveIncr()
    theirs = path.read_bytes()
    window.save_warning_answer = SAVE_HERE
    window.pdf_view.mark_modified()
    assert save_and_wait(window, wait_until)
    (version,) = window.versions.of(path)
    assert version.file.read_bytes() == theirs, "it is in Versiones anteriores"


def test_our_own_saves_are_not_taken_for_another_program(window, opened, wait_until):
    opened()
    questions = asked(window)
    for _ in range(3):
        window.pdf_view.mark_modified()
        assert save_and_wait(window, wait_until)
    assert questions == []


def test_a_second_change_from_outside_is_asked_again(window, opened, wait_until):
    path = opened()
    questions = asked(window)
    window.save_warning_answer = SAVE_HERE
    for _ in range(2):
        touch_from_outside(path)
        window.pdf_view.mark_modified()
        assert save_and_wait(window, wait_until)
    assert questions == ["changed_outside", "changed_outside"]


def test_the_gravest_reason_is_asked_first(window, opened):
    path = opened("firmado.pdf")
    touch_from_outside(path)
    questions = asked(window)
    window.save_warning_answer = CANCEL
    window.pdf_view.mark_modified()
    window.save_document()
    assert questions == ["changed_outside"]


# ---- a temporary folder -----------------------------------------------------


def test_a_document_in_a_temporary_folder_asks_where_to_save(
    window, opened, wait_until, tmp_path, monkeypatch
):
    path = opened()
    window.warn_about_temporary_folders = True
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))  # its folder is the temporary one
    questions = asked(window)
    window.save_warning_answer = CANCEL
    window.pdf_view.mark_modified()
    assert window.save_document() is False
    assert questions == ["temporary"]
    window.save_warning_answer = SAVE_HERE
    assert save_and_wait(window, wait_until)
    assert not window.pdf_view.modified and path.exists()


def test_save_as_never_asks(window, opened, wait_until, tmp_path):
    opened("firmado.pdf")
    questions = asked(window)
    window.pdf_view.mark_modified()
    assert window.save_document_as(tmp_path / "copia.pdf")
    wait_until(lambda: not window.pdf_view.saving)
    assert questions == []
    window.pdf_view.mark_modified()
    assert save_and_wait(window, wait_until)
    assert questions == [], "the copy is the user's working file; the original stays signed"
