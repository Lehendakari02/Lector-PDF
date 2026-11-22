import pymupdf
import pytest

from app.core import my_signature
from app.core.my_signature import INITIALS, SIGNATURE, SignatureError


def photo(paper=205, ink=(30, 40, 140), size=(3000, 2000), kind="jpg") -> bytes:
    """A photo of a signature on paper: two strokes on a greyish page."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, *size), 0)
    pix.clear_with(paper)
    pix.set_rect(pymupdf.IRect(1000, 900, 1800, 960), ink)
    pix.set_rect(pymupdf.IRect(1200, 700, 1260, 1100), ink)
    return pix.tobytes(kind)


def test_a_photo_loses_its_paper_and_is_cut_to_the_ink():
    clean = pymupdf.Pixmap(my_signature.clean(photo()))
    assert clean.alpha
    assert (clean.width, clean.height) == (800 + 8, 400 + 8)
    assert clean.pixel(0, 0)[3] == 0, "the paper is see-through"
    red, green, blue, alpha = clean.pixel(230, 230)
    assert alpha == 255 and blue > 120 and red < 50, "the ink keeps its colour"


def test_paper_of_any_light_shade_goes():
    for paper in (170, 235, 255):
        clean = pymupdf.Pixmap(my_signature.clean(photo(paper=paper, kind="png")))
        assert clean.pixel(2, 2)[3] == 0, paper
        assert clean.pixel(230, 230)[3] == 255, paper


def test_a_large_picture_is_made_smaller():
    clean = pymupdf.Pixmap(my_signature.clean(photo(size=(7000, 2000))))
    assert max(clean.width, clean.height) <= my_signature.LONGEST_SIDE


def test_a_picture_already_see_through_keeps_its_own_background():
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 100), 1)
    pix.set_rect(pix.irect, (0, 0, 0, 0))
    pix.set_rect(pymupdf.IRect(50, 40, 250, 60), (10, 10, 10, 255))
    clean = pymupdf.Pixmap(my_signature.clean(pix.tobytes("png")))
    assert (clean.width, clean.height) == (208, 28)


def test_keeping_the_background_cuts_nothing_off():
    clean = pymupdf.Pixmap(my_signature.clean(photo(kind="png"), remove_background=False))
    assert (clean.width, clean.height) == (1500, 1000)  # made smaller, nothing cut
    assert clean.pixel(0, 0)[3] == 255


@pytest.mark.parametrize("data", [b"", b"not a picture at all"])
def test_what_is_not_a_picture_is_refused(data):
    with pytest.raises(SignatureError):
        my_signature.clean(data)


def test_a_blank_page_has_no_signature():
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), 0)
    pix.clear_with(250)
    with pytest.raises(SignatureError):
        my_signature.clean(pix.tobytes("png"))


def test_saved_loaded_and_forgotten(tmp_path):
    folder = tmp_path / "firma"
    assert my_signature.load(folder, SIGNATURE) is None
    png = my_signature.clean(photo())
    my_signature.save(folder, SIGNATURE, png)
    assert my_signature.load(folder, SIGNATURE) == png
    assert my_signature.load(folder, INITIALS) is None
    assert not list(folder.glob("*.tmp"))
    assert my_signature.size_of(png) == (808, 408)
    my_signature.forget(folder, SIGNATURE)
    my_signature.forget(folder, SIGNATURE)  # twice is fine
    assert my_signature.load(folder, SIGNATURE) is None
    with pytest.raises(ValueError):
        my_signature.picture_path(folder, "otra")
