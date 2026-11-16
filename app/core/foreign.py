"""Annotations made by other programs (Edge, Adobe…): they can be taken away.

They are not changed, moved or copied: what another program made is kept as it
is, and only taken off the page or put back. Taking one away removes it from
its page's list of annotations; the object itself is left untouched in the
document, so Deshacer puts back exactly what was there, with its look, its
pop-up and the replies to it.

Never touched: form fields and signatures (``Widget``), links, pop-ups on
their own (they go with their annotation) and areas marked to be blacked out.
Those are not read as annotations at all.
"""

import re
from dataclasses import dataclass

from app.core.commands import CommandError, register_reader
from app.core.search import Rect

OTHER = "other"  # what is not read as a note, a text, a drawing or a mark
KEY_PREFIX = "#"  # the name an annotation of another program goes by here
# Kinds of annotation that are read only as "something there", to be taken away.
OTHER_TYPES = frozenset(
    {"Polygon", "PolyLine", "Squiggly", "Stamp", "Caret", "FileAttachment", "Sound"}
)
_REFERENCE = re.compile(r"(\d+)\s+(\d+)\s+R")


def key_of(xref: int) -> str:
    return f"{KEY_PREFIX}{xref}"


@dataclass(frozen=True)
class Foreign:
    """An annotation of another program, as it is on its page.

    Applying it puts it on the page (back); undoing it takes it away. So
    ``notes.Remove(foreign)`` takes it away, and Deshacer puts it back.
    """

    page: int
    xrefs: tuple[int, ...]  # the annotation, then its pop-up and the replies to it
    subtype: str  # what it is ("Highlight", "Ink"…): checked before touching it
    rect: Rect  # where it is, as the page is shown

    @property
    def name(self) -> str:
        return key_of(self.xrefs[0])

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        self._check(doc)
        listed, holder = _annotations(doc, self.page)
        there = {xref for xref, _ in listed}
        listed += [(xref, 0) for xref in self.xrefs if xref not in there]
        _write(doc, self.page, listed, holder)
        return self.pages()

    def undo(self, doc) -> list[int]:
        self._check(doc)
        listed, holder = _annotations(doc, self.page)
        if self.xrefs[0] not in {xref for xref, _ in listed}:
            raise CommandError("the annotation is not on its page")
        gone = set(self.xrefs)
        _write(doc, self.page, [entry for entry in listed if entry[0] not in gone], holder)
        return self.pages()

    def _check(self, doc) -> None:
        if not 0 <= self.page < doc.page_count:
            raise CommandError(f"no page {self.page}")
        xref = self.xrefs[0]
        if not 0 < xref < doc.xref_length() or _subtype(doc, xref) != self.subtype:
            raise CommandError("that annotation is not in this document")

    def to_dict(self) -> dict:
        return {
            "what": "foreign",
            "page": self.page,
            "xrefs": list(self.xrefs),
            "subtype": self.subtype,
            "rect": list(self.rect),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Foreign":
        xrefs = tuple(int(xref) for xref in data["xrefs"])
        if not xrefs:
            raise ValueError("no annotation")
        x0, y0, x1, y1 = (float(value) for value in data["rect"])
        return cls(int(data["page"]), xrefs, str(data["subtype"]), (x0, y0, x1, y1))


register_reader("foreign", Foreign.from_dict)


@dataclass(frozen=True)
class PageFamilies:
    """What is on a page's list, and which annotations answer which."""

    listed: frozenset[int]
    replies: dict[int, tuple[int, ...]]  # an annotation -> the ones that answer it


def families_of(doc, page_number: int) -> PageFamilies:
    """Read once for a page, for every annotation of it."""
    listed = [xref for xref, _ in _annotations(doc, page_number)[0]]
    replies: dict[int, list[int]] = {}
    for xref in listed:
        kind, value = doc.xref_get_key(xref, "IRT")
        if kind == "xref":
            replies.setdefault(int(value.split()[0]), []).append(xref)
    return PageFamilies(frozenset(listed), {k: tuple(v) for k, v in replies.items()})


def foreign_of(
    doc, page_number: int, annotation, rect: Rect, families: PageFamilies | None = None
) -> Foreign:
    """The order for an annotation of another program, with its family:
    its pop-up and the replies to it (with theirs)."""
    families = families or families_of(doc, page_number)
    xref = annotation.xref
    family = [xref]

    def with_popup(member: int) -> None:
        kind, value = doc.xref_get_key(member, "Popup")
        if kind == "xref":
            popup = int(value.split()[0])
            if popup in families.listed and popup not in family:
                family.append(popup)

    with_popup(xref)
    for reply in families.replies.get(xref, ()):
        if reply not in family:
            family.append(reply)  # a reply to it: it goes with it
            with_popup(reply)
    return Foreign(page_number, tuple(family), annotation.type[1], rect)


def _subtype(doc, xref: int) -> str:
    kind, value = doc.xref_get_key(xref, "Subtype")
    return value.lstrip("/") if kind == "name" else ""


def _annotations(doc, page_number: int) -> tuple[list[tuple[int, int]], int | None]:
    """The page's list of annotations, (xref, generation) each, and the object
    that holds the list when it is kept apart from the page (else None)."""
    page_xref = doc.page_xref(page_number)
    kind, value = doc.xref_get_key(page_xref, "Annots")
    holder = None
    if kind == "xref":
        holder = int(value.split()[0])
        value = doc.xref_object(holder, compressed=True)
    elif kind != "array":
        return [], None
    return [(int(x), int(g)) for x, g in _REFERENCE.findall(value)], holder


def _write(doc, page_number: int, listed: list[tuple[int, int]], holder: int | None) -> None:
    text = "[" + " ".join(f"{xref} {generation} R" for xref, generation in listed) + "]"
    if holder is not None:
        doc.update_object(holder, text)
    else:
        doc.xref_set_key(doc.page_xref(page_number), "Annots", text)
