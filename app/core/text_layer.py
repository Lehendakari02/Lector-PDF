"""The text read from scanned pages, written on them as invisible text.

The page looks exactly the same: the words are ordinary PDF text drawn in
"invisible" mode (render mode 3), each one over its picture. Any PDF reader
(Adobe, Edge…) can then search, select and copy them, and so can this one.

Written as an order (see ``app.core.commands``), so it goes into the journal,
is saved when the user saves and can be taken back. Each page gets one
content stream of its own, added at the end of the page's list of contents,
and a note on the page (``/LectorPDFOCR``) of which streams are ours: taking
the text away removes exactly those and nothing else.

The words use Helvetica, which every reader has, with the Windows letters
(WinAnsi): every Spanish letter is there (á, ñ, ü, ¿, ¡, €…). A letter outside
them is written as "?", and the rest of the word is still found.
"""

import math
from dataclasses import dataclass

from app.core.commands import CommandError, register_reader

LAYER_KEY = "LectorPDFOCR"  # on the page: the content streams that are ours
FONT_NAME = "LectorOCR"  # the name of the font in the page's resources
FONT_OBJECT = "<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/WinAnsiEncoding>>"
ENCODING = "cp1252"

Matrix = tuple[float, float, float, float, float, float]
Word = tuple[str, float, float, float, float]  # text, x0, y0, x1, y1


@dataclass(frozen=True)
class PageLayer:
    """The words of one page, on the straightened picture, and how to get
    from there to the page as it is shown (see ``app.core.ocr.OcrPage``)."""

    page: int
    matrix: Matrix
    words: tuple[Word, ...]

    @classmethod
    def of(cls, recognised) -> "PageLayer":
        """From an ``OcrPage``.

        The words are written level, not with the small slant of the scan:
        some readers break a slanted line into pieces, even in the middle of
        a word. Each word covers the place of its picture. When the page was
        read turned on its side or upside down, the words go that way.

        The numbers are rounded: tenths of a point is far finer than any scan,
        and the journal stays small.
        """
        import pymupdf

        matrix = pymupdf.Matrix(*recognised.matrix)
        quarter = round(math.degrees(math.atan2(matrix.b, matrix.a)) / 90) * 90 % 360
        to_level = matrix * pymupdf.Matrix(-quarter)
        words = []
        for word in recognised.words:
            if not word.text.strip():
                continue
            box = (pymupdf.Rect(word.rect).quad * to_level).rect
            words.append((word.text, *(round(value, 1) for value in box)))
        level = tuple(round(value, 6) for value in pymupdf.Matrix(quarter))
        return cls(recognised.page, level, tuple(words))


@dataclass(frozen=True)
class AddTextLayer:
    """Write the text read on some pages. Undo takes it away again."""

    layers: tuple[PageLayer, ...]

    text_change = True  # the letters of these pages are different afterwards

    def pages(self) -> list[int]:
        return [layer.page for layer in self.layers]

    def apply(self, doc) -> list[int]:
        for layer in self.layers:
            if not 0 <= layer.page < doc.page_count:
                raise CommandError(f"no page {layer.page}")
            if has_layer(doc, layer.page):
                raise CommandError(f"page {layer.page} already has its text written")
        for layer in self.layers:
            _write(doc, layer)
        return self.pages()

    def undo(self, doc) -> list[int]:
        for layer in self.layers:
            if not 0 <= layer.page < doc.page_count or not has_layer(doc, layer.page):
                raise CommandError(f"page {layer.page} has no text written by us")
        for layer in self.layers:
            remove_layer(doc, layer.page)
        return self.pages()

    def to_dict(self) -> dict:
        return {
            "what": "text_layer",
            "layers": [
                {"page": layer.page, "matrix": list(layer.matrix), "words": layer.words}
                for layer in self.layers
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AddTextLayer":
        layers = []
        for item in data["layers"]:
            matrix = tuple(float(value) for value in item["matrix"])
            if len(matrix) != 6:
                raise ValueError("a matrix has six numbers")
            words = tuple(
                (str(text), float(x0), float(y0), float(x1), float(y1))
                for text, x0, y0, x1, y1 in item["words"]
            )
            layers.append(PageLayer(int(item["page"]), matrix, words))
        if not layers:
            raise ValueError("no pages")
        return cls(tuple(layers))


register_reader("text_layer", AddTextLayer.from_dict)


def has_layer(doc, page_number: int) -> bool:
    return bool(_ours(doc, doc.page_xref(page_number)))


def _ours(doc, page_xref: int) -> list[int]:
    kind, value = doc.xref_get_key(page_xref, LAYER_KEY)
    if kind == "array":
        return [int(part) for part in value.strip("[]").split()[::3] if part.isdigit()]
    return []


def _contents(doc, page_xref: int) -> list[int]:
    kind, value = doc.xref_get_key(page_xref, "Contents")
    if kind == "xref":
        return [int(value.split()[0])]
    if kind == "array":
        return [int(part) for part in value.strip("[]").split()[::3] if part.isdigit()]
    return []


def _references(xrefs: list[int]) -> str:
    return "[" + " ".join(f"{xref} 0 R" for xref in xrefs) + "]"


def _new_stream(doc, data: bytes) -> int:
    xref = doc.get_new_xref()
    doc.update_object(xref, "<<>>")
    doc.update_stream(xref, data)
    return xref


def _inherited_resources(doc, page_xref: int) -> str:
    """The resources a page takes from the tree of pages, written out."""
    xref = page_xref
    for _ in range(64):  # a damaged tree must not loop forever
        kind, value = doc.xref_get_key(xref, "Parent")
        if kind != "xref":
            break
        xref = int(value.split()[0])
        kind, value = doc.xref_get_key(xref, "Resources")
        if kind == "xref":
            return doc.xref_object(int(value.split()[0]), compressed=True)
        if kind == "dict":
            return value
    return "<<>>"


def _add_font(doc, page_xref: int) -> None:
    """Make the font available on the page as ``FONT_NAME``."""
    kind, value = doc.xref_get_key(page_xref, "Resources")
    if kind == "xref":
        holder, path = int(value.split()[0]), "Font"
    else:
        if kind != "dict":  # taken from the tree of pages: the page gets its own copy
            doc.xref_set_key(page_xref, "Resources", _inherited_resources(doc, page_xref))
        holder, path = page_xref, "Resources/Font"
    kind, value = doc.xref_get_key(holder, path)
    if kind == "xref":
        holder, path = int(value.split()[0]), ""
    elif kind != "dict":
        doc.xref_set_key(holder, path, "<<>>")
    key = f"{path}/{FONT_NAME}" if path else FONT_NAME
    if doc.xref_get_key(holder, key)[0] != "xref":
        font = doc.get_new_xref()
        doc.update_object(font, FONT_OBJECT)
        doc.xref_set_key(holder, key, f"{font} 0 R")


def _escaped(text: bytes) -> str:
    out = text.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return out.decode("latin-1")


_FONT = []


def _helvetica():
    """Helvetica's measures, to make each word as wide as on the picture.
    (``pymupdf.get_text_length`` takes "ñ" and "ó" as having no width.)"""
    import pymupdf

    if not _FONT:
        _FONT.append(pymupdf.Font("helv"))
    return _FONT[0]


def layer_content(page, layer: PageLayer) -> bytes:
    """The invisible words of a page, as PDF drawing instructions."""
    import pymupdf

    font = _helvetica()
    to_pdf = page.derotation_matrix * ~page.transformation_matrix
    straight = pymupdf.Matrix(*layer.matrix)
    lines = ["Q", "q", "BT", "3 Tr"]
    for text, x0, y0, x1, y1 in layer.words:
        written = text.encode(ENCODING, "replace")
        width = font.text_length(written.decode(ENCODING), fontsize=1)
        if width <= 0 or x1 <= x0 or y1 <= y0:
            continue
        # The letters fill the word's box: from their top to their bottom is
        # its height (what a reader marks when the word is selected).
        size = (y1 - y0) / (font.ascender - font.descender)
        baseline = y1 + font.descender * size
        # From the letters at size 1 to the word's box on the straightened page,
        # then to the page as shown, then to the page as the PDF writes it.
        box = pymupdf.Matrix((x1 - x0) / width, 0, 0, -size, x0, baseline)
        a, b, c, d, e, f = box * straight * to_pdf
        lines.append(
            f"/{FONT_NAME} 1 Tf {a:.5f} {b:.5f} {c:.5f} {d:.5f} {e:.2f} {f:.2f} Tm "
            f"({_escaped(written + b' ')}) Tj"
        )
    lines += ["ET", "Q", ""]
    return "\n".join(lines).encode("latin-1")


def _write(doc, layer: PageLayer) -> None:
    page = doc[layer.page]
    page_xref = page.xref
    _add_font(doc, page_xref)
    content = layer_content(page, layer)
    before = _contents(doc, page_xref)
    # What was on the page is closed in "q … Q", so that whatever it left
    # changed (where the drawing starts, its size…) does not move our words.
    opening = _new_stream(doc, b"q\n")
    ours = _new_stream(doc, content)
    doc.xref_set_key(page_xref, "Contents", _references([opening, *before, ours]))
    doc.xref_set_key(page_xref, LAYER_KEY, _references([opening, ours]))


def remove_layer(doc, page_number: int) -> None:
    """Take away the text we wrote on a page (the streams stay unused in the file)."""
    page_xref = doc.page_xref(page_number)
    ours = set(_ours(doc, page_xref))
    left = [xref for xref in _contents(doc, page_xref) if xref not in ours]
    doc.xref_set_key(page_xref, "Contents", _references(left))
    doc.xref_set_key(page_xref, LAYER_KEY, "null")
