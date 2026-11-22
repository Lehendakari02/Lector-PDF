import pymupdf
import pytest

from app.core import arrange, my_signature
from app.core.commands import CommandError, Together, command_from_dict, new_name
from app.core.drawing import PICTURE, page_drawings
from app.core.notes import SANS, new_text_box, page_notes
from app.core.pictures import AddPicture, fitted


@pytest.fixture
def signature() -> bytes:
    """A signature in blue with a red tick at its left end."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1200, 800), 0)
    pix.clear_with(215)
    pix.set_rect(pymupdf.IRect(300, 400, 900, 430), (20, 30, 120))
    pix.set_rect(pymupdf.IRect(300, 400, 330, 438), (200, 0, 0))
    return my_signature.clean(pix.tobytes("png"))


def blank(rotation: int = 0):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.set_rotation(rotation)
    return doc


def test_the_place_keeps_the_shape_of_the_picture(signature):
    x0, y0, x1, y1 = fitted(signature, 200, 300, 140)
    assert (x1 - x0, round(y1 - y0, 2)) == (140, round(140 * 46 / 608, 2))
    assert ((x0 + x1) / 2, (y0 + y1) / 2) == (200, 300)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_signature_is_put_upright_read_back_and_taken_away(signature, rotation):
    doc = blank(rotation)
    rect = fitted(signature, 200, 300, 140)
    order = AddPicture(0, rect, signature, new_name(), "Firma")
    order.apply(doc)
    order.apply(doc)  # twice is once
    page = doc[0]
    assert len(list(page.annots())) == 1
    shown = page.get_pixmap(dpi=72)
    assert shown.pixel(int(rect[0]) + 2, int(rect[1]) + 2)[0] > 150, "the red end is on the left"
    assert shown.pixel(int(rect[2]) - 3, int(rect[1]) + 3)[2] > 100, "the blue line goes right"
    assert min(shown.pixel(int(rect[0]) + 20, int(rect[3]) - 1)) >= 245, "see-through"

    (found,) = page_drawings(doc, 0)
    assert found.kind == PICTURE and found.ours and found.description == "Firma"
    assert all(abs(a - b) < 0.6 for a, b in zip(found.rect, rect, strict=True))
    again = found.order()
    assert isinstance(again, AddPicture) and again.name == order.name
    assert pymupdf.Pixmap(again.png).width == 608

    order.undo(doc)
    assert not list(doc[0].annots())


def test_it_is_written_down_and_read_back(signature):
    order = AddPicture(2, (1.0, 2.0, 3.0, 4.0), signature, new_name(), "Iniciales")
    assert command_from_dict(order.to_dict()) == order


def test_a_signature_survives_saving(signature, tmp_path):
    doc = blank()
    AddPicture(0, fitted(signature, 300, 400, 140), signature, new_name(), "Firma").apply(doc)
    doc.save(tmp_path / "firmado.pdf", garbage=1, deflate=True)
    again = pymupdf.open(tmp_path / "firmado.pdf")
    (found,) = page_drawings(again, 0)
    assert found.kind == PICTURE
    assert (tmp_path / "firmado.pdf").stat().st_size < 60_000


def test_it_moves_and_grows_keeping_its_shape(signature):
    order = AddPicture(0, (100.0, 100.0, 240.0, 110.0), signature, new_name(), "Firma")
    assert arrange.can_move(order) and arrange.can_resize(order)
    moved = arrange.moved(order, 50, 20, (595, 842)).new
    assert moved.rect == (150.0, 120.0, 290.0, 130.0)
    edge = arrange.moved(order, 1000, 0, (595, 842)).new
    assert edge.rect[2] == 595
    bigger = arrange.resized(order, arrange.BOTTOM_RIGHT, (380.0, 115.0), (595, 842)).new
    x0, y0, x1, y1 = bigger.rect
    assert (x0, y0) == (100.0, 100.0) and x1 == pytest.approx(380.0)
    assert (y1 - y0) / (x1 - x0) == pytest.approx(10 / 140)
    copy = arrange.copy_of(order, 0, (595, 842))
    assert copy.name != order.name and copy.png == order.png


def test_together_puts_all_or_nothing(signature):
    doc = blank()
    picture = AddPicture(0, (100.0, 100.0, 240.0, 110.0), signature, new_name(), "Firma")
    date = new_text_box(0, (100.0, 112.0), "22/11/2026", SANS, 10.0, (0.1, 0.1, 0.1), 0.0, False)
    both = Together((picture, date))
    assert command_from_dict(both.to_dict()) == both
    assert both.apply(doc) == [0]
    assert [note.text for note in page_notes(doc, 0)] == ["22/11/2026"]
    assert len(page_drawings(doc, 0)) == 1
    both.undo(doc)
    assert not list(doc[0].annots())

    broken = Together((picture, AddPicture(5, (0, 0, 1, 1), signature, new_name())))
    with pytest.raises(CommandError):
        broken.apply(doc)
    assert not list(doc[0].annots()), "the signature put first went away again"


def test_one_picture_on_many_pages_is_kept_once(signature):
    # Review of Phase 3, B1: the journal had the picture once for each page.
    import json

    from app.core.commands import command_from_dict
    from app.core.pictures import AddPictures, puts_picture

    doc = pymupdf.open()
    for _ in range(100):
        doc.new_page()
    order = AddPictures(
        signature,
        tuple((page, (450.0, 780.0, 498.0, 800.0), f"lectorpdf-i{page}") for page in range(100)),
        "Iniciales",
    )
    written = json.dumps(order.to_dict())
    assert len(written) < 2 * len(signature) + 20_000
    assert command_from_dict(json.loads(written)) == order
    assert puts_picture(order)
    order.apply(doc)
    order.apply(doc)  # again, as when recovering: not twice
    assert all(len(list(page.annots())) == 1 for page in doc)
    order.undo(doc)
    assert not any(list(page.annots()) for page in doc)
