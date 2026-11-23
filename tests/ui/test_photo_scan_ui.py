"""Tests for «De foto a PDF» in the window."""

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core import photo_scan
from app.ui.main_window import Mode
from app.ui.photo_scan_dialog import LOOK_SETTING, PhotoScanDialog


@pytest.fixture
def photos(tmp_path, photo_of_paper):
    return [
        photo_of_paper(tmp_path / "foto 1.jpg"),
        photo_of_paper(tmp_path / "foto 2.jpg", shadow=False),
    ]


@pytest.fixture
def dialog(qt_app, photos):
    shown = PhotoScanDialog(None, photos, photo_scan.DOCUMENT)
    shown.resize(1100, 700)
    shown.show()
    qt_app.processEvents()
    yield shown
    shown.close()
    shown.deleteLater()


def test_each_photo_is_listed_with_its_sheet_found(dialog, photo_of_paper):
    assert dialog.list.count() == 2
    first = dialog.photos[0]
    width, height = 1199, 999  # the made-up photo is 1200 × 1000
    for found, real in zip(first.corners, photo_of_paper.sheet, strict=True):
        assert found[0] * width == pytest.approx(real[0], abs=15)
        assert found[1] * height == pytest.approx(real[1], abs=15)
    assert dialog.result.pixmap() is not None and not dialog.result.pixmap().isNull()
    assert dialog.create_button.isEnabled()


def test_dragging_a_corner_moves_it(dialog, qt_app):
    editor = dialog.editor
    start = editor.corner_on_screen(0).toPoint()
    end = start + QPoint(-20, -15)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(editor, end)
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    moved = editor.corner_on_screen(0).toPoint()
    assert (moved - end).manhattanLength() <= 2
    assert dialog.photos[0].corners[0] == editor.corners[0], "the photo keeps the new corner"


def test_the_arrows_move_the_chosen_corner(dialog):
    editor = dialog.editor
    editor.setFocus()
    before = editor.corners[2]
    QTest.keyClick(editor, Qt.Key.Key_3)
    QTest.keyClick(editor, Qt.Key.Key_Right)
    QTest.keyClick(editor, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    after = editor.corners[2]
    assert after[0] > before[0] and after[1] > before[1]
    assert after[1] - before[1] > after[0] - before[0], "with Mayús it moves further"


def test_a_corner_cannot_fold_the_sheet(dialog):
    editor = dialog.editor
    before = list(editor.corners)
    assert not editor.move_corner(0, (1.0, 1.0)), "past the opposite corner"
    assert editor.corners == before


def test_turning_whole_photo_and_finding_again(dialog):
    dialog.turn(1)
    assert dialog.photos[0].turns == 1
    dialog.turn(-1)
    dialog.turn(-1)
    assert dialog.photos[0].turns == 3
    found = dialog.photos[0].corners
    dialog.use_whole()
    assert dialog.photos[0].corners == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    dialog.find_again()
    assert dialog.photos[0].corners == found


def test_removing_a_photo(dialog):
    dialog.list.setCurrentRow(0)
    dialog.remove_current()
    assert [photo.path.name for photo in dialog.photos] == ["foto 2.jpg"]
    dialog.remove_current()
    assert not dialog.create_button.isEnabled()


def test_what_is_not_a_photo_is_left_out(qt_app, photos, tmp_path):
    wrong = tmp_path / "nota.png"
    wrong.write_text("no soy una foto")
    shown = PhotoScanDialog(None, [photos[0], wrong], photo_scan.GRAY)
    assert shown.problems == ["nota.png"]
    assert len(shown.photos) == 1
    assert shown.look == photo_scan.GRAY
    shown.deleteLater()


def test_de_foto_a_pdf_makes_and_opens_the_pdf(window, photos, tmp_path, wait_until):
    window.show_problem_dialogs = False
    target = tmp_path / "escaneado.pdf"
    suggested = []

    def answer(dialog):
        dialog.look_box.setCurrentIndex(dialog.look_box.findData(photo_scan.BLACK_WHITE))
        dialog.list.setCurrentRow(1)
        dialog.turn(1)
        return True

    window.photo_files_answer = photos
    window.photo_scan_answer = answer
    window.organize_target_answer = lambda proposal: suggested.append(proposal) or target
    window.set_mode(Mode.ORGANIZE)
    window.feature_actions["photo_to_pdf"].trigger()
    assert suggested[0].name == "Escaneado.pdf"
    assert suggested[0].parent == tmp_path, "beside the photos"
    wait_until(lambda: window.current_document.path == target)
    with pymupdf.open(target) as doc:
        assert doc.page_count == 2
        assert doc[1].rect.width > doc[1].rect.height, "the second page was turned"
    assert window.settings.get(LOOK_SETTING) == photo_scan.BLACK_WHITE, "remembered"
    assert "2 páginas" in window.statusBar().currentMessage()


def test_cancelling_makes_nothing(window, photos, tmp_path):
    window.photo_files_answer = photos
    window.photo_scan_answer = lambda dialog: False
    window.organize_target_answer = lambda proposal: pytest.fail("no file is asked for")
    assert not window.photo_to_pdf()
    assert not list(tmp_path.glob("*.pdf"))
