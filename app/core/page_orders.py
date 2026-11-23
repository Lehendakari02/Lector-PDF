"""Organising the pages of a document: turning, moving, taking them away and
putting in pages of other documents or pictures.

Each one is an order like the others (it can be undone, redone and written in
the recovery journal). They change which page is where, so each one says how
with ``layout``: for every page before, where it is after (or None if it is
gone), and the sizes of the pages after. The window follows with that, without
reading the whole document again.

Taking pages away keeps a copy of them first (``prepared``), so that undo puts
them back as they were (with what was written on them, their form fields,
the links to them and the outline entries that pointed to them), even after
saving.
"""

import base64
from dataclasses import dataclass, replace

from app.core.commands import CommandError, register_reader

Size = tuple[float, float]
Mapping = list[int | None]  # for every page before: where it is after, or None

# A copy of the pages taken away bigger than this is not written in the
# recovery journal (it would make every change slow to write down): after a
# power cut, those pages could be taken away again but not put back.
MAX_JOURNAL_COPY = 32 * 1024 * 1024


def _clean_pages(pages, count: int | None = None) -> tuple[int, ...]:
    found = sorted({int(page) for page in pages})
    if not found:
        raise CommandError("no pages")
    if found[0] < 0 or (count is not None and found[-1] >= count):
        raise CommandError("a page that is not in the document")
    return tuple(found)


# ---- turning --------------------------------------------------------------


@dataclass(frozen=True)
class RotatePages:
    """Turn some pages ``by`` 90, 180 or 270 degrees, clockwise."""

    pages_: tuple[int, ...]
    by: int

    def pages(self) -> list[int]:
        return list(self.pages_)

    def layout(self, sizes: list[Size], undone: bool) -> tuple[Mapping, list[Size]]:
        new = list(sizes)
        if self.by % 180:
            for page in self.pages_:
                if 0 <= page < len(new):
                    new[page] = (new[page][1], new[page][0])
        return list(range(len(sizes))), new

    def _turn(self, doc, by: int) -> list[int]:
        if by % 90:
            raise CommandError(f"pages turn by quarters, not by {by}")
        pages = _clean_pages(self.pages_, doc.page_count)
        try:
            for number in pages:
                page = doc[number]
                page.set_rotation((page.rotation + by) % 360)
        except Exception as error:  # PyMuPDF raises several unrelated error types
            raise CommandError(f"cannot turn the page: {error}") from error
        return list(pages)

    def apply(self, doc) -> list[int]:
        return self._turn(doc, self.by)

    def undo(self, doc) -> list[int]:
        return self._turn(doc, -self.by)

    def to_dict(self) -> dict:
        return {"what": "rotate_pages", "pages": list(self.pages_), "by": self.by}

    @classmethod
    def from_dict(cls, data: dict) -> "RotatePages":
        return cls(_clean_pages(data["pages"]), int(data["by"]))


def rotate_pages(pages, by: int) -> RotatePages:
    return RotatePages(_clean_pages(pages), int(by) % 360)


# ---- moving ---------------------------------------------------------------


def moved_order(count: int, pages, to: int) -> list[int]:
    """The new order of the pages (the old number of each one, in order) when
    ``pages`` go together before the page that was at ``to`` (``count``:
    at the end), keeping their order."""
    chosen = list(_clean_pages(pages, count))
    rest = [page for page in range(count) if page not in chosen]
    place = sum(1 for page in rest if page < to)
    return rest[:place] + chosen + rest[place:]


@dataclass(frozen=True)
class MovePages:
    """Put ``pages`` together before the page that was at ``to`` (at the end
    when ``to`` is the number of pages)."""

    pages_: tuple[int, ...]
    to: int

    def pages(self) -> list[int]:
        return list(self.pages_)

    def _order(self, count: int) -> list[int]:
        return moved_order(count, self.pages_, max(0, min(count, self.to)))

    def first_after(self, count: int) -> int:
        """Where the first page moved is after moving them."""
        return self._order(count).index(self.pages_[0])

    def layout(self, sizes: list[Size], undone: bool) -> tuple[Mapping, list[Size]]:
        order = self._order(len(sizes))
        if undone:  # the page at place i goes back to order[i]
            mapping: Mapping = list(order)
            new = [sizes[0]] * len(sizes)
            for place, old in enumerate(order):
                new[old] = sizes[place]
            return mapping, new
        mapping = [0] * len(sizes)
        for place, old in enumerate(order):
            mapping[old] = place
        return mapping, [sizes[old] for old in order]

    def apply(self, doc) -> list[int]:
        order = self._order(doc.page_count)
        return self._select(doc, order)

    def undo(self, doc) -> list[int]:
        order = self._order(doc.page_count)
        back = [0] * len(order)
        for place, old in enumerate(order):
            back[old] = place
        return self._select(doc, back)

    @staticmethod
    def _select(doc, order: list[int]) -> list[int]:
        changed = [place for place, old in enumerate(order) if place != old]
        if changed:
            try:
                doc.select(order)
            except Exception as error:
                raise CommandError(f"cannot move the pages: {error}") from error
        return changed

    def to_dict(self) -> dict:
        return {"what": "move_pages", "pages": list(self.pages_), "to": self.to}

    @classmethod
    def from_dict(cls, data: dict) -> "MovePages":
        return cls(_clean_pages(data["pages"]), int(data["to"]))


def move_pages(pages, to: int) -> MovePages:
    return MovePages(_clean_pages(pages), int(to))


# ---- taking away ----------------------------------------------------------


@dataclass(frozen=True)
class DeletePages:
    """Take ``pages`` away. ``prepared`` keeps a copy of them first, to undo it."""

    pages_: tuple[int, ...]
    kept: bytes = b""  # a PDF with the pages taken away, as they were
    sizes: tuple[Size, ...] = ()  # their sizes, as shown
    links: tuple = ()  # (page, link) of links on them or to them
    outline: tuple = ()  # the outline before, if some entry pointed to them
    fields: tuple = ()  # the names of their form fields, in order

    def pages(self) -> list[int]:
        return list(self.pages_)

    def layout(self, sizes: list[Size], undone: bool) -> tuple[Mapping, list[Size]]:
        taken = set(self.pages_)
        if undone:
            total = len(sizes) + len(self.pages_)
            rest = [page for page in range(total) if page not in taken]
            new: list[Size] = [(0.0, 0.0)] * total
            for place, page in enumerate(rest):
                new[page] = sizes[place]
            for page, size in zip(self.pages_, self.sizes or (), strict=False):
                new[page] = size
            for page in self.pages_:  # not known: as the page before or after
                if new[page] == (0.0, 0.0):
                    new[page] = sizes[min(page, len(sizes) - 1)] if sizes else (595.0, 842.0)
            return list(rest), new
        mapping: Mapping = []
        left = 0
        for page in range(len(sizes)):
            if page in taken:
                mapping.append(None)
            else:
                mapping.append(left)
                left += 1
        return mapping, [size for page, size in enumerate(sizes) if page not in taken]

    def prepared(self, doc) -> "DeletePages":
        """The same order, with a copy of what it takes away."""
        import pymupdf

        pages = _clean_pages(self.pages_, doc.page_count)
        if len(pages) >= doc.page_count:
            raise CommandError("a document cannot be left without pages")
        taken = set(pages)
        try:
            copy = pymupdf.open()
            for page in pages:
                copy.insert_pdf(doc, from_page=page, to_page=page)
            kept = copy.tobytes(garbage=3, deflate=True)
            copy.close()
            links = []
            for number in range(doc.page_count):
                for link in doc[number].get_links():
                    if number in taken or link.get("page") in taken:
                        links.append((number, _plain(link)))
            outline = doc.get_toc(simple=False)
            points_there = any(entry[2] - 1 in taken for entry in outline)
            fields = tuple(
                tuple(widget.field_name or "" for widget in doc[page].widgets() or ())
                for page in pages
            )
        except Exception as error:
            raise CommandError(f"cannot keep a copy of the pages: {error}") from error
        return replace(
            self,
            pages_=pages,
            kept=kept,
            sizes=tuple((doc[page].rect.width, doc[page].rect.height) for page in pages),
            links=tuple(links),
            outline=tuple(map(_plain, outline)) if points_there else (),
            fields=fields,
        )

    def apply(self, doc) -> list[int]:
        pages = _clean_pages(self.pages_, doc.page_count)
        if len(pages) >= doc.page_count:
            raise CommandError("a document cannot be left without pages")
        try:
            taken = _field_roots(doc, pages)
            doc.delete_pages(list(pages))
            # The engine leaves their fields in the form, belonging to no page:
            # a form that still asks for them. Those of no other page go too.
            _drop_fields(doc, taken - _field_roots(doc, range(doc.page_count)))
        except Exception as error:
            raise CommandError(f"cannot take the pages away: {error}") from error
        return list(range(pages[0], doc.page_count))

    def undo(self, doc) -> list[int]:
        import pymupdf

        if not self.kept:
            raise CommandError("no copy of the pages was kept")
        try:
            copy = pymupdf.open("pdf", self.kept)
        except Exception as error:
            raise CommandError(f"the copy of the pages cannot be read: {error}") from error
        if copy.page_count != len(self.pages_):
            raise CommandError("the copy does not have those pages")
        try:
            with copy:
                for index, page in enumerate(self.pages_):  # in order: each at its place
                    doc.insert_pdf(copy, from_page=index, to_page=index, start_at=page)
            self._mend(doc)
        except Exception as error:
            raise CommandError(f"cannot put the pages back: {error}") from error
        return list(range(self.pages_[0], doc.page_count))

    def _mend(self, doc) -> None:
        """What putting the pages back loses: links, outline entries, field names."""
        import pymupdf

        for page in self.pages_:  # their own links come again below, all of them
            shown = doc[page]
            for link in shown.get_links():
                shown.delete_link(link)
        for number, link in self.links:
            if 0 <= number < doc.page_count:
                doc[number].insert_link(_link_back(link))
        if self.outline:
            doc.set_toc([_entry_back(entry) for entry in self.outline])
        # The engine renames the fields it copies («nombre [46]»): they get
        # their own names back.
        names = {name.split(".")[0] for page in self.fields for name in page if name}
        for root in _field_roots(doc, self.pages_):
            kind, value = doc.xref_get_key(root, "T")
            if kind != "string":
                continue
            plain, _, number = value.rpartition(" [")
            if plain in names and number.endswith("]") and number[:-1].isdigit():
                doc.xref_set_key(root, "T", pymupdf.get_pdf_str(plain))

    def to_dict(self) -> dict:
        kept = self.kept if len(self.kept) <= MAX_JOURNAL_COPY else b""
        return {
            "what": "delete_pages",
            "pages": list(self.pages_),
            "kept": base64.b64encode(kept).decode("ascii"),
            "sizes": [list(size) for size in self.sizes],
            "links": [[number, link] for number, link in self.links],
            "outline": list(self.outline),
            "fields": [list(names) for names in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeletePages":
        return cls(
            _clean_pages(data["pages"]),
            base64.b64decode(data.get("kept") or ""),
            tuple((float(w), float(h)) for w, h in data.get("sizes") or ()),
            tuple((int(number), dict(link)) for number, link in data.get("links") or ()),
            tuple(data.get("outline") or ()),
            tuple(tuple(str(name) for name in names) for names in data.get("fields") or ()),
        )


def delete_pages(pages) -> DeletePages:
    return DeletePages(_clean_pages(pages))


# ---- putting pages in -----------------------------------------------------

A4 = (595.0, 842.0)
IMAGE_TYPES = ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "gif", "webp")


class SourceNeedsPassword(CommandError):
    """A PDF to take pages from asks for a password."""

    def __init__(self, path) -> None:
        super().__init__(f"{path} asks for a password")
        self.path = path


@dataclass(frozen=True)
class InsertPages:
    """Pages of other documents (``kept``, a PDF with them) put at place
    ``at``: the first of them becomes that page."""

    at: int
    kept: bytes
    sizes: tuple[Size, ...]  # of the pages put, as shown

    def pages(self) -> list[int]:
        return list(range(self.at, self.at + len(self.sizes)))

    def layout(self, sizes: list[Size], undone: bool) -> tuple[Mapping, list[Size]]:
        count = len(self.sizes)
        if undone:
            mapping: Mapping = [
                page if page < self.at else (None if page < self.at + count else page - count)
                for page in range(len(sizes))
            ]
            return mapping, sizes[: self.at] + sizes[self.at + count :]
        mapping = [page if page < self.at else page + count for page in range(len(sizes))]
        return mapping, sizes[: self.at] + list(self.sizes) + sizes[self.at :]

    def apply(self, doc) -> list[int]:
        import pymupdf

        if not 0 <= self.at <= doc.page_count:
            raise CommandError(f"no place {self.at} for pages")
        try:
            with pymupdf.open("pdf", self.kept) as source:
                if source.page_count != len(self.sizes):
                    raise CommandError("the pages to put are not all there")
                doc.insert_pdf(source, start_at=self.at)
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(f"cannot put the pages: {error}") from error
        return list(range(self.at, doc.page_count))

    def undo(self, doc) -> list[int]:
        last = self.at + len(self.sizes) - 1
        if last >= doc.page_count or len(self.sizes) >= doc.page_count:
            raise CommandError("the pages put are not there")
        doc.delete_pages(from_page=self.at, to_page=last)
        return list(range(self.at, doc.page_count))

    def to_dict(self) -> dict:
        return {
            "what": "insert_pages",
            "at": self.at,
            "kept": base64.b64encode(self.kept).decode("ascii"),
            "sizes": [list(size) for size in self.sizes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InsertPages":
        return cls(
            int(data["at"]),
            base64.b64decode(data["kept"]),
            tuple((float(w), float(h)) for w, h in data["sizes"]),
        )


def is_image(path) -> bool:
    from pathlib import Path

    return Path(path).suffix.lower().lstrip(".") in IMAGE_TYPES


def _image_page(result, path) -> None:
    """A page the size of an A4 sheet (turned if the picture is wider than
    tall) with the picture filling it, as a scanner would."""
    import pymupdf

    with pymupdf.open(path) as picture:
        rect = picture[0].rect
    width, height = A4 if rect.height >= rect.width else (A4[1], A4[0])
    page = result.new_page(width=width, height=height)
    page.insert_image(page.rect, filename=str(path), keep_proportion=True)


def insert_pages(at: int, sources) -> InsertPages:
    """The order that puts at ``at`` the pages of ``sources``: each one is a
    path (a PDF, all its pages; or a picture, one page) or a (path, password)
    pair, or (path, password, pages) to take only those pages (from 0)."""
    import pymupdf

    result = pymupdf.open()
    try:
        for source in sources:
            parts = list(source) if isinstance(source, tuple) else [source]
            path, password, chosen = (parts + [None, None])[:3]
            if is_image(path):
                try:
                    _image_page(result, path)
                except Exception as error:
                    raise CommandError(f"{path} cannot be read: {error}") from error
                continue
            try:
                doc = pymupdf.open(path, filetype="pdf")
            except Exception as error:
                raise CommandError(f"{path} cannot be read: {error}") from error
            with doc:
                if doc.needs_pass and not (password and doc.authenticate(password)):
                    raise SourceNeedsPassword(path)
                pages = list(range(doc.page_count)) if chosen is None else list(chosen)
                for page in pages:
                    if 0 <= page < doc.page_count:
                        result.insert_pdf(doc, from_page=page, to_page=page)
        if result.page_count == 0:
            raise CommandError("no pages to put")
        sizes = tuple((page.rect.width, page.rect.height) for page in result)
        kept = result.tobytes(garbage=3, deflate=True)
    finally:
        result.close()
    return InsertPages(int(at), kept, sizes)


def _field_roots(doc, pages) -> set[int]:
    """The form fields (the top of each, by number) with a box on those pages."""
    import pymupdf

    roots = set()
    for number in pages:
        page = doc[number]
        for xref in page.annot_xrefs():
            if xref[1] != pymupdf.PDF_ANNOT_WIDGET:
                continue
            root, seen = xref[0], set()
            while root not in seen:
                seen.add(root)
                kind, parent = doc.xref_get_key(root, "Parent")
                if kind != "xref":
                    break
                root = int(parent.split()[0])
            roots.add(root)
    return roots


def _drop_fields(doc, roots: set[int]) -> None:
    if not roots:
        return
    kind, value = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")
    if kind != "array":
        return
    parts = value.strip("[] ").split()
    refs = [" ".join(parts[i : i + 3]) for i in range(0, len(parts) - 2, 3)]
    if len(refs) * 3 != len(parts):
        return  # not a plain list of references: left as it is
    left = [ref for ref in refs if int(ref.split()[0]) not in roots]
    doc.xref_set_key(doc.pdf_catalog(), "AcroForm/Fields", f"[{' '.join(left)}]")


def _plain(value):
    """A value of PyMuPDF (points, rectangles, dictionaries) as plain lists and
    dictionaries, to be written in the journal."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items() if key not in ("xref", "id")}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if hasattr(value, "x") and hasattr(value, "y") and not hasattr(value, "x1"):
        return [float(value.x), float(value.y)]
    if hasattr(value, "x0") and hasattr(value, "y1"):
        return [float(value.x0), float(value.y0), float(value.x1), float(value.y1)]
    return value


def _link_back(link: dict) -> dict:
    import pymupdf

    link = dict(link)
    link["from"] = pymupdf.Rect(link["from"])
    if isinstance(link.get("to"), list):
        link["to"] = pymupdf.Point(link["to"])
    return link


def _entry_back(entry: list) -> list:
    import pymupdf

    entry = list(entry)
    if len(entry) > 3 and isinstance(entry[3], dict):
        details = dict(entry[3])
        if isinstance(details.get("to"), list):
            details["to"] = pymupdf.Point(details["to"])
        entry[3] = details
    return entry


register_reader("rotate_pages", RotatePages.from_dict)
register_reader("move_pages", MovePages.from_dict)
register_reader("delete_pages", DeletePages.from_dict)
register_reader("insert_pages", InsertPages.from_dict)
