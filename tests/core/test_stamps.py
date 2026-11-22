"""Tests for quick marks and stamps."""

from datetime import date

import pymupdf

from app.core.drawing import AddInk
from app.core.stamps import CHECK, CROSS, DOT, OWN, TODAY, Stamp, mark_order, own_stamps


def test_marks_are_drawings_centred_at_the_click(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    for kind in (CHECK, CROSS, DOT):
        order = mark_order(kind, 0, 100, 200, 12)
        assert isinstance(order, AddInk)
        xs = [x for stroke in order.strokes for x, _ in stroke]
        ys = [y for stroke in order.strokes for _, y in stroke]
        assert min(xs) > 93 and max(xs) < 107 and min(ys) > 193 and max(ys) < 207, kind
        order.apply(doc)
    doc.save(tmp_path / "marcas.pdf")
    with pymupdf.open(tmp_path / "marcas.pdf") as saved:
        assert [a.type[1] for a in saved[0].annots()] == ["Ink", "Ink", "Ink"]


def test_the_words_of_a_stamp():
    assert Stamp(TODAY).text(date(2026, 11, 22)) == "22/11/2026"
    assert Stamp(OWN, "Pagado").text() == "Pagado"
    assert Stamp(CHECK).text() == ""
    assert own_stamps(["Pagado", " Pagado ", "", 3, "Copia"]) == ["Pagado", "Copia"]
    assert own_stamps(None) == []
