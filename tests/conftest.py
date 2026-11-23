"""Shared test setup."""

import os
from pathlib import Path

import pytest

# Run Qt without a real screen so interface tests work on GitHub's machines.
# Must be set before PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SAMPLES_DIR = Path(__file__).resolve().parent / "ejemplos"


@pytest.fixture
def sample():
    """Return the path of a sample PDF from ``tests/ejemplos`` by file name."""

    def find(name: str) -> Path:
        path = SAMPLES_DIR / name
        assert path.is_file(), f"Missing sample file: {path}"
        return path

    return find


def _add_options(doc, page) -> None:
    """A group of two round options ("grupo": "uno" or "dos") and a list."""
    import pymupdf

    parent = doc.get_new_xref()
    kids = []
    height = page.rect.height
    for index, state in enumerate(("uno", "dos")):
        shown = doc.get_new_xref()
        doc.update_object(shown, "<< /Type /XObject /Subtype /Form /BBox [0 0 16 16] >>")
        doc.update_stream(shown, b"0 0 1 rg 4 4 8 8 re f")
        hidden = doc.get_new_xref()
        doc.update_object(hidden, "<< /Type /XObject /Subtype /Form /BBox [0 0 16 16] >>")
        doc.update_stream(hidden, b"")
        kid = doc.get_new_xref()
        top = 450 + 30 * index
        doc.update_object(
            kid,
            f"<< /Type /Annot /Subtype /Widget /Rect [220 {height - top - 16} 236 {height - top}]"
            f" /Parent {parent} 0 R /P {page.xref} 0 R /AS /Off"
            f" /AP << /N << /{state} {shown} 0 R /Off {hidden} 0 R >> >> >>",
        )
        kids.append(kid)
    refs = " ".join(f"{kid} 0 R" for kid in kids)
    doc.update_object(parent, f"<< /FT /Btn /Ff 49152 /T (grupo) /V /Off /Kids [{refs}] >>")
    kind, annots = doc.xref_get_key(page.xref, "Annots")
    assert kind == "array"
    doc.xref_set_key(page.xref, "Annots", "[" + annots.strip("[]") + f" {refs}]")
    catalog = doc.pdf_catalog()
    _kind, fields = doc.xref_get_key(catalog, "AcroForm/Fields")
    doc.xref_set_key(catalog, "AcroForm/Fields", "[" + fields.strip("[]") + f" {parent} 0 R]")
    page = doc.reload_page(page)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_LISTBOX
    widget.field_name = "turno"
    widget.choice_values = ["Mañana", "Tarde"]
    widget.rect = pymupdf.Rect(300, 450, 460, 490)
    widget.field_value = "Mañana"
    page.add_widget(widget)


@pytest.fixture
def full_form(tmp_path, sample):
    """The sample form with round options and a list too, in a folder of its own."""
    import pymupdf

    path = tmp_path / "solicitud.pdf"
    with pymupdf.open(sample("formulario.pdf")) as doc:
        _add_options(doc, doc[0])
        doc.save(path)
    return path


# ---- a made-up photo of a sheet of paper (De foto a PDF) -------------------

# The sheet in the made-up photo: slanted, as a phone sees it.
SHEET = [(300.0, 120.0), (880.0, 170.0), (940.0, 860.0), (250.0, 820.0)]
LINES = 10


def _along(a, b, share):
    return (a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share)


def _make_photo(path, shadow=True):
    """A photo of a sheet with ten lines of "writing" lying on a dark table,
    darker towards one corner, saved as a JPEG."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=1200, height=1000)
    page.draw_rect(page.rect, color=None, fill=(0.35, 0.25, 0.15))
    top_left, top_right, bottom_right, bottom_left = SHEET
    shape = page.new_shape()
    shape.draw_polyline([*SHEET, top_left])
    shape.finish(fill=(0.95, 0.94, 0.9), color=None, closePath=True)
    for line in range(LINES):
        share = 0.1 + line * 0.08
        left = _along(top_left, bottom_left, share)
        right = _along(top_right, bottom_right, share)
        shape.draw_line(_along(left, right, 0.1), _along(left, right, 0.9))
    shape.finish(color=(0.1, 0.1, 0.1), width=6)
    shape.commit()
    if shadow:  # less light on the right: a grey veil, stronger to the right
        for step in range(12):
            box = pymupdf.Rect(600 + step * 50, 0, 1200, 1000)
            page.draw_rect(box, color=None, fill=(0, 0, 0), fill_opacity=0.03)
    page.get_pixmap().save(path, jpg_quality=90)
    doc.close()
    return path


@pytest.fixture
def photo_of_paper():
    """Make a photo of a slanted sheet with lines of writing on a dark table:
    ``photo_of_paper(path, shadow=True)``. ``.sheet`` are its corners in the
    photo and ``.lines`` how many lines it has."""
    _make_photo.sheet = SHEET
    _make_photo.lines = LINES
    return _make_photo
