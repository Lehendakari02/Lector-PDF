"""Tests for reading the outline of a document."""

import pymupdf

from app.core.outline import OutlineEntry, read_outline


def test_outline_of_a_law(sample):
    with pymupdf.open(sample("boe.pdf")) as doc:
        outline = read_outline(doc)
    assert outline[0] == OutlineEntry(1, "Constitución Española.", 0)
    assert OutlineEntry(2, "TÍTULO PRELIMINAR", 2) in outline
    assert all(0 <= entry.page < 39 for entry in outline)


def test_document_without_outline(sample):
    with pymupdf.open(sample("formulario.pdf")) as doc:
        assert read_outline(doc) == []


class SloppyDocument:
    """An outline as careless programs write it."""

    page_count = 5

    def get_toc(self, simple=True):
        return [
            [1, "  Tema   1 \n", 1],
            [3, "Skips a level", 2],  # goes from level 1 to level 3
            [2, "", 3],  # no title
            [1, "Leads nowhere", 99],
            [1, "No page", -1],
        ]


def test_sloppy_outlines_are_tidied():
    assert read_outline(SloppyDocument()) == [
        OutlineEntry(1, "Tema 1", 0),
        OutlineEntry(2, "Skips a level", 1),
        OutlineEntry(1, "Leads nowhere", -1),
        OutlineEntry(1, "No page", -1),
    ]


def test_a_damaged_outline_counts_as_none():
    class Broken:
        page_count = 1

        def get_toc(self, simple=True):
            raise RuntimeError("damaged")

    assert read_outline(Broken()) == []
