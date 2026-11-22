"""Tests for the summary of what is marked and written on a document."""

import zipfile

import pymupdf
import pytest

from app.core.annotation_list import Entry
from app.core.summary import summary_of, write_docx, write_pdf

YELLOW = (1.0, 0.92, 0.23)
BLUE = (0.1, 0.3, 0.9)
LONG = "artículo 14 de la Constitución española " * 20


def entries():
    return [
        Entry(4, "highlight", "a", (0, 10, 5, 12), YELLOW, "Los españoles son iguales"),
        Entry(0, "underline", "b", (0, 10, 5, 12), BLUE, LONG),
        Entry(0, "note", "c", (0, 50, 5, 52), YELLOW, "Repasar   el año"),
        Entry(0, "ink", "d", (0, 60, 5, 62), BLUE, ""),
        Entry(1, "highlight", "e", (0, 60, 5, 62), BLUE, "   "),
        Entry(2, "text_box", "f", (0, 60, 5, 62), BLUE, "Esquema"),
    ]


def test_marks_notes_and_texts_by_page_without_drawings():
    made = summary_of("tema 5", entries(), lambda c: "Definiciones" if c == YELLOW else "")
    assert [page.number for page in made.pages] == [0, 2, 4]
    first = made.pages[0].items
    assert [item.kind for item in first] == ["underline", "note"]
    assert first[0].text == LONG.strip(), "nothing cut"
    assert first[1].text == "Repasar el año" and first[1].color_name == "Definiciones"


def test_the_pdf_has_every_word_in_order(tmp_path):
    target = tmp_path / "resumen.pdf"
    write_pdf(summary_of("tema 5", entries() * 30, lambda c: "Plazos"), target)
    with pymupdf.open(target) as doc:
        assert doc.page_count > 1
        text = " ".join(page.get_text() for page in doc)
    plain = " ".join(text.split())
    assert "Resumen de tema 5" in plain and "Página 1" in plain and "Página 5" in plain
    assert "Repasar el año" in plain and "Los españoles son iguales" in plain
    assert plain.index("Página 1") < plain.index("Página 3") < plain.index("Página 5")
    assert not list(tmp_path.glob("*.tmp"))


def test_the_word_document_is_a_docx_with_the_words(tmp_path):
    target = tmp_path / "resumen.docx"
    write_docx(summary_of("tema <5> & más", entries()), target)
    with zipfile.ZipFile(target) as docx:
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= set(docx.namelist())
        body = docx.read("word/document.xml").decode("utf-8")
    assert "tema &lt;5&gt; &amp; más" in body
    assert "Los españoles son iguales" in body and "<w:u " in body and "<w:shd " in body


def test_an_empty_document_says_so(tmp_path):
    made = summary_of("vacío", [Entry(0, "ink", "d", (0, 0, 1, 1), BLUE, "")])
    assert made.empty
    write_pdf(made, tmp_path / "r.pdf")
    with pymupdf.open(tmp_path / "r.pdf") as doc:
        assert "no tiene nada subrayado" in doc[0].get_text()


def test_labels_can_be_translated():
    made = summary_of("x", entries(), labels={"page": "Page {0}"})
    assert made.label("page", 3) == "Page 3" and made.label("title", "x") == "Resumen de x"


def test_a_failed_write_leaves_no_file(tmp_path):
    folder = tmp_path / "no-such-folder"
    with pytest.raises(OSError):
        write_docx(summary_of("x", entries()), folder / "r.docx")
    assert not folder.exists()
