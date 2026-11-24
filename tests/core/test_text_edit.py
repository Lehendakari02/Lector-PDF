"""Tests for «Corregir texto» (task 6.1): a word of the document is changed
and looks as if it had always been there."""

import json

import pymupdf
import pytest

from app.core import text_edit
from app.core.commands import CommandError, command_from_dict
from app.core.text_edit import change_text

TIMES = pymupdf.Font("tiro").buffer  # a font to keep inside the test documents


@pytest.fixture(autouse=True)
def no_fonts_of_this_computer(monkeypatch):
    """The fonts installed differ from one computer to another: the tests
    say which ones there are."""
    monkeypatch.setattr(text_edit, "font_folders", lambda: [])
    monkeypatch.setattr(text_edit, "_installed", None)


def new_doc(lines, font="helv", size=12, embedded=False, width=400, height=300):
    """A page with these lines, one under the other, from the left margin."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    name = font
    if embedded:
        name = "Tiempos"
        page.insert_font(fontname=name, fontbuffer=TIMES)
    for number, line in enumerate(lines):
        page.insert_text((50, 60 + number * 20), line, fontname=name, fontsize=size)
    return doc


def seen_box(page, text, number=0):
    rect = (page.search_for(text)[number] * page.rotation_matrix).normalize()
    return tuple(rect)


def correct(doc, old, new, page=0, number=0):
    order = change_text(page, [seen_box(doc[page], old, number)], old, new).prepared(doc)
    order.apply(doc)
    return order


def lines_of(doc, page=0):
    return [line.strip() for line in doc[page].get_text().splitlines() if line.strip()]


def test_a_word_is_changed_with_the_font_of_the_document():
    doc = new_doc(["Primera línea del texto.", "El plazo es de diez días.", "Última."])
    fonts_before = len(doc[0].get_fonts())
    order = correct(doc, "diez", "quince")
    assert lines_of(doc) == ["Primera línea del texto.", "El plazo es de quince días.", "Última."]
    assert order.look == text_edit.LOOK_SAME
    assert len(doc[0].get_fonts()) == fonts_before, "no other font was needed"


def test_the_rest_of_the_line_moves_so_nothing_overlaps():
    doc = new_doc(["El plazo es de diez días hábiles."])
    correct(doc, "diez", "veinticinco")
    page = doc[0]
    new = page.search_for("veinticinco")[0]
    following = page.search_for("días")[0]
    assert new.x1 < following.x0 < new.x1 + 6, "the usual gap between the words"
    assert page.search_for("hábiles.")[0].x0 > following.x1


def test_a_shorter_word_pulls_the_rest_back():
    doc = new_doc(["Se publica en el Boletín Oficial del Estado."])
    before = doc[0].search_for("Oficial")[0]
    correct(doc, "Boletín", "BOE")
    after = doc[0].search_for("Oficial")[0]
    assert after.x0 < before.x0 - 10
    assert lines_of(doc) == ["Se publica en el BOE Oficial del Estado."]


def test_the_new_text_is_read_in_its_place():
    """Search, selection and copying read it with its sentence, not at the
    end of the page."""
    doc = new_doc(["Uno dos tres", "cuatro cinco seis", "siete ocho nueve"])
    correct(doc, "cinco", "CINCO")
    words = [word[4] for word in doc[0].get_text("words", sort=False)]
    assert words == ["Uno", "dos", "tres", "cuatro", "CINCO", "seis", "siete", "ocho", "nueve"]


def test_undo_brings_back_the_page_as_it_was():
    doc = new_doc(["El plazo es de diez días."])
    before = doc[0].get_text("rawdict")
    order = correct(doc, "diez", "quince")
    assert order.undo(doc) == [0]
    assert lines_of(doc) == ["El plazo es de diez días."]
    after = doc[0].get_text("rawdict")
    assert [b["bbox"] for b in after["blocks"]] == [b["bbox"] for b in before["blocks"]]


def test_a_font_kept_inside_the_document_is_used_again():
    doc = new_doc(["Firmado en Bilbao, a tres de marzo."], embedded=True)
    order = correct(doc, "tres", "trece")
    assert order.look == text_edit.LOOK_SAME
    assert lines_of(doc) == ["Firmado en Bilbao, a trece de marzo."]
    names = {font[3] for font in doc[0].get_fonts()}
    assert len(names) == 1, "the same embedded font, no other"


def test_a_letter_the_font_does_not_have_is_borrowed_and_said():
    """Fonts are usually kept with only the letters used: a new one comes
    from a similar font, and the window says which."""
    doc = new_doc(["abc def"], embedded=True)
    doc.subset_fonts()
    order = correct(doc, "def", "dZf")
    assert order.look == "Times"
    assert lines_of(doc) == ["abc dZf"]


def test_the_same_font_of_the_computer_is_borrowed_when_there(tmp_path, monkeypatch):
    folder = tmp_path / "Fonts"
    folder.mkdir()
    (folder / "times.otf").write_bytes(TIMES)
    monkeypatch.setattr(text_edit, "font_folders", lambda: [folder])
    doc = new_doc(["abc def"], embedded=True)
    doc.subset_fonts()
    order = correct(doc, "def", "dQf")
    assert order.look == pymupdf.Font(fontbuffer=TIMES).name
    assert lines_of(doc) == ["abc dQf"]


def test_a_letter_no_font_has_is_refused():
    doc = new_doc(["abc def"])
    with pytest.raises(CommandError, match=text_edit.NO_LETTER):
        change_text(0, [seen_box(doc[0], "def")], "def", "d中f").prepared(doc)


def test_taking_a_word_away_leaves_one_gap():
    doc = new_doc(["uno dos tres"])
    correct(doc, "dos", "")
    assert lines_of(doc) == ["uno tres"]
    page = doc[0]
    gap = page.search_for("tres")[0].x0 - page.search_for("uno")[0].x1
    assert 1 < gap < 6


def test_a_justified_line_keeps_its_right_edge():
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    text = (
        "La Nación española, deseando establecer la justicia, la libertad y la "
        "seguridad y promover el bien de cuantos la integran, proclama su voluntad."
    )
    page.insert_textbox((40, 40, 260, 200), text, fontsize=11, align=pymupdf.TEXT_ALIGN_JUSTIFY)
    first_line = doc[0].get_text("dict")["blocks"][0]["lines"][0]
    right = first_line["bbox"][2]
    words = "".join(span["text"] for span in first_line["spans"]).split()
    old = words[2]
    correct(doc, old, old + "s")
    line = doc[0].get_text("dict")["blocks"][0]["lines"][0]
    assert abs(line["bbox"][2] - right) < 1.0
    assert (old + "s") in "".join(span["text"] for span in line["spans"])


def test_a_centred_title_stays_centred():
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    title = "Tema 5"
    width = pymupdf.get_text_length(title, fontsize=16)
    page.insert_text(((400 - width) / 2, 60), title, fontsize=16)
    page.insert_text((50, 120), "Un párrafo que empieza a la izquierda del todo.", fontsize=11)
    correct(doc, "5", "15 bis")
    rect = doc[0].search_for("Tema 15 bis")[0]
    assert abs((rect.x0 + rect.x1) / 2 - 200) < 1.0


def test_a_text_too_long_for_the_line_is_refused_and_nothing_changes():
    doc = new_doc(["Una línea que llega casi hasta el borde derecho de la hoja"], width=330)
    before = doc[0].read_contents()
    order = change_text(0, [seen_box(doc[0], "casi")], "casi", "prácticamente siempre")
    with pytest.raises(CommandError, match=text_edit.TOO_LONG):
        order.prepared(doc)
    assert doc[0].read_contents() == before


def test_text_recognised_in_a_picture_is_not_changed():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Texto escaneado", render_mode=3)
    with pytest.raises(CommandError, match=text_edit.SCANNED):
        change_text(0, [seen_box(page, "escaneado")], "escaneado", "otro").prepared(doc)


def test_only_one_line_at_a_time():
    doc = new_doc(["primera línea", "segunda línea"])
    boxes = [seen_box(doc[0], "primera"), seen_box(doc[0], "segunda")]
    with pytest.raises(CommandError, match=text_edit.NOT_ONE_LINE):
        change_text(0, boxes, "primera segunda", "x").prepared(doc)


def test_a_text_that_is_no_longer_there_is_not_changed():
    doc = new_doc(["El plazo es de diez días."])
    order = change_text(0, [seen_box(doc[0], "diez")], "once", "quince")
    with pytest.raises(CommandError, match=text_edit.NOT_THERE):
        order.prepared(doc)


def test_the_other_lines_are_never_touched_even_when_close():
    lines = [f"línea número {n} con palabras" for n in range(8)]
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    for number, line in enumerate(lines):
        page.insert_text((50, 40 + number * 11), line, fontsize=12)  # boxes overlap
    correct(doc, "3", "tres")
    expected = list(lines)
    expected[3] = "línea número tres con palabras"
    assert lines_of(doc) == expected


def test_a_turned_page():
    doc = new_doc(["El plazo es de diez días."])
    doc[0].set_rotation(90)
    correct(doc, "diez", "quince")
    assert lines_of(doc) == ["El plazo es de quince días."]


def test_the_order_is_written_down_and_read_back():
    """The recovery journal keeps it, with the copy of the page to undo it."""
    doc = new_doc(["El plazo es de diez días."])
    order = change_text(0, [seen_box(doc[0], "diez")], "diez", "quince").prepared(doc)
    again = command_from_dict(json.loads(json.dumps(order.to_dict())))
    assert again == order
    again.apply(doc)
    assert lines_of(doc) == ["El plazo es de quince días."]
    again.undo(doc)
    assert lines_of(doc) == ["El plazo es de diez días."]


def test_saved_it_reads_the_same_everywhere(tmp_path):
    doc = new_doc(["El plazo es de diez días."], embedded=True)
    correct(doc, "diez", "quince")
    path = tmp_path / "corregido.pdf"
    doc.save(path, garbage=3, deflate=True)
    with pymupdf.open(path) as saved:
        assert saved[0].search_for("quince días")
        assert not saved[0].search_for("diez")


def test_a_real_law(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        fonts = len(doc.get_page_fonts(0))
        order = correct(doc, "Generales", "Españolas")
        assert order.look == text_edit.LOOK_SAME
        assert "Cortes Españolas" in doc[0].get_text()
        assert len(doc.get_page_fonts(0)) == fonts
        # A justified line of the preamble keeps its edge.
        page = doc[2]
        line = next(
            line
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", ())
            if "deseando establecer" in "".join(span["text"] for span in line["spans"])
        )
        right = line["bbox"][2]
        correct(doc, "establecer", "implantar", page=2)
        line = next(
            line
            for block in doc[2].get_text("dict")["blocks"]
            for line in block.get("lines", ())
            if "deseando implantar" in "".join(span["text"] for span in line["spans"])
        )
        assert abs(line["bbox"][2] - right) < 1.0


def test_font_names_of_documents_are_understood():
    assert text_edit._family("ABCDEF+Arial-BoldItalicMT") == ("arial", True, True)
    assert text_edit._family("TimesNewRomanPSMT") == ("timesnewroman", False, False)
    assert text_edit._family("Calibri,Bold") == ("calibri", True, False)
    assert text_edit._family("Cambria Regular") == ("cambria", False, False)
    assert text_edit._family("Arimo-Regular") == ("arimo", False, False)
