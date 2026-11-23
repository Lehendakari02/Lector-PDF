"""Tests for «Exportar» in the window: pages as pictures, the text as a file."""

import shutil

import pymupdf
import pytest

from app.core.export import JPEG
from app.ui.main_window import EXPORT_SETTING, Mode
from app.ui.organize_dialogs import TEXT, ExportDialog
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


def test_the_page_being_read_as_a_png(window, opened, tmp_path):
    view, path = opened()
    asked = []
    window.export_answer = lambda dialog: True
    window.export_target_answer = lambda proposal: asked.append(proposal) or proposal
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["export"].trigger()
    assert asked[0] == tmp_path / "boe - página 01.png"
    picture = pymupdf.Pixmap(asked[0])
    assert abs(picture.width - view._sizes[0].width * 150 / 72) <= 1, "at 150 ppp"
    assert "boe - página 01.png" in window.statusBar().currentMessage()


def test_several_pages_go_into_a_folder(window, opened, tmp_path):
    opened()
    folder = tmp_path / "imagenes"
    folder.mkdir()

    def answer(dialog):
        dialog.these_pages.setChecked(True)
        dialog.ranges_edit.setText("2-3, 5")
        dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(JPEG))
        return True

    window.export_answer = answer
    window.export_target_answer = lambda proposal: folder
    assert window.export_pages()
    assert sorted(p.name for p in folder.iterdir()) == [
        "boe - página 02.jpg",
        "boe - página 03.jpg",
        "boe - página 05.jpg",
    ]
    assert window.settings.get(EXPORT_SETTING)["kind"] == JPEG, "remembered for next time"


def test_the_text_of_the_whole_document(window, opened, tmp_path):
    view, _path = opened()

    def answer(dialog):
        dialog.as_text.setChecked(True)
        dialog.all_pages.setChecked(True)
        return True

    window.export_answer = answer
    window.export_target_answer = lambda proposal: proposal
    assert window.export_pages()
    text = (tmp_path / "boe.txt").read_text(encoding="utf-8")
    assert "Constitución Española" in text
    assert text.count("— Página ") == view.page_count


def test_the_pages_picked_in_the_miniatures_are_offered(window, opened):
    view, _path = opened()
    window.show_side_panel(Tab.THUMBNAILS)
    window.side_panel.thumbnails.pick_pages([1, 4])
    seen = []
    window.export_answer = lambda dialog: seen.append(dialog.pages) and False
    window.export_pages()
    assert seen == [[1, 4]]


def test_wrong_pages_are_said(qt_app):
    dialog = ExportDialog(None, 10, 0, [])
    dialog.these_pages.setChecked(True)
    dialog.ranges_edit.setText("3-x")
    dialog.accept()
    assert dialog.result() != ExportDialog.DialogCode.Accepted
    assert "1-3, 7" in dialog.problem.text()
    dialog.ranges_edit.setText("11")
    assert dialog.pages == []
    dialog.deleteLater()


def test_the_choices_of_last_time_come_back(qt_app):
    dialog = ExportDialog(
        None, 5, 2, [], {"what": TEXT, "kind": JPEG, "resolution": 300, "annotations": False}
    )
    assert dialog.what == TEXT
    assert dialog.kind == JPEG and dialog.resolution == 300 and not dialog.annotations
    assert dialog.pages == [2], "the page being read"
    dialog.deleteLater()


def test_changes_not_saved_are_saved_first(window, opened, tmp_path, wait_until):
    view, path = opened()
    assert view.rotate_pages([0], 90)
    settle(view, wait_until)
    window.save_first_answer = True
    window.export_answer = lambda dialog: True
    window.export_target_answer = lambda proposal: proposal
    window.export_pages()
    settle(view, wait_until)
    wait_until(lambda: (tmp_path / "boe - página 01.png").exists())
    picture = pymupdf.Pixmap(tmp_path / "boe - página 01.png")
    assert picture.width > picture.height, "the page turned is exported turned"
