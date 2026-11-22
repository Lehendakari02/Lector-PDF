"""Tests for the arrows and symbols written inside a text of the page."""

import pymupdf
import pytest

from app.core import notes, symbols
from app.core.notes import MONO, SANS, SERIF
from app.core.settings import Settings


def test_the_font_brings_every_symbol_that_can_be_chosen():
    assert symbols.font_file().is_file()
    assert symbols.font_file().stat().st_size < 40_000, "small: it goes inside the PDFs"
    font = pymupdf.Font(fontfile=str(symbols.font_file()))
    assert all(font.has_glyph(ord(symbol)) for symbol in symbols.SYMBOLS)
    chosen = "".join(members for _, members in symbols.GROUPS)
    assert len(chosen) == len(set(chosen)), "none twice"
    for symbol in symbols.SYMBOLS:
        with pytest.raises(UnicodeEncodeError):  # none is a letter the base fonts have
            symbol.encode("cp1252")


def test_a_line_is_cut_into_letters_and_symbols():
    assert symbols.runs("a → b ✓✗") == [(False, "a "), (True, "→"), (False, " b "), (True, "✓✗")]
    assert symbols.runs("") == [] and symbols.runs("ñ€") == [(False, "ñ€")]
    assert symbols.has_symbols("x ⇒ y") and not symbols.has_symbols("x => y")


@pytest.mark.parametrize(
    ("keys", "result"),
    [
        ("a -> b", "a → b"),
        ("a --> b", "a → b"),
        ("a <- b", "a ← b"),
        ("a <-- b", "a ← b"),
        ("a <-> b", "a ↔ b"),
        ("a <--> b", "a ↔ b"),
        ("a => b", "a ⇒ b"),
        ("a ==> b", "a ⇒ b"),
        ("a <=> b", "a ⇔ b"),
        ("a <= b - c", "a <= b - c"),
    ],
)
def test_arrows_typed_with_plain_keys(keys, result):
    assert symbols.typed(keys) == result
    # Letter by letter, as the hand types them, the result is the same.
    text = ""
    for letter in keys:
        text += letter
        found = symbols.typed_at(text)
        if found is not None:
            count, symbol = found
            last = text[-1] if text[-1] not in "<>-=" else ""
            text = text[: len(text) - len(last) - count] + symbol + last
    assert text == result


def test_typed_arrows_can_be_turned_off(tmp_path):
    settings = Settings(tmp_path / "s.json")
    assert symbols.typed_wanted(settings)
    settings.set(symbols.TYPED_SETTING, False)
    assert not symbols.typed_wanted(settings)
    settings.set(symbols.TYPED_SETTING, "no sé")
    assert symbols.typed_wanted(settings)


def test_a_symbol_counts_in_the_width_of_a_line():
    plain = notes.text_width("a  b", SANS, 12)
    assert notes.text_width("a → b", SANS, 12) == pytest.approx(plain + symbols.width("→", 12))
    lines = notes.wrap_text("uno → dos → tres → cuatro", SANS, 12, 70)
    assert len(lines) > 1 and " ".join(lines) == "uno → dos → tres → cuatro"


def look_of(doc, annotation):
    xref = int(doc.xref_get_key(annotation.xref, "AP/N")[1].split()[0])
    return xref, doc.xref_stream(xref).decode("latin-1")


@pytest.mark.parametrize("font", [SANS, SERIF, MONO])
def test_a_text_with_symbols_is_written_with_two_fonts(font):
    doc = pymupdf.open()
    doc.new_page()
    text = "Ley (orgánica) → mayoría ✓ €"
    notes.new_text_box(0, (60, 80), text, font, 14).apply(doc)
    page = doc[0]
    (annotation,) = page.annots()
    xref, stream = look_of(doc, annotation)
    assert f"/{symbols.FONT_NAME} 14 Tf" in stream and f"/{notes.FONTS[font]} 14 Tf" in stream
    assert "(Ley \\(org\\341nica\\) ) Tj" in stream, "plain letters stay with the base font"
    assert "?" not in stream
    fonts = doc.xref_get_key(xref, "Resources/Font")[1]
    assert symbols.FONT_NAME in fonts and notes.FONTS[font] in fonts
    assert "Nimbus" not in "".join(doc.xref_object(x) for x in range(1, doc.xref_length()))
    # Any reader can find and copy the text, symbols included.
    words = [word[4] for word in page.get_text("words")]
    assert "→" in words and "✓" in words and "mayoría" in words
    (note,) = notes.page_notes(doc, 0)
    assert (note.text, note.font, note.size) == (text, font, 14)


def test_the_font_goes_into_the_document_only_once():
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    for page, text in ((0, "uno → dos"), (0, "✓ hecho"), (1, "otra ⇒ página")):
        notes.new_text_box(page, (60, 80 + 40 * len(text)), text).apply(doc)
    files = [x for x in range(1, doc.xref_length()) if "/FontFile2" in doc.xref_object(x)]
    assert len(files) == 1
    data = doc.tobytes()
    assert len(data) < 40_000
    again = pymupdf.open(stream=data)
    notes.new_text_box(1, (60, 300), "al volver a abrir ★").apply(again)
    files = [x for x in range(1, again.xref_length()) if "/FontFile2" in again.xref_object(x)]
    assert len(files) == 1, "a document that already has it does not get another"


def test_bold_and_a_width_chosen_by_hand_keep_their_symbols():
    doc = pymupdf.open()
    doc.new_page()
    order = notes.new_text_box(
        0, (60, 80), "① primero ⇒ segundo ⇒ tercero", SANS, 12, (0.1, 0.1, 0.1), 90, True
    )
    order.apply(doc)
    page = doc[0]
    (annotation,) = page.annots()
    xref, stream = look_of(doc, annotation)
    assert stream.count(") Tj") >= 3, "cut into lines"
    assert "Helvetica-Bold" in doc.xref_object(
        int(doc.xref_get_key(xref, "Resources/Font/Helv")[1].split()[0])
    )
    (note,) = notes.page_notes(doc, 0)
    assert note.bold and note.width == 90 and "⇒" in note.text
    order.undo(doc)
    page = doc[0]
    assert list(page.annots()) == []


def test_a_text_without_symbols_is_written_as_always():
    doc = pymupdf.open()
    doc.new_page()
    notes.new_text_box(0, (60, 80), "sin nada raro: ñ € «»").apply(doc)
    page = doc[0]
    (annotation,) = page.annots()
    _, stream = look_of(doc, annotation)
    assert symbols.FONT_NAME not in stream
    assert doc.xref_get_key(doc.pdf_catalog(), notes.SYMBOL_FONT_KEY)[0] == "null"


def test_symbols_on_a_turned_page():
    doc = pymupdf.open()
    doc.new_page()
    doc[0].set_rotation(90)
    notes.new_text_box(0, (60, 80), "girada → bien").apply(doc)
    page = doc[0]
    (annotation,) = page.annots()
    _, stream = look_of(doc, annotation)
    assert f"/{symbols.FONT_NAME}" in stream
    assert "→" in page.get_text()


def test_the_built_program_can_check_its_symbols(monkeypatch, tmp_path):
    from app.main import CHECK_SYMBOLS_FLAG, EXIT_SYMBOLS_FAILED, main

    assert main(["lector-pdf", CHECK_SYMBOLS_FLAG]) == 0
    monkeypatch.setattr(symbols, "font_file", lambda: tmp_path / "no-esta.ttf")
    symbols._font.cache_clear()
    try:
        assert main(["lector-pdf", CHECK_SYMBOLS_FLAG]) == EXIT_SYMBOLS_FAILED
    finally:
        symbols._font.cache_clear()


def test_letters_of_other_languages_are_written_with_the_font_of_the_symbols():
    """«Łódź», «Ştefan» or Greek: the built-in letters lack them."""
    import pymupdf

    from app.core import notes
    from app.core.commands import new_name

    assert symbols.is_symbol("Ł") and symbols.is_symbol("ά") and symbols.is_symbol("ș")
    assert not symbols.is_symbol("ñ") and not symbols.is_symbol("€") and not symbols.is_symbol("a")
    doc = pymupdf.open()
    doc.new_page()
    text = "Łódź, Ştefan, Ελλάδα → fin"
    notes.AddTextBox(0, (50, 50), text, notes.SANS, 12, (0, 0, 0), new_name()).apply(doc)
    assert doc[0].get_text().strip() == text
