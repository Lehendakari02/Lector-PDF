"""Links from one document to a place of another (standard /GoToR links).

A link is a /Link annotation over some words. Its action opens another PDF,
written as a path *relative* to the folder of the document (so the link works
on any computer with the same folders), at a page and a height:

    << /Subtype /Link /Rect [...] /Border [0 0 0]
       /A << /S /GoToR /F (../Leyes/Constitucion.pdf) /D [13 /XYZ null 640 null] >>
       /LectorPDFLink (name) >>

Adobe follows these links; browsers usually do not, but the PDF stays valid.
Links made by other programs are read too (they can be followed).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.commands import CommandError, register_reader

NAME_KEY = "LectorPDFLink"
Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class DocLink:
    """A link of a page to another document, as this program reads it."""

    name: str  # "" for one made by another program
    rect: Rect  # on the page as shown
    file: str  # as written in the PDF (relative, with "/")
    page: int  # of the other document, from 0
    top: float | None  # height on that page, PDF points from the bottom, or None


def relative_file(source: str | Path, target: str | Path) -> str:
    """How ``target`` is written in a link of ``source``: relative to its
    folder, with "/". On another drive (Windows) only the whole path works."""
    source, target = Path(source).absolute(), Path(target).absolute()
    try:
        relative = os.path.relpath(target, source.parent)
    except ValueError:
        return target.as_posix()
    return PurePosixPath(*Path(relative).parts).as_posix()


def resolve(source: str | Path, file: str) -> Path:
    """The file a link of ``source`` points to."""
    written = Path(file.replace("\\", "/"))
    if written.is_absolute() or (len(file) > 1 and file[1] == ":"):
        return Path(file)
    return (Path(source).absolute().parent / written).resolve()


def _string(doc, xref: int, key: str) -> str:
    kind, value = doc.xref_get_key(xref, key)
    return value if kind == "string" else ""


def _annots(doc, page) -> tuple[str, int, list[int]]:
    """Where the page keeps its annotations: ("array"|"xref"|"none", the
    array's object, the annotation objects)."""
    kind, value = doc.xref_get_key(page.xref, "Annots")
    if kind == "xref":
        holder = int(value.split()[0])
        text = doc.xref_object(holder, compressed=True)
    elif kind == "array":
        holder, text = 0, value
    else:
        return "none", 0, []
    numbers = text.strip().strip("[]").split()
    found = []
    for index in range(0, len(numbers) - 2, 3):
        if numbers[index + 2] == "R" and numbers[index].isdigit():
            found.append(int(numbers[index]))
    return kind, holder, found


def _set_annots(doc, page, kind: str, holder: int, items: list[int]) -> None:
    array = "[" + " ".join(f"{item} 0 R" for item in items) + "]"
    if kind == "xref":
        doc.update_object(holder, array)
    else:
        doc.xref_set_key(page.xref, "Annots", array if items else "null")


def _target(doc, xref: int) -> tuple[str, int, float | None] | None:
    if _string_or_name(doc, xref, "Subtype") != "Link":
        return None
    if _string_or_name(doc, xref, "A/S") != "GoToR":
        return None
    file = _string(doc, xref, "A/F/UF") or _string(doc, xref, "A/F/F") or _string(doc, xref, "A/F")
    if not file:
        return None
    kind, value = doc.xref_get_key(xref, "A/D")
    page, top = 0, None
    if kind == "array":
        parts = value.strip("[]").replace("/", " /").split()
        if parts and parts[0].lstrip("-").isdigit():
            page = max(0, int(parts[0]))
        if len(parts) > 3 and parts[1] == "/XYZ":
            try:
                top = float(parts[3])
            except ValueError:
                top = None
    return file, page, top


def _string_or_name(doc, xref: int, key: str) -> str:
    kind, value = doc.xref_get_key(xref, key)
    if kind == "name":
        return value.lstrip("/")
    return value if kind == "string" else ""


def _shown_rect(doc, page, xref: int) -> Rect | None:
    import pymupdf

    kind, value = doc.xref_get_key(xref, "Rect")
    if kind != "array":
        return None
    try:
        x0, y0, x1, y1 = (float(n) for n in value.strip("[]").split())
    except ValueError:
        return None
    to_shown = page.transformation_matrix * page.rotation_matrix
    rect = pymupdf.Rect(x0, y0, x1, y1) * to_shown
    rect.normalize()
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def page_doc_links(doc, number: int) -> list[DocLink]:
    """The links of a page to other documents, in reading order."""
    page = doc[number]
    found = []
    for xref in _annots(doc, page)[2]:
        try:
            target = _target(doc, xref)
            rect = _shown_rect(doc, page, xref) if target else None
        except Exception:
            continue
        if target is None or rect is None:
            continue
        found.append(DocLink(_string(doc, xref, NAME_KEY), rect, *target))
    found.sort(key=lambda link: (round(link.rect[1]), link.rect[0]))
    return found


def _pdf_string(text: str) -> str:
    import pymupdf

    return pymupdf.get_pdf_str(text)


def _file_spec(file: str) -> str:
    """The other file as a file specification: /UF keeps any letter (ñ, tildes)."""
    return f"<< /Type /Filespec /F {_pdf_string(file)} /UF {_pdf_string(file)} >>"


@dataclass(frozen=True)
class AddDocLink:
    """A link over some words of a page (rectangles as shown) to a place of
    another document. Undoing it takes it away."""

    page: int
    rects: tuple[Rect, ...]
    file: str
    target_page: int
    target_top: float | None  # PDF points from the bottom of that page
    name: str

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        if not 0 <= self.page < doc.page_count:
            raise CommandError(f"no page {self.page}")
        if not self.rects or not self.file:
            raise CommandError("nothing to link")
        page = doc[self.page]
        kind, holder, items = _annots(doc, page)
        if any(_string(doc, item, NAME_KEY) == self.name for item in items):
            return [self.page]  # already there (recovered twice)
        to_pdf = page.derotation_matrix * ~page.transformation_matrix
        top = "null" if self.target_top is None else f"{self.target_top:.2f}"
        destination = f"[{max(0, self.target_page)} /XYZ null {top} null]"
        for rect in self.rects:
            box = pymupdf.Rect(rect) * to_pdf
            box.normalize()
            xref = doc.get_new_xref()
            doc.update_object(
                xref,
                f"<< /Type /Annot /Subtype /Link /Rect [{box.x0:.2f} {box.y0:.2f} "
                f"{box.x1:.2f} {box.y1:.2f}] /Border [0 0 0] /P {page.xref} 0 R"
                f" /A << /S /GoToR /F {_file_spec(self.file)} /D {destination}"
                f" /NewWindow false >> /{NAME_KEY} {_pdf_string(self.name)} >>",
            )
            items.append(xref)
        _set_annots(doc, page, kind if kind != "none" else "array", holder, items)
        return [self.page]

    def undo(self, doc) -> list[int]:
        if not 0 <= self.page < doc.page_count:
            return []
        page = doc[self.page]
        kind, holder, items = _annots(doc, page)
        kept = [item for item in items if _string(doc, item, NAME_KEY) != self.name]
        if len(kept) != len(items):
            _set_annots(doc, page, kind, holder, kept)
        return [self.page]

    def to_dict(self) -> dict:
        return {
            "what": "doc_link",
            "page": self.page,
            "rects": [list(rect) for rect in self.rects],
            "file": self.file,
            "target_page": self.target_page,
            "target_top": self.target_top,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AddDocLink:
        top = data.get("target_top")
        return cls(
            int(data["page"]),
            tuple(tuple(float(n) for n in rect) for rect in data["rects"]),
            str(data["file"]),
            int(data["target_page"]),
            None if top is None else float(top),
            str(data["name"]),
        )


@dataclass(frozen=True)
class ChangeLinkFile:
    """Every link of the document to ``old_file`` now goes to ``new_file`` (the other
    document was moved or renamed). Undoing it puts ``old_file`` back."""

    old_file: str  # not "new": that name means "an annotation put" to the view
    new_file: str

    def pages(self) -> list[int]:
        return []  # nothing looks different

    def _swap(self, doc, before: str, after: str) -> list[int]:
        changed = []
        for number in range(doc.page_count):
            page = doc[number]
            for xref in _annots(doc, page)[2]:
                target = _target(doc, xref)
                if target is None or target[0] != before:
                    continue
                doc.xref_set_key(xref, "A/F", _file_spec(after))
                if number not in changed:
                    changed.append(number)
        return changed  # their links are read again

    def apply(self, doc) -> list[int]:
        if not self.new_file:
            raise CommandError("no new file")
        return self._swap(doc, self.old_file, self.new_file)

    def undo(self, doc) -> list[int]:
        return self._swap(doc, self.new_file, self.old_file)

    def to_dict(self) -> dict:
        return {"what": "link_file", "old": self.old_file, "new": self.new_file}

    @classmethod
    def from_dict(cls, data: dict) -> ChangeLinkFile:
        return cls(str(data["old"]), str(data["new"]))


register_reader("doc_link", AddDocLink.from_dict)
register_reader("link_file", ChangeLinkFile.from_dict)

LINKS_CHANGE = (AddDocLink, ChangeLinkFile)
