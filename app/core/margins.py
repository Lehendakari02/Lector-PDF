"""Wider pages, with blank room on a side (or below) to write notes in.

The page boxes of the PDF (/MediaBox and /CropBox) grow: the content stays
where it is and the new room is blank, so every reader shows it the same.
Growing on the left or at the top moves the whole content right or down on
the page as shown, but notes, marks and links keep their place over the text
because they are written in the same coordinates as the content.

Sides are those of the page as it is shown: on a page kept turned
(``/Rotate``) "the right" is another side of the boxes, worked out here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.commands import CommandError, register_reader

MARGINS_KEY = "LectorPDFMargins"  # on each page: the names of the margins it has
BOXES = ("MediaBox", "CropBox", "TrimBox", "BleedBox", "ArtBox")
LARGEST = 14400.0  # points: the biggest page a PDF reader is sure to take
POINTS_PER_CM = 72 / 2.54

# Shown side → side of the page before its turn, for each turn (clockwise).
# Sides are written left, top, right, bottom.
_SIDES = {
    0: (0, 1, 2, 3),
    90: (3, 0, 1, 2),
    180: (2, 3, 0, 1),
    270: (1, 2, 3, 0),
}


def cm(value: float) -> float:
    return value * POINTS_PER_CM


def unturned(rotation: int, shown: tuple[float, float, float, float]) -> tuple[float, ...]:
    """Room on each side (left, top, right, bottom) of the page as shown, as
    room on each side of the page before its turn."""
    order = _SIDES.get(rotation % 360, _SIDES[0])
    room = [0.0, 0.0, 0.0, 0.0]
    for side, amount in enumerate(shown):
        room[order[side]] = amount
    return tuple(room)


def _names(doc, page) -> list[str]:
    kind, value = doc.xref_get_key(page.xref, MARGINS_KEY)
    if kind != "string" or not value:
        return []
    return value.split()


def _set_names(doc, page, names: list[str]) -> None:
    doc.xref_set_key(page.xref, MARGINS_KEY, f"({' '.join(names)})" if names else "null")


def _box(doc, page, key: str):
    kind, value = doc.xref_get_key(page.xref, key)
    if kind != "array":
        return None
    try:
        return [float(n) for n in value.strip("[]").split()]
    except ValueError:
        return None


def _grow(doc, page, room: tuple[float, ...], sign: float) -> None:
    """Make the boxes of a page bigger (sign 1) or smaller (-1) by ``room``
    (left, top, right, bottom, before the page's turn)."""
    left, top, right, bottom = (sign * amount for amount in room)
    media = page.mediabox
    # The page as PyMuPDF has it (its own /MediaBox may be inherited).
    for key in BOXES:
        box = _box(doc, page, key)
        if box is None:
            if key == "MediaBox":
                box = [media.x0, media.y0, media.x1, media.y1]
            else:
                continue
        x0, y0, x1, y1 = (
            min(box[0], box[2]),
            min(box[1], box[3]),
            max(box[0], box[2]),
            max(box[1], box[3]),
        )
        x0, y0, x1, y1 = x0 - left, y0 - bottom, x1 + right, y1 + top  # PDF: y goes up
        doc.xref_set_key(page.xref, key, f"[{x0:.4f} {y0:.4f} {x1:.4f} {y1:.4f}]")


@dataclass(frozen=True)
class AddMargin:
    """Blank room on some pages, in points, on sides of the page as shown."""

    pages_: tuple[int, ...]
    left: float
    right: float
    bottom: float
    name: str

    text_change = True  # the letters move with the content (a margin on the left)

    def pages(self) -> list[int]:
        return sorted(set(self.pages_))

    def size_change(self, undone: bool) -> dict[int, tuple[float, float]]:
        """How much wider and taller each page becomes (smaller when undone)."""
        sign = -1.0 if undone else 1.0
        return {
            page: (sign * (self.left + self.right), sign * self.bottom) for page in self.pages()
        }

    def apply(self, doc) -> list[int]:
        if min(self.left, self.right, self.bottom) < 0 or not (
            self.left or self.right or self.bottom
        ):
            raise CommandError("no room to add")
        done = []
        for number in self.pages():
            if not 0 <= number < doc.page_count:
                raise CommandError(f"no page {number}")
            page = doc[number]
            names = _names(doc, page)
            if self.name in names:
                continue  # already there (recovered twice)
            width = page.rect.width + self.left + self.right
            height = page.rect.height + self.bottom
            if width > LARGEST or height > LARGEST:
                for undone in done:  # all or nothing
                    self._shrink(doc, undone)
                raise CommandError("the page would be too big")
            room = unturned(page.rotation, (self.left, 0.0, self.right, self.bottom))
            _grow(doc, page, room, 1.0)
            _set_names(doc, doc[number], [*names, self.name])
            done.append(number)
        return self.pages()

    def _shrink(self, doc, number: int) -> None:
        page = doc[number]
        names = _names(doc, page)
        if self.name not in names:
            return
        room = unturned(page.rotation, (self.left, 0.0, self.right, self.bottom))
        _grow(doc, page, room, -1.0)
        names.remove(self.name)
        _set_names(doc, doc[number], names)

    def undo(self, doc) -> list[int]:
        for number in self.pages():
            if 0 <= number < doc.page_count:
                self._shrink(doc, number)
        return self.pages()

    def to_dict(self) -> dict:
        return {
            "what": "margin",
            "pages": list(self.pages_),
            "left": self.left,
            "right": self.right,
            "bottom": self.bottom,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AddMargin:
        return cls(
            tuple(int(page) for page in data["pages"]),
            float(data["left"]),
            float(data["right"]),
            float(data["bottom"]),
            str(data["name"]),
        )


register_reader("margin", AddMargin.from_dict)


def size_change(order, undone: bool = False) -> dict[int, tuple[float, float]]:
    """How an order (or the one it takes away) changes the size of pages."""
    if hasattr(order, "size_change"):
        return order.size_change(undone)
    inner = getattr(order, "order", None)  # notes.Remove: the other way round
    if inner is not None and type(order).__name__ == "Remove":
        return size_change(inner, not undone)
    return {}
