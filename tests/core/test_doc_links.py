"""Tests for links to a place of another document (/GoToR)."""

import shutil
from pathlib import Path
from urllib.parse import unquote

import pymupdf
import pytest

from app.core.commands import command_from_dict
from app.core.doc_links import (
    AddDocLink,
    ChangeLinkFile,
    page_doc_links,
    relative_file,
    resolve,
)


@pytest.fixture
def tema(tmp_path, sample):
    (tmp_path / "Temas").mkdir()
    (tmp_path / "Leyes").mkdir()
    shutil.copy(sample("texto-partido.pdf"), tmp_path / "Temas" / "Tema 5.pdf")
    shutil.copy(sample("boe.pdf"), tmp_path / "Leyes" / "Constitución.pdf")
    return tmp_path / "Temas" / "Tema 5.pdf"


def test_the_other_file_is_written_relative_to_the_document(tema):
    ley = tema.parent.parent / "Leyes" / "Constitución.pdf"
    written = relative_file(tema, ley)
    assert written == "../Leyes/Constitución.pdf"
    assert resolve(tema, written) == ley.resolve()
    assert relative_file(tema, tema.parent / "Tema 6.pdf") == "Tema 6.pdf"


def link(name="l1", page=0, top=640.0, file="../Leyes/Constitución.pdf"):
    return AddDocLink(
        0, ((72.0, 100.0, 200.0, 112.0), (72.0, 114.0, 150.0, 126.0)), file, page, top, name
    )


def test_a_link_is_a_standard_gotor_and_can_be_undone(tema, tmp_path):
    with pymupdf.open(tema) as doc:
        order = link(page=13)
        assert order.apply(doc) == [0]
        found = page_doc_links(doc, 0)
        assert [(item.name, item.file, item.page, item.top) for item in found] == [
            ("l1", "../Leyes/Constitución.pdf", 13, 640.0)
        ] * 2
        assert found[0].rect == pytest.approx((72.0, 100.0, 200.0, 112.0), abs=0.05)
        doc.save(tmp_path / "con-enlace.pdf")
        order.undo(doc)
        assert page_doc_links(doc, 0) == []
    with pymupdf.open(tmp_path / "con-enlace.pdf") as saved:
        links = [item for item in saved[0].get_links() if item["kind"] == pymupdf.LINK_GOTOR]
        assert len(links) == 2 and unquote(links[0]["file"]) == "../Leyes/Constitución.pdf"
        assert links[0]["page"] == 13


def test_applied_twice_it_is_put_once_and_it_is_written_down(tema):
    order = link()
    assert command_from_dict(order.to_dict()) == order
    with pymupdf.open(tema) as doc:
        order.apply(doc)
        order.apply(doc)
        assert len(page_doc_links(doc, 0)) == 2


def test_a_moved_file_is_changed_in_every_link(tema):
    with pymupdf.open(tema) as doc:
        link("a").apply(doc)
        link("b", file="otro.pdf").apply(doc)
        change = ChangeLinkFile("../Leyes/Constitución.pdf", "../Leyes/CE.pdf")
        assert command_from_dict(change.to_dict()) == change
        assert change.apply(doc) == [0]
        assert sorted({item.file for item in page_doc_links(doc, 0)}) == [
            "../Leyes/CE.pdf",
            "otro.pdf",
        ]
        change.undo(doc)
        assert "../Leyes/Constitución.pdf" in {item.file for item in page_doc_links(doc, 0)}


def test_on_a_page_kept_turned_the_link_covers_the_words_as_shown(tema):
    with pymupdf.open(tema) as doc:
        doc[0].set_rotation(90)
        link().apply(doc)
        assert page_doc_links(doc, 0)[0].rect == pytest.approx(
            (72.0, 100.0, 200.0, 112.0), abs=0.05
        )


def test_links_of_another_program_are_read(tema):
    with pymupdf.open(tema) as doc:
        page = doc[0]
        page.insert_link(
            {
                "kind": pymupdf.LINK_GOTOR,
                "from": pymupdf.Rect(10, 10, 50, 20),
                "file": "x.pdf",
                "page": 2,
                "to": pymupdf.Point(0, 300),
            }
        )
        found = page_doc_links(doc, 0)
        assert [(item.name, item.file, item.page) for item in found] == [("", "x.pdf", 2)]


def test_nothing_to_link_is_refused(tema):
    from app.core.commands import CommandError

    with pymupdf.open(tema) as doc, pytest.raises(CommandError):
        AddDocLink(0, (), "x.pdf", 0, None, "n").apply(doc)
    assert Path(tema).exists()
