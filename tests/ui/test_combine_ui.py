"""Tests for Unir, Dividir and Extraer páginas in the window."""

import shutil

import pymupdf
import pytest

from app.core import combine
from app.core.combine import RANGES
from app.core.document import PdfDocument
from app.ui.main_window import Mode
from app.ui.organize_dialogs import MergeDialog, SplitDialog
from app.ui.side_panel import Tab


@pytest.fixture
def opened(window, sample, tmp_path, wait_until):
    window.show_problem_dialogs = False

    def open_it(name="boe.pdf"):
        path = tmp_path / name
        shutil.copy(sample(name), path)
        assert window.open_document(path)
        view = window.pdf_view
        wait_until(lambda: 0 in view.cached_pages())
        return view, path

    return open_it


def settle(view, wait_until) -> None:
    wait_until(lambda: not view._changing and not view.saving)


def count_of(path) -> int:
    with pymupdf.open(path) as doc:
        return doc.page_count


def first_text(path) -> str:
    with pymupdf.open(path) as doc:
        return doc[0].get_text()[:120]


def test_unir_joins_and_opens_the_result(window, opened, sample, tmp_path, wait_until):
    view, boe = opened()
    other = tmp_path / "partido.pdf"
    shutil.copy(sample("texto-partido.pdf"), other)
    window.merge_answer = [boe, other]
    asked = []
    window.organize_target_answer = lambda suggested: asked.append(suggested) or suggested
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["merge"].trigger()
    assert asked == [tmp_path / "Unido.pdf"]
    target = tmp_path / "Unido.pdf"
    assert count_of(target) == count_of(boe) + count_of(other)
    assert window.current_document.path == target
    assert "2 documentos unidos" in window.statusBar().currentMessage()
    with pymupdf.open(target) as doc:
        tops = [title for level, title, _page in doc.get_toc() if level == 1]
    assert tops == ["boe", "partido"]


def test_unir_asks_the_password_of_a_locked_document(window, opened, sample, tmp_path):
    _view, boe = opened()
    locked = tmp_path / "cerrado.pdf"
    shutil.copy(sample("con-contrasena.pdf"), locked)
    window.merge_answer = [locked, boe]
    window.organize_target_answer = lambda suggested: str(tmp_path / "juntos")
    window.ask_password = lambda path: PdfDocument(path, "lector")
    assert window.merge_documents()
    with pymupdf.open(locked) as doc:
        doc.authenticate("lector")
        locked_pages = doc.page_count
    assert count_of(tmp_path / "juntos.pdf") == count_of(boe) + locked_pages
    window.ask_password = lambda path: None
    window.merge_answer = [locked, boe]
    window.organize_target_answer = lambda suggested: str(tmp_path / "otra")
    assert not window.merge_documents()
    assert not (tmp_path / "otra.pdf").exists()


def test_the_merge_dialog_orders_the_documents(qt_app, tmp_path):
    a, b, c = (tmp_path / name for name in ("a.pdf", "b.pdf", "c.pdf"))
    dialog = MergeDialog(None, [(a, False), (b, True)], [c])
    assert dialog.paths == [c]
    assert not dialog.merge_button.isEnabled()
    dialog.add_open()
    assert dialog.paths == [c, a, b]
    assert dialog.merge_button.text() == "Unir 3 documentos"
    assert "sin guardar" in dialog.note.text()
    dialog.list.item(0).setSelected(True)
    dialog.move_selected(1)
    assert dialog.paths == [a, c, b]
    dialog.remove_selected()
    assert dialog.paths == [a, b]
    dialog.deleteLater()


def test_dividir_by_the_outline(window, opened, tmp_path, wait_until):
    view, boe = opened()
    captured = {}

    def answer_from_dialog():
        dialog = SplitDialog(
            window, boe.name, view.page_count, tmp_path / "partes", captured["sections"]
        )
        return dialog.parts, dialog.titles, dialog.folder

    captured["sections"] = combine.outline_parts(boe)
    assert len(captured["sections"]) >= 2
    (tmp_path / "partes").mkdir()
    window.split_answer = answer_from_dialog()
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["split"].trigger()
    made = sorted((tmp_path / "partes").iterdir())
    assert len(made) == len(captured["sections"])
    assert sum(count_of(path) for path in made) == view.page_count
    assert "Dividido en" in window.statusBar().currentMessage()


def test_the_split_dialog_says_what_will_come_out(qt_app, tmp_path):
    dialog = SplitDialog(None, "doc.pdf", 10, tmp_path)
    assert not dialog.outline_button.isEnabled()
    dialog.size_box.setValue(4)
    assert dialog.parts == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]
    assert "3 documentos" in dialog.note.text()
    dialog.ranges_edit.setText("1-3, x")
    dialog.ranges_edit.textEdited.emit("1-3, x")
    assert dialog.chosen_way == RANGES
    assert not dialog.split_button.isEnabled()
    assert "No entiendo" in dialog.note.text()
    dialog.ranges_edit.setText("1-3, 4-")
    dialog.ranges_edit.textEdited.emit("1-3, 4-")
    assert dialog.parts == [[0, 1, 2], list(range(3, 10))]
    assert dialog.split_button.isEnabled()
    dialog.size_box.setValue(10)
    assert not dialog.split_button.isEnabled(), "one part equal to the whole"
    dialog.deleteLater()


def test_extraer_paginas_from_the_miniatures(window, opened, tmp_path, wait_until):
    view, boe = opened()
    window.show_side_panel(Tab.THUMBNAILS)
    window.side_panel.thumbnails.pick_pages([1, 2])
    asked = []
    window.organize_target_answer = lambda suggested: asked.append(suggested) or suggested
    window.side_panel.thumbnails.extract_wanted.emit([1, 2])
    assert asked == [tmp_path / "boe - páginas 2-3.pdf"]
    assert count_of(asked[0]) == 2
    with pymupdf.open(boe) as doc:
        assert first_text(asked[0]) == doc[1].get_text()[:120]
    assert window.current_document.path == asked[0]


def test_changes_not_saved_are_saved_first(window, opened, tmp_path, wait_until):
    view, boe = opened()
    assert view.rotate_pages([0], 90)
    settle(view, wait_until)
    window.organize_target_answer = lambda suggested: str(tmp_path / "primera.pdf")
    window.save_first_answer = False
    assert not window.extract_pages([0])
    assert not (tmp_path / "primera.pdf").exists()
    window.save_first_answer = True
    assert not window.extract_pages([0]), "it goes on once saved"
    wait_until(lambda: (tmp_path / "primera.pdf").exists())
    with pymupdf.open(tmp_path / "primera.pdf") as doc:
        assert doc[0].rotation == 90
