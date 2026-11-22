"""Tests for making and keeping one's signature and initials."""

import datetime
import shutil
from pathlib import Path

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core import arrange, my_data, my_signature
from app.core.drawing import PICTURE
from app.core.my_signature import INITIALS, SIGNATURE
from app.ui.pdf_view import SIGN_TOOL
from app.ui.signature_dialog import SignatureDialog
from tests.ui.test_forms_ui import place

LEFT = Qt.MouseButton.LeftButton
NO_KEYS = Qt.KeyboardModifier.NoModifier


def photo(tmp_path, paper=210):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1200, 800), 0)
    pix.clear_with(paper)
    pix.set_rect(pymupdf.IRect(300, 400, 900, 430), (20, 30, 120))
    path = tmp_path / "foto.jpg"
    pix.save(path)
    return str(path)


def picture(png: bytes):
    pix = pymupdf.Pixmap(png)
    assert pix.alpha
    return pix


def test_a_signature_drawn_is_kept_cut_to_the_ink(qt_app):
    dialog = SignatureDialog(SIGNATURE)
    dialog.resize(600, 400)
    dialog.show()
    pad = dialog.pad
    assert dialog.tabs.currentIndex() == dialog.DRAW
    assert not dialog.save_button.isEnabled(), "nothing to keep yet"
    QTest.mousePress(pad, LEFT, NO_KEYS, QPoint(60, 60))
    for x in range(70, 300, 10):
        QTest.mouseMove(pad, QPoint(x, 60 + (x % 40)))
    QTest.mouseRelease(pad, LEFT, NO_KEYS, QPoint(300, 80))
    assert dialog.save_button.isEnabled()
    dialog.accept()
    pix = picture(dialog.png)
    assert pix.width < pad.width() * 3 and pix.height < 80 * 3, "cut to what was drawn"
    assert pix.pixel(0, 0)[3] == 0
    pad.undo_stroke()
    assert pad.empty


def test_a_signature_written_in_blue(qt_app):
    dialog = SignatureDialog(SIGNATURE, "Ane Etxeberria")
    dialog.tabs.setCurrentIndex(dialog.WRITE)
    assert dialog.words.text() == "Ane Etxeberria" and dialog.save_button.isEnabled()
    dialog.set_ink("blue")
    assert not dialog.written_preview.pixmap().isNull()
    dialog.accept()
    pix = picture(dialog.png)
    inked = [
        pix.pixel(x, y)
        for x in range(0, pix.width, 4)
        for y in range(0, pix.height, 4)
        if pix.pixel(x, y)[3] == 255
    ]
    assert inked and all(blue > red for red, _green, blue, _alpha in inked)
    dialog.words.clear()
    assert not dialog.save_button.isEnabled()


def test_a_signature_from_a_photo_loses_its_paper(qt_app, tmp_path):
    dialog = SignatureDialog(SIGNATURE)
    dialog.tabs.setCurrentIndex(dialog.PICTURE)
    assert not dialog.save_button.isEnabled()
    dialog.image_answer = photo(tmp_path)
    assert dialog.choose_picture()
    assert dialog.save_button.isEnabled()
    dialog.accept()
    pix = picture(dialog.png)
    assert (pix.width, pix.height) == (608, 38)
    assert pix.pixel(1, 1)[3] == 0


def test_a_photo_with_no_signature_is_explained(qt_app, tmp_path):
    dialog = SignatureDialog(INITIALS)
    dialog.tabs.setCurrentIndex(dialog.PICTURE)
    blank = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 200), 0)
    blank.clear_with(240)
    blank.save(tmp_path / "blanca.png")
    dialog.image_answer = str(tmp_path / "blanca.png")
    assert not dialog.choose_picture()
    assert "No se ve ninguna firma" in dialog.picture_preview.text()
    assert not dialog.save_button.isEnabled()


def test_firmar_makes_the_signature_the_first_time_then_offers_it(window, tmp_path):
    window.settings.set(my_data.SETTING, {"name": "Ane", "surnames": "Etxeberria Goñi"})
    assert window._suggested_words(SIGNATURE) == "Ane Etxeberria Goñi"
    assert window._suggested_words(INITIALS) == "A. E. G."
    png = my_signature.clean(Path(photo(tmp_path)).read_bytes())
    window.signature_answer = png
    assert window.show_signature() is None, "the first time it is made"
    assert window.saved_signature(SIGNATURE) == png
    assert (window.signature_folder / "firma.png").is_file()
    assert window.signature_folder.parent == window.settings.path.parent

    menu = window.show_signature()
    names = [action.text() for action in menu.actions() if action.text()]
    assert names == [
        "Poner mi firma",
        "Poner la fecha de hoy debajo de la firma",
        "Cambiar mi firma…",
        "Quitar mi firma",
        "Crear mis iniciales…",
    ]
    assert not menu.actions()[0].isEnabled(), "no document open to sign"
    menu.close()
    menu.actions()[-1].trigger()  # make the initials
    assert window.saved_signature(INITIALS) == png
    menu = window.show_signature()
    assert [a.text() for a in menu.actions()][:2] == ["Poner mi firma", "Poner mis iniciales"]
    menu.close()

    window.forget_signature_answer = False
    assert not window.forget_signature(SIGNATURE)
    assert window.saved_signature(SIGNATURE) == png
    window.forget_signature_answer = True
    assert window.forget_signature(SIGNATURE)
    assert window.saved_signature(SIGNATURE) is None
    assert window.saved_signature(INITIALS) == png


def test_the_signature_is_found_with_the_function_finder(window):
    assert "my_signature" in window.feature_actions
    window.signature_answer = b""  # cancelled
    window.feature_actions["my_signature"].trigger()
    assert window.saved_signature(SIGNATURE) is None


def test_a_click_signs_with_the_date_under_and_saving_proposes_a_copy(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    path = tmp_path / "contrato.pdf"
    shutil.copy(sample("formulario.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    png = my_signature.clean(Path(photo(tmp_path)).read_bytes())
    window.signature_answer = png
    assert window.show_signature() is None, "made, and then in hand"
    assert view.markup_tool == SIGN_TOOL and window.feature_actions["sign_drawn"].isChecked()
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 300, 600))
    wait_until(lambda: any(item.kind == PICTURE for item in view.drawings_of(0)))
    wait_until(lambda: view.notes_of(0))
    assert view.markup_tool == "", "one signature per click on Firmar"
    (signed,) = [item for item in view.drawings_of(0) if item.kind == PICTURE]
    x0, y0, x1, y1 = signed.rect
    assert abs((x0 + x1) / 2 - 300) < 1 and abs((y0 + y1) / 2 - 600) < 1
    assert x1 - x0 == pytest.approx(140, abs=1)
    (date,) = view.notes_of(0)
    assert date.text == datetime.date.today().strftime("%d/%m/%Y") and date.rect[1] > y1

    view.undo()
    wait_until(lambda: not view.drawings_of(0) and not view.notes_of(0))
    view.redo()
    wait_until(lambda: view.drawings_of(0) and view.notes_of(0))

    # It moves and grows like any drawing, keeping its shape.
    spots = [place(view, 0, 300, 600), place(view, 0, 320, 640)]
    QTest.mousePress(view.viewport(), LEFT, NO_KEYS, spots[0])
    QTest.mouseMove(view.viewport(), spots[1])
    QTest.mouseRelease(view.viewport(), LEFT, NO_KEYS, spots[1])
    wait_until(
        lambda: (
            [i.rect[1] for i in view.drawings_of(0)]
            and abs([i for i in view.drawings_of(0) if i.kind == PICTURE][0].rect[1] - (y0 + 40))
            < 1
        )
    )
    (moved,) = [item for item in view.drawings_of(0) if item.kind == PICTURE]
    order = view.picked_item().order() if view.picked_item() else moved.order()
    grown = arrange.resized(order, arrange.BOTTOM_RIGHT, (moved.rect[2] + 70, 0), (595, 842))
    assert grown is not None
    view._do(grown)
    wait_until(
        lambda: (
            [i for i in view.drawings_of(0) if i.kind == PICTURE][0].rect[2] > moved.rect[2] + 60
        )
    )

    window.signed_save_answer = ""  # cancel
    assert not window.save_document()
    asked = []
    window.signed_save_answer = "copy"
    window.save_as_answer = lambda suggested: asked.append(suggested) or str(suggested)
    assert window.save_document()
    wait_until(lambda: not view.saving and not view.modified)
    assert [p.name for p in asked] == ["contrato-firmado.pdf"]
    assert window.current_document.path.name == "contrato-firmado.pdf"
    with pymupdf.open(tmp_path / "contrato-firmado.pdf") as doc:
        assert sorted(a.type[1] for a in doc[0].annots()) == ["FreeText", "Stamp"]
    with pymupdf.open(path) as doc:
        assert not list(doc[0].annots()), "the original stays as it was"


def test_initials_go_without_the_date_and_the_date_can_be_left_out(
    window, sample, tmp_path, wait_until
):
    window.show_problem_dialogs = False
    path = tmp_path / "hoja.pdf"
    shutil.copy(sample("formulario.pdf"), path)
    assert window.open_document(path)
    view = window.pdf_view
    wait_until(lambda: 0 in view.cached_pages() and 0 in view._notes)
    png = my_signature.clean(Path(photo(tmp_path)).read_bytes())
    my_signature.save(window.signature_folder, SIGNATURE, png)
    my_signature.save(window.signature_folder, INITIALS, png)
    assert window.put_signature(INITIALS)
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 500, 800))
    wait_until(lambda: view.drawings_of(0))
    (initials,) = view.drawings_of(0)
    assert initials.rect[2] - initials.rect[0] == pytest.approx(48, abs=1)
    assert initials.description == "Iniciales" and not view.notes_of(0)

    menu = window.show_signature()
    dated = next(a for a in menu.actions() if a.text().startswith("Poner la fecha"))
    dated.toggle()
    menu.close()
    assert window.settings.get("firma/fecha") is False
    assert window.put_signature()
    assert window.show_signature() is None and view.markup_tool == "", "the button leaves it"
    assert window.put_signature()
    QTest.mouseClick(view.viewport(), LEFT, NO_KEYS, place(view, 0, 200, 300))
    wait_until(lambda: len(view.drawings_of(0)) == 2)
    assert not view.notes_of(0)
