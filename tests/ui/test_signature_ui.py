"""Tests for making and keeping one's signature and initials."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core import my_data, my_signature
from app.core.my_signature import INITIALS, SIGNATURE
from app.ui.signature_dialog import SignatureDialog

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
    assert names == ["Cambiar mi firma…", "Quitar mi firma", "Crear mis iniciales…"]
    menu.close()
    menu.actions()[-2].trigger()  # make the initials
    assert window.saved_signature(INITIALS) == png

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
