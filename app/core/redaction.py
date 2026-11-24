"""Covering data for real («Tapar datos»).

What is covered does not only get a black box on top: it is taken out of the
page. The letters under the box are removed (also an invisible text layer
from OCR), the parts of pictures under it are painted black, and the lines
and shapes it covers go. Notes, marks, links and form fields that touch the
box go too, because they may hold the same data. Once the document is saved,
nothing of it can be copied, searched or recovered.

Until then it can be undone: before covering, the order keeps a copy of the
pages as they were (with their links, outline entries and field names, as
when taking pages away) and undoing puts that copy in their place.

Boxes are given as seen on the page (turned if the page is turned), like
everything else the window sends; here they are turned back to the page's
own coordinates.
"""

from dataclasses import dataclass, replace

from app.core.commands import CommandError, register_reader
from app.core.page_orders import (
    MAX_JOURNAL_COPY,
    DeletePages,
    _drop_fields,
    _field_roots,
    copy_of_pages,
    put_back_pages,
)

Box = tuple[float, float, float, float]
COVER = (0.0, 0.0, 0.0)
# Counted on the open document while something covered is in it: such a
# document is always written whole, never "adding at the end" (as a signed
# one is), because the earlier version at the start of the file would still
# have what was covered.
COVERED = "lector_covered"  # the boxes are black, as on paper
MIN_SIDE = 1.0  # points: a box thinner than this covers nothing


@dataclass(frozen=True)
class CoverData:
    """Cover ``areas`` ((page, box), …); or, with ``query``, every place where
    that text is written (found when the order is prepared).
    ``copy`` keeps the pages as they were, to undo it."""

    areas: tuple[tuple[int, Box], ...] = ()
    query: str = ""
    copy: DeletePages | None = None

    text_change = True  # the letters of these pages are different afterwards

    def pages(self) -> list[int]:
        return sorted({page for page, _box in self.areas})

    def prepared(self, doc) -> "CoverData":
        """The same order, with the places of the text found and a copy of
        the pages as they are now."""
        areas = self.areas
        if self.query.strip():
            areas = tuple(find_text(doc, self.query))
            if not areas:
                raise CommandError("the text is not in the document")
        areas = tuple(
            (page, box) for page, box in areas if 0 <= page < doc.page_count and _big(box)
        )
        if not areas:
            raise CommandError("nothing to cover")
        pages = sorted({page for page, _box in areas})
        return replace(self, areas=areas, copy=copy_of_pages(doc, pages))

    def apply(self, doc) -> list[int]:
        import pymupdf

        by_page: dict[int, list[Box]] = {}
        for page, box in self.areas:
            if not 0 <= page < doc.page_count:
                raise CommandError(f"there is no page {page + 1}")
            by_page.setdefault(page, []).append(box)
        try:
            for number, boxes in by_page.items():
                page = doc[number]
                rects = [(pymupdf.Rect(box) * page.derotation_matrix).normalize() for box in boxes]
                _take_away_what_touches(doc, page, rects)
                for rect in rects:
                    page.add_redact_annot(rect, fill=COVER, cross_out=False)
                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(f"cannot cover the data: {error}") from error
        setattr(doc, COVERED, getattr(doc, COVERED, 0) + 1)
        return sorted(by_page)

    def undo(self, doc) -> list[int]:
        pages = put_back_pages(doc, self.copy)
        setattr(doc, COVERED, max(0, getattr(doc, COVERED, 0) - 1))
        return pages

    def to_dict(self) -> dict:
        copy = self.copy.to_dict() if self.copy is not None else None
        if copy is not None and len(self.copy.kept) > MAX_JOURNAL_COPY:
            copy["kept"] = ""
        return {
            "what": "cover_data",
            "areas": [[page, list(box)] for page, box in self.areas],
            "query": self.query,
            "copy": copy,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CoverData":
        copy = data.get("copy")
        return cls(
            tuple((int(page), tuple(float(v) for v in box)) for page, box in data["areas"]),
            str(data.get("query") or ""),
            DeletePages.from_dict(copy) if copy else None,
        )


def has_covered(doc) -> bool:
    """Whether something was covered in the open document since it was read."""
    return getattr(doc, COVERED, 0) > 0


def _big(box: Box) -> bool:
    x0, y0, x1, y1 = box
    return abs(x1 - x0) >= MIN_SIDE and abs(y1 - y0) >= MIN_SIDE


def _take_away_what_touches(doc, page, rects) -> None:
    """Notes, marks, links and fields over the boxes: they may say the same."""
    import pymupdf

    def touches(rect) -> bool:
        return any(rect.intersects(box) for box in rects)

    gone = set()
    for annotation in list(page.annots() or ()):
        if annotation.type[0] != pymupdf.PDF_ANNOT_REDACT and touches(annotation.rect):
            gone.add(annotation.xref)
            page.delete_annot(annotation)
    # A note's pop-up window is an annotation of its own that keeps pointing at
    # the note (and its text) from the page: it goes as well.
    for xref, *_rest in page.annot_xrefs():
        kind, parent = doc.xref_get_key(xref, "Parent")
        if kind == "xref" and int(parent.split()[0]) in gone:
            _unlist_annotation(doc, page, xref)
    for link in page.get_links():
        if touches(pymupdf.Rect(link["from"]) * page.derotation_matrix):
            page.delete_link(link)
    before = _field_roots(doc, [page.number])
    gone = False
    for widget in list(page.widgets() or ()):
        if touches(widget.rect):
            page.delete_widget(widget)
            gone = True
    if gone:  # their fields leave the form too, unless another page has them
        _drop_fields(doc, before - _field_roots(doc, range(doc.page_count)))


def _unlist_annotation(doc, page, xref: int) -> None:
    kind, value = doc.xref_get_key(page.xref, "Annots")
    if kind == "array":
        kept = [part for part in value.strip("[] ").split(" 0 R") if part.strip()]
        kept = [int(part) for part in kept if int(part) != xref]
        doc.xref_set_key(page.xref, "Annots", "[" + " ".join(f"{x} 0 R" for x in kept) + "]")


def find_text(doc, query: str) -> list[tuple[int, Box]]:
    """Every place where ``query`` is written, as seen on each page (capital
    letters or not)."""
    found = []
    for number in range(doc.page_count):
        page = doc[number]
        for rect in page.search_for(query.strip()):  # on the page not turned
            seen = (rect * page.rotation_matrix).normalize()
            found.append((number, (seen.x0, seen.y0, seen.x1, seen.y1)))
    return found


def cover_areas(areas) -> CoverData:
    """Cover these boxes: ((page, (x0, y0, x1, y1)), …), as seen on the page."""
    return CoverData(tuple((int(page), tuple(map(float, box))) for page, box in areas))


def cover_text(query: str) -> CoverData:
    """Cover every place where this text is written."""
    return CoverData(query=query)


register_reader("cover_data", CoverData.from_dict)
