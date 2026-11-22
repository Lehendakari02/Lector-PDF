"""A picture put on a page: one's handwritten signature or initials.

It is a standard picture annotation (a "stamp" with an image), so every
reader shows it, and it can be moved, resized, undone and taken away like
any drawing. Its picture keeps its see-through background.

On a turned page the picture is turned the other way inside the PDF, so it
is upright as the page is shown.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from app.core.commands import CommandError, find_annotation, register_reader

Rect = tuple[float, float, float, float]

SIGNATURE_WIDTH = 140.0  # points: how wide a signature is put at first
INITIALS_WIDTH = 48.0
MIN_HEIGHT = 6.0
_IMAGE = re.compile(r"(\d+)\s+0\s+R")
_TURNS = {90: 270, 180: 180, 270: 90}  # page rotation -> how the picture is turned


def _turned(png: bytes, degrees: int) -> bytes:
    """The picture turned clockwise by ``degrees`` (0, 90, 180 or 270)."""
    import pymupdf

    mode = {
        90: pymupdf.Pixmap.ROTATE_90,
        180: pymupdf.Pixmap.ROTATE_180,
        270: pymupdf.Pixmap.ROTATE_270,
    }.get(degrees % 360)
    if mode is None:
        return png
    return pymupdf.Pixmap(png).flip_rotate(mode).tobytes("png")


def fitted(png: bytes, x: float, y: float, width: float) -> Rect:
    """Where a picture goes, ``width`` points wide, centred on (x, y)."""
    from app.core.my_signature import size_of

    pixels_wide, pixels_high = size_of(png)
    height = max(MIN_HEIGHT, width * pixels_high / max(1, pixels_wide))
    return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)


@dataclass(frozen=True)
class AddPicture:
    """A picture (PNG) put in ``rect`` of a page, as the page is shown."""

    page: int
    rect: Rect
    png: bytes
    name: str
    what: str = ""  # how it is described to other readers ("Firma")

    def pages(self) -> list[int]:
        return [self.page]

    def apply(self, doc) -> list[int]:
        import pymupdf

        try:
            page = doc[self.page]
            if find_annotation(page, self.name) is None:
                rect = (pymupdf.Rect(self.rect) * page.derotation_matrix).normalize()
                if rect.is_empty:
                    raise CommandError("no room for the picture")
                picture = _turned(self.png, _TURNS.get(page.rotation % 360, 0))
                annotation = page.add_stamp_annot(rect, stamp=picture)
                # It fills the whole place given, not only a centred part.
                annotation.set_rect(rect)
                if self.what:
                    annotation.set_info(content=self.what)
                annotation.update()
                doc.xref_set_key(annotation.xref, "NM", f"({self.name})")
        except CommandError:
            raise
        except Exception as error:  # PyMuPDF raises several unrelated error types
            raise CommandError(f"cannot put the picture: {error}") from error
        return self.pages()

    def undo(self, doc) -> list[int]:
        try:
            page = doc[self.page]
            annotation = find_annotation(page, self.name)
            if annotation is not None:
                page.delete_annot(annotation)
        except Exception as error:
            raise CommandError(f"cannot remove it: {error}") from error
        return self.pages()

    def to_dict(self) -> dict:
        return {
            "what": "add_picture",
            "page": self.page,
            "rect": list(self.rect),
            "png": base64.b64encode(self.png).decode("ascii"),
            "name": self.name,
            "description": self.what,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AddPicture:
        x0, y0, x1, y1 = (float(value) for value in data["rect"])
        return cls(
            int(data["page"]),
            (x0, y0, x1, y1),
            base64.b64decode(data["png"]),
            str(data["name"]),
            str(data.get("description", "")),
        )


register_reader("add_picture", AddPicture.from_dict)


@dataclass(frozen=True)
class AddPictures:
    """One picture put in several places at once (one's initials on every
    page): one change, undone at once. The picture is kept once, not once for
    each page, so the journal stays small."""

    png: bytes
    places: tuple[tuple[int, Rect, str], ...]  # page, rect as shown, name
    what: str = ""

    def _each(self) -> list[AddPicture]:
        return [
            AddPicture(page, rect, self.png, name, self.what) for page, rect, name in self.places
        ]

    def pages(self) -> list[int]:
        return sorted({page for page, _rect, _name in self.places})

    def apply(self, doc) -> list[int]:
        done = []
        try:
            for picture in self._each():
                picture.apply(doc)
                done.append(picture)
        except CommandError:
            for picture in reversed(done):  # all or nothing
                picture.undo(doc)
            raise
        return self.pages()

    def undo(self, doc) -> list[int]:
        for picture in reversed(self._each()):
            picture.undo(doc)
        return self.pages()

    def to_dict(self) -> dict:
        return {
            "what": "add_pictures",
            "png": base64.b64encode(self.png).decode("ascii"),
            "places": [[page, list(rect), name] for page, rect, name in self.places],
            "description": self.what,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AddPictures:
        places = []
        for page, rect, name in data["places"]:
            x0, y0, x1, y1 = (float(value) for value in rect)
            places.append((int(page), (x0, y0, x1, y1), str(name)))
        return cls(base64.b64decode(data["png"]), tuple(places), str(data.get("description", "")))


register_reader("add_pictures", AddPictures.from_dict)


def puts_picture(order) -> bool:
    """Whether a change puts a new picture (a signature or initials)."""
    if isinstance(order, AddPicture | AddPictures):
        return True
    return any(puts_picture(part) for part in getattr(order, "orders", ()))


def picture_of(doc, page, annotation) -> bytes:
    """The picture of a picture annotation, upright as the page is shown
    (b"" if it has none that can be read)."""
    import pymupdf

    try:
        kind, appearance = doc.xref_get_key(annotation.xref, "AP/N")
        if kind != "xref":
            return b""
        form = int(appearance.split()[0])
        kind, images = doc.xref_get_key(form, "Resources/XObject")
        if kind != "dict":
            return b""
        found = _IMAGE.search(images)
        if found is None:
            return b""
        image = int(found.group(1))
        pix = pymupdf.Pixmap(doc, image)
        kind, mask = doc.xref_get_key(image, "SMask")
        if kind == "xref" and not pix.alpha:
            pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, int(mask.split()[0])))
        if pix.colorspace is None or pix.colorspace.n != 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        png = pix.tobytes("png")
        back = _TURNS.get(page.rotation % 360, 0)
        return _turned(png, (360 - back) % 360) if back else png
    except Exception:
        return b""
