"""Tests for app.core.notes: sticky notes and text boxes."""

import pymupdf
import pytest

from app.core import notes
from app.core.commands import CommandError, command_from_dict
from app.core.journal import net
from app.core.notes import (
    MONO,
    NOTE,
    SANS,
    SERIF,
    TEXT_BOX,
    AddNote,
    AddTextBox,
    Remove,
    Replace,
    box_layout,
    changed,
    new_note,
    new_text_box,
    note_at,
    page_notes,
    wrap_text,
)

SPANISH = "Repasar: ¿año? ñ á é ü € «art. 14»"


@pytest.fixture
def doc():
    document = pymupdf.open()
    document.new_page(width=400, height=300)
    turned = document.new_page(width=400, height=300)
    turned.set_rotation(90)
    yield document
    document.close()


def saved_again(document) -> pymupdf.Document:
    """The document as another program would find it in the file."""
    return pymupdf.open("pdf", document.tobytes())


def close_to(first, second, by: float = 0.01) -> bool:
    return all(abs(a - b) <= by for a, b in zip(first, second, strict=True))


# ---- notes ---------------------------------------------------------------------


def test_a_note_is_a_standard_annotation_with_its_text(doc):
    order = new_note(0, (300, 40), SPANISH, (0.2, 0.6, 1.0))
    assert order.apply(doc) == [0]
    with saved_again(doc) as other:
        page = other[0]  # kept: an annotation dies with its page
        (annotation,) = page.annots()
        assert annotation.type[1] == "Text"
        assert annotation.info["content"] == SPANISH
        assert annotation.info["id"] == order.name
        assert close_to(annotation.colors["stroke"], (0.2, 0.6, 1.0))
        assert close_to(annotation.rect, (300, 40, 316, 56))


def test_a_note_is_read_back_as_it_was_put(doc):
    order = new_note(0, (300, 40), SPANISH, (0.2, 0.6, 1.0))
    order.apply(doc)
    (found,) = page_notes(doc, 0)
    assert found.kind == NOTE and found.ours and found.text == SPANISH
    assert close_to(found.rect, (300, 40, 316, 56))
    rebuilt = found.order()
    assert isinstance(rebuilt, AddNote) and rebuilt.name == order.name
    assert close_to(rebuilt.point, order.point) and close_to(rebuilt.color, order.color)


@pytest.mark.parametrize("turn", [90, 180, 270])
def test_on_a_turned_page_the_note_is_where_it_was_clicked(doc, turn):
    doc[1].set_rotation(turn)
    new_note(1, (250, 30), "hola").apply(doc)
    (found,) = page_notes(doc, 1)
    assert close_to(found.rect, (250, 30, 266, 46))
    inside = doc[1].rect  # as shown
    assert found.rect[0] >= 0 and found.rect[2] <= inside.width


def test_undoing_takes_the_note_away_and_doing_it_twice_puts_one(doc):
    order = new_note(0, (10, 10), "una")
    order.apply(doc)
    order.apply(doc)
    assert len(page_notes(doc, 0)) == 1
    assert order.undo(doc) == [0]
    assert page_notes(doc, 0) == []
    order.undo(doc)  # nothing to take away: no error


def test_a_page_that_does_not_exist_is_an_error(doc):
    with pytest.raises(CommandError):
        new_note(9, (10, 10), "una").apply(doc)
    with pytest.raises(CommandError):
        new_text_box(9, (10, 10), "una").apply(doc)


# ---- text boxes ------------------------------------------------------------------


@pytest.mark.parametrize(("font", "size"), [(SANS, 12), (SERIF, 20), (MONO, 9)])
def test_a_text_box_is_standard_and_shows_every_line_whole(doc, font, size):
    text = f"Esquema gjpqy ÁÉ\n{SPANISH}\ny tercera"
    order = new_text_box(0, (20, 40), text, font, size, (0.8, 0.0, 0.0))
    order.apply(doc)
    with saved_again(doc) as other:
        page = other[0]  # kept: an annotation dies with its page
        (annotation,) = page.annots()
        assert annotation.type[1] == "FreeText"
        assert annotation.info["content"] == text
        shown = [line.strip() for line in annotation.get_text().splitlines() if line.strip()]
        assert shown == text.split("\n"), "no line is cut or pushed out of the box"
        assert other.xref_get_key(annotation.xref, "CL")[0] == "null"


def test_a_text_box_is_read_back_as_it_was_put(doc):
    order = new_text_box(0, (20, 40), "uno\ndos", SERIF, 18, (0.0, 0.4, 0.8))
    order.apply(doc)
    (found,) = page_notes(doc, 0)
    assert (found.kind, found.font, found.size, found.text) == (TEXT_BOX, SERIF, 18, "uno\ndos")
    assert found.ours and close_to(found.color, (0.0, 0.4, 0.8))
    rebuilt = found.order()
    assert isinstance(rebuilt, AddTextBox)
    assert close_to(rebuilt.origin, (20, 40))
    rebuilt.undo(doc)
    rebuilt.apply(doc)
    (again,) = page_notes(doc, 0)
    assert close_to(again.rect, found.rect), "put again, it takes the same place"


def test_a_long_line_never_leaves_the_page(doc):
    text = "una frase bastante larga que no cabe en lo que queda de página " * 2
    new_text_box(0, (250, 40), text.strip(), SANS, 12).apply(doc)
    (found,) = page_notes(doc, 0)
    assert found.rect[2] <= 400
    assert found.rect[3] - found.rect[1] > 3 * 12 * 1.25, "cut into more than three lines"
    assert found.text == text.strip(), "what was written is kept as it was written"
    assert found.text.replace("\n", " ") == text.strip(), "cut at the spaces, nothing lost"
    with saved_again(doc) as other:
        page = other[0]  # kept: an annotation dies with its page
        (annotation,) = page.annots()
        shown = [line.strip() for line in annotation.get_text().splitlines() if line.strip()]
        assert shown == box_layout(text.strip(), SANS, 12, (250, 40), 400)[0]


def test_on_a_turned_page_the_text_box_reads_upright_where_it_was_put(doc):
    new_text_box(1, (30, 50), "uno\ndos", SANS, 12).apply(doc)
    (found,) = page_notes(doc, 1)
    x0, y0, x1, y1 = found.rect
    assert close_to((x0, y0), (30, 50))
    assert x1 - x0 < 60 and 30 < y1 - y0 < 40, "two lines tall, as wide as a short word"
    page = doc[1]
    (annotation,) = page.annots()
    assert doc.xref_get_key(annotation.xref, "Rotate")[1] == "90"


def test_wrapping_cuts_at_spaces_and_inside_endless_words():
    assert wrap_text("uno dos", SANS, 12, 500) == ["uno dos"]
    assert wrap_text("uno\n\ndos", SANS, 12, 500) == ["uno", "", "dos"]
    lines = wrap_text("palabra " * 12, SANS, 12, 100)
    assert len(lines) > 3
    assert all(notes.text_width(line, SANS, 12) <= 100 for line in lines)
    endless = wrap_text("x" * 200, SANS, 12, 100)
    assert "".join(endless) == "x" * 200 and len(endless) > 5


def test_the_box_is_as_wide_as_its_longest_line():
    lines, (x0, y0, x1, y1) = box_layout("corta\nuna línea más larga", SANS, 12, (10, 20), 600)
    assert lines == ["corta", "una línea más larga"]
    width = notes.text_width("una línea más larga", SANS, 12)
    assert (x0, y0) == (10, 20) and width < x1 - x0 < width * 1.2
    assert 2 * 12 < y1 - y0 < 2 * 12 * 1.5


def test_an_unknown_font_is_an_error(doc):
    with pytest.raises(CommandError):
        AddTextBox(0, (10, 10), "a", "comic", 12, (0, 0, 0), "lectorpdf-x").apply(doc)


# ---- removing and changing ---------------------------------------------------------


def test_removing_and_undoing_the_removal(doc):
    new_note(0, (10, 10), "una").apply(doc)
    (found,) = page_notes(doc, 0)
    order = Remove(found.order())
    assert order.apply(doc) == [0] and page_notes(doc, 0) == []
    assert order.undo(doc) == [0]
    (back,) = page_notes(doc, 0)
    assert back == found


def test_changing_the_text_and_undoing_it(doc):
    new_text_box(0, (20, 40), "antes", SANS, 12).apply(doc)
    (found,) = page_notes(doc, 0)
    order = changed(found, text="después, y más largo", size=16.0, font=MONO)
    order.apply(doc)
    (now,) = page_notes(doc, 0)
    assert (now.text, now.size, now.font, now.name) == (
        "después, y más largo",
        16,
        MONO,
        found.name,
    )
    assert now.rect[2] > found.rect[2], "the box grows with its text"
    order.undo(doc)
    assert page_notes(doc, 0) == [found]


def test_a_change_that_cannot_be_made_leaves_what_there_was(doc):
    new_text_box(0, (20, 40), "antes").apply(doc)
    (found,) = page_notes(doc, 0)
    order = changed(found, font="comic")
    with pytest.raises(CommandError):
        order.apply(doc)
    assert page_notes(doc, 0) == [found]


# ---- written down and read back ----------------------------------------------------


def test_every_order_survives_being_written_down(doc):
    note = new_note(0, (10, 10), SPANISH)
    box = new_text_box(1, (20, 40), "uno\ndos", SERIF, 18, (0.0, 0.4, 0.8))
    for order in (note, box, Remove(note), Replace(box, new_text_box(1, (5, 5), "otro"))):
        assert command_from_dict(order.to_dict()) == order


def test_an_order_and_its_undoing_cancel_out_in_the_journal():
    note = new_note(0, (10, 10), "una")
    remove = Remove(note)
    assert net([(note, False), (note, True)]) == []
    assert net([(note, False), (remove, False)]) == [(note, False), (remove, False)]


# ---- the ones of other programs, and finding them ------------------------------------


def test_notes_of_other_programs_are_read_but_not_ours(doc):
    page = doc[0]
    theirs = page.add_text_annot((50, 50), "de Adobe")
    theirs.update()
    page.add_highlight_annot(pymupdf.Rect(10, 100, 80, 110))
    (found,) = page_notes(doc, 0)
    assert found.text == "de Adobe" and not found.ours


def test_finding_what_is_under_a_point(doc):
    new_note(0, (100, 100), "debajo").apply(doc)
    new_note(0, (110, 110), "encima").apply(doc)
    found = page_notes(doc, 0)
    assert note_at(found, 105, 105).text == "debajo"
    assert note_at(found, 115, 115).text == "encima"
    assert note_at(found, 300, 200) is None


# ---- a width chosen by hand, and bold -------------------------------------------

LONG = "una frase bastante larga para que haya que cortarla en varias líneas seguidas"


def dark(document, page: int, rect) -> int:
    """How many pixels of a part of a page are painted."""
    pixmap = document[page].get_pixmap(clip=pymupdf.Rect(rect), matrix=pymupdf.Matrix(3, 3))
    return sum(1 for value in pixmap.samples[1::3] if value < 140)


def test_a_box_with_a_width_cuts_its_text_to_fit():
    lines, rect = box_layout(LONG, SANS, 12, (50, 40), 400, width=120)
    assert len(lines) > 3 and rect[2] - rect[0] == pytest.approx(120)
    assert all(notes.text_width(line, SANS, 12) <= 120 - 2 * notes.PADDING for line in lines)
    assert " ".join(lines) == LONG, "cut at the spaces, with nothing lost"
    narrow, wide = (box_layout(LONG, SANS, 12, (50, 40), 400, width=w)[1] for w in (90, 200))
    assert narrow[3] > rect[3] > wide[3], "narrower is taller"


def test_a_width_never_takes_the_box_out_of_the_page():
    _, rect = box_layout(LONG, SANS, 12, (300, 40), 400, width=300)
    assert rect[2] <= 400


@pytest.mark.parametrize("page", [0, 1])
def test_a_box_with_a_width_is_read_back_as_it_was_put(doc, page):
    order = new_text_box(page, (50, 40), LONG, SANS, 11, (0.1, 0.2, 0.8), width=130)
    order.apply(doc)
    again = saved_again(doc)
    (found,) = page_notes(again, page)
    assert found.text == LONG and found.width == pytest.approx(130)
    assert found.rect[2] - found.rect[0] == pytest.approx(130, abs=0.1)
    assert found.order() == order or close_to(found.order().origin, order.origin, 0.1)
    assert box_layout(LONG, SANS, 11, (50, 40), 400, 130)[1][3] == pytest.approx(
        found.rect[3], abs=0.1
    )


def test_every_line_of_a_narrow_box_is_seen_whole(doc):
    order = new_text_box(0, (50, 40), LONG, SANS, 12, width=110)
    order.apply(doc)
    lines, rect = box_layout(LONG, SANS, 12, (50, 40), 400, 110)
    again = saved_again(doc)
    page = again[0]
    (annotation,) = page.annots()
    shown = [line.strip() for line in annotation.get_text().splitlines() if line.strip()]
    assert shown == lines, "the lines cut here are the lines every viewer shows"
    words = page.get_text("words")
    assert all(rect[0] <= word[0] and word[2] <= rect[2] for word in words), "inside its box"
    assert max(word[3] for word in words) <= rect[3] + 3, "the last line is there, whole"
    assert dark(again, 0, (rect[2] + 1, rect[1], 400, rect[3])) == 0, "nothing past its edge"


@pytest.mark.parametrize("font", [SANS, SERIF, MONO])
def test_bold_is_heavier_and_is_read_back(doc, font):
    place = (40, 40)
    new_text_box(0, place, "Muy importante", font, 14).apply(doc)
    new_text_box(1, place, "Muy importante", font, 14, bold=True).apply(doc)
    again = saved_again(doc)
    plain, bold = page_notes(again, 0)[0], page_notes(again, 1)[0]
    assert not plain.bold and bold.bold and bold.order().bold
    assert dark(again, 1, bold.rect) > dark(again, 0, plain.rect) * 1.15
    assert bold.rect[2] - bold.rect[0] >= plain.rect[2] - plain.rect[0]
    look = again.xref_object(again[1].first_annot.xref, compressed=True)
    assert "FreeText" in look


def test_bold_letters_are_wider_so_the_lines_are_cut_for_them():
    assert notes.text_width("Muy importante", SANS, 12, bold=True) > notes.text_width(
        "Muy importante", SANS, 12
    )
    plain = wrap_text(LONG, SANS, 12, 150)
    bold = wrap_text(LONG, SANS, 12, 150, bold=True)
    assert len(bold) >= len(plain)
    assert all(notes.text_width(line, SANS, 12, True) <= 150 for line in bold)


def test_width_and_bold_go_to_the_journal_and_back():
    order = new_text_box(0, (50, 40), LONG, SANS, 12, width=130, bold=True)
    assert command_from_dict(order.to_dict()) == order
    plain = new_text_box(0, (50, 40), "hola")
    written = plain.to_dict()
    assert "width" not in written and "bold" not in written, "old journals read the same"
    assert command_from_dict(written) == plain
    odd = written | {"width": "ancho", "bold": "sí"}
    assert command_from_dict(odd).width == 0 and command_from_dict(odd).bold is False


def test_changing_width_or_weight_and_undoing_it(doc):
    new_text_box(0, (50, 40), LONG, SANS, 12).apply(doc)
    (note,) = page_notes(doc, 0)
    before = doc[0].get_pixmap().samples
    change = changed(note, width=120.0, bold=True)
    change.apply(doc)
    (now,) = page_notes(doc, 0)
    assert now.width == pytest.approx(120) and now.bold and now.name == note.name
    change.undo(doc)
    assert doc[0].get_pixmap().samples == before
    assert page_notes(doc, 0)[0].width == 0
