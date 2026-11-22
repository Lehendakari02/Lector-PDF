"""The user's own bookmarks, kept in the outline of the PDF (standard).

They hang from one item at the top of the outline, "Mis marcadores", so any
reader (Adobe, Edge…) shows them in its bookmarks, apart from the document's
own index, which is never touched. Each one leads to a place of a page and
carries its name in a key of its own, so this program can rename or remove
it; other readers ignore that key.

Each change is an order (``AddBookmark``), so Deshacer, the journal and the
recovery work as with everything else; ``notes.Remove`` takes one away and
``notes.Replace`` renames it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.commands import CommandError, register_reader

NAME_KEY = "LectorPDFBookmark"  # on each bookmark: its name
GROUP_KEY = "LectorPDFBookmarks"  # on the item that holds them
GROUP_TITLE = "Mis marcadores"


def _ref(value: tuple[str, str]) -> int:
    """The object a key points to, or 0."""
    kind, text = value
    if kind != "xref":
        return 0
    try:
        return int(text.split()[0])
    except (ValueError, IndexError):
        return 0


def _outlines(doc, create: bool) -> int:
    catalog = doc.pdf_catalog()
    root = _ref(doc.xref_get_key(catalog, "Outlines"))
    if root or not create:
        return root
    root = doc.get_new_xref()
    doc.update_object(root, "<< /Type /Outlines /Count 0 >>")
    doc.xref_set_key(catalog, "Outlines", f"{root} 0 R")
    return root


def _children(doc, parent: int) -> list[int]:
    found, item, seen = [], _ref(doc.xref_get_key(parent, "First")), set()
    while item and item not in seen:
        seen.add(item)
        found.append(item)
        item = _ref(doc.xref_get_key(item, "Next"))
    return found


def _is_group(doc, xref: int) -> bool:
    return doc.xref_get_key(xref, GROUP_KEY)[1] == "true"


def _group(doc, create: bool, title: str = GROUP_TITLE) -> int:
    """The item that holds the bookmarks (made first of all, if wanted)."""
    root = _outlines(doc, create)
    if not root:
        return 0
    for item in _children(doc, root):
        if _is_group(doc, item):
            return item
    if not create:
        return 0
    import pymupdf

    group = doc.get_new_xref()
    doc.update_object(
        group, f"<< /Title {pymupdf.get_pdf_str(title)} /Parent {root} 0 R /{GROUP_KEY} true >>"
    )
    _link(doc, root, [group, *_children(doc, root)])
    return group


def _link(doc, parent: int, items: list[int]) -> None:
    """Make ``items`` the children of ``parent``, in this order."""
    for index, item in enumerate(items):
        doc.xref_set_key(item, "Parent", f"{parent} 0 R")
        doc.xref_set_key(item, "Prev", f"{items[index - 1]} 0 R" if index else "null")
        following = f"{items[index + 1]} 0 R" if index + 1 < len(items) else "null"
        doc.xref_set_key(item, "Next", following)
    if items:
        doc.xref_set_key(parent, "First", f"{items[0]} 0 R")
        doc.xref_set_key(parent, "Last", f"{items[-1]} 0 R")
    else:
        doc.xref_set_key(parent, "First", "null")
        doc.xref_set_key(parent, "Last", "null")
    _count(doc, parent, len(items))


def _count(doc, parent: int, children: int) -> None:
    """Keep /Count right enough for other readers: open items count theirs."""
    kind, text = doc.xref_get_key(parent, "Count")
    if parent == _outlines(doc, False):
        total = 0
        for item in _children(doc, parent):
            total += 1
            kind, value = doc.xref_get_key(item, "Count")
            if kind == "int" and int(value) > 0:
                total += int(value)
        doc.xref_set_key(parent, "Count", str(total))
        return
    doc.xref_set_key(parent, "Count", str(children) if children else "null")
    root = _outlines(doc, False)
    if root:
        _count(doc, root, len(_children(doc, root)))


def _find(doc, group: int, name: str) -> int:
    for item in _children(doc, group) if group else ():
        kind, value = doc.xref_get_key(item, NAME_KEY)
        if kind == "string" and value == name:
            return item
    return 0


def _places(doc) -> dict[int, tuple[int, float]]:
    """(page, top) every outline item leads to, by its object number."""
    places = {}
    for entry in doc.get_toc(simple=False):
        details = entry[3] if len(entry) > 3 else {}
        point = details.get("to")
        places[details.get("xref", 0)] = (entry[2] - 1, point.y if point is not None else 0.0)
    return places


@dataclass(frozen=True)
class AddBookmark:
    """Put a bookmark at a place of a page: ``top`` in points of the page as
    it is shown, from its top. Undoing it takes it away again."""

    page: int
    top: float
    title: str
    name: str
    group_title: str = GROUP_TITLE

    outline_change = True  # the outline is read again after it

    def pages(self) -> list[int]:
        return []  # no page looks different

    def apply(self, doc) -> list[int]:
        import pymupdf

        if not 0 <= self.page < doc.page_count:
            raise CommandError(f"no page {self.page}")
        if _find(doc, _group(doc, False), self.name):
            return []  # already there (recovered twice)
        group = _group(doc, True, self.group_title)
        page = doc[self.page]
        to_pdf = page.derotation_matrix * ~page.transformation_matrix
        target = pymupdf.Point(0, max(0.0, self.top)) * to_pdf
        item = doc.get_new_xref()
        doc.update_object(
            item,
            f"<< /Title {pymupdf.get_pdf_str(self.title)} /Parent {group} 0 R"
            f" /Dest [{page.xref} 0 R /XYZ {target.x:.2f} {target.y:.2f} null]"
            f" /{NAME_KEY} {pymupdf.get_pdf_str(self.name)} >>",
        )
        children = _children(doc, group)
        # In the order of the document, not of making them.
        known = _places(doc)
        here = (self.page, self.top)
        at = len(children)
        for index, child in enumerate(children):
            if known.get(child, (0, 0.0)) > here:
                at = index
                break
        children.insert(at, item)
        _link(doc, group, children)
        return []

    def undo(self, doc) -> list[int]:
        group = _group(doc, False)
        item = _find(doc, group, self.name)
        if not item:
            return []
        children = [child for child in _children(doc, group) if child != item]
        _link(doc, group, children)
        if not children:  # the last one: the group goes too
            root = _outlines(doc, False)
            _link(doc, root, [child for child in _children(doc, root) if child != group])
        return []

    def to_dict(self) -> dict:
        return {
            "what": "bookmark",
            "page": self.page,
            "top": self.top,
            "title": self.title,
            "name": self.name,
            "group_title": self.group_title,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AddBookmark:
        return cls(
            int(data["page"]),
            float(data["top"]),
            str(data["title"]),
            str(data["name"]),
            str(data.get("group_title", GROUP_TITLE)),
        )


register_reader("bookmark", AddBookmark.from_dict)


def changes_outline(order) -> bool:
    """Whether an order (or the one it removes or replaces) changes the outline."""
    if getattr(order, "outline_change", False):
        return True
    inner = [getattr(order, key, None) for key in ("order", "old", "new")]
    return any(part is not None and changes_outline(part) for part in inner)
