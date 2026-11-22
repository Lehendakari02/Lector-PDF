"""The list of everything put on a document: marks, notes, texts and drawings,
in reading order, each with its colour and the words it is about.

It feeds the annotations panel, where the user sees all of them, keeps only
those of one colour and goes to each one.
"""

from dataclasses import dataclass

from app.core.commands import HIGHLIGHT, MARKUP_KINDS, STRIKEOUT, UNDERLINE
from app.core.drawing import DRAWING_KINDS, INK, page_drawings
from app.core.notes import NOTE, TEXT_BOX, page_notes

Color = tuple[float, float, float]
Rect = tuple[float, float, float, float]

MARKS = "marks"
NOTES = "notes"
DRAWINGS = "drawings"
OTHERS = "others"

GROUPS = {
    **dict.fromkeys(MARKUP_KINDS, MARKS),
    NOTE: NOTES,
    TEXT_BOX: NOTES,
    **dict.fromkeys(DRAWING_KINDS, DRAWINGS),
}

LONGEST_TEXT = 300  # letters kept of what an entry says; the panel shows fewer


@dataclass(frozen=True)
class Entry:
    """One annotation of the document, as the panel lists it."""

    page: int
    kind: str  # a markup kind, NOTE, TEXT_BOX, a drawing kind, or "other"
    name: str  # how the page knows it (to pick it once there)
    rect: Rect  # the room it takes, as the page is shown
    color: Color
    text: str = ""  # the words marked, or what a note or a text says

    @property
    def group(self) -> str:
        return GROUPS.get(self.kind, OTHERS)


def color_key(color: Color) -> str:
    """A colour as "#rrggbb": two marks of the same colour have the same key."""
    return "#" + "".join(f"{round(max(0.0, min(1.0, part)) * 255):02x}" for part in color)


CLOSE = 0.02  # colours this near, part by part, are the same colour read back


def same_color(first: Color, second: Color) -> bool:
    """Whether two colours are the same one (a PDF keeps them a bit rounded)."""
    return all(abs(a - b) <= CLOSE for a, b in zip(first, second, strict=True))


def colors_of(entries: list[Entry]) -> list[Color]:
    """The colours used, each once, in the order they first appear."""
    found: list[Color] = []
    for entry in entries:
        if not any(same_color(entry.color, color) for color in found):
            found.append(entry.color)
    return found


def _short(text: str, longest: int | None = LONGEST_TEXT) -> str:
    text = " ".join(text.split())
    if longest is None or len(text) <= longest:
        return text
    return text[: longest - 1].rstrip() + "…"


def _marked_words(page, rects: tuple[Rect, ...], words: list) -> str:
    """The words under the rectangles of a mark (one per line), in order."""
    chosen = []
    matrix = page.rotation_matrix
    for word in words:
        x0, y0, x1, y1 = (_rect_of(word) * matrix).normalize()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(a <= cx <= c and b <= cy <= d for a, b, c, d in rects):
            chosen.append(word[4])
    return " ".join(chosen)


def _rect_of(word):
    import pymupdf

    return pymupdf.Rect(word[:4])


def page_entries(doc, page_number: int, longest: int | None = LONGEST_TEXT) -> list[Entry]:
    """The annotations of one page, from top to bottom (what they say cut to
    ``longest`` letters; None: whole, for the summary)."""
    page = doc[page_number]
    if page.first_annot is None:
        return []
    entries = []
    words = None  # read only when the page has a mark
    for drawn in page_drawings(doc, page_number):
        text = ""
        if drawn.kind in MARKUP_KINDS:
            if words is None:
                words = page.get_text("words", sort=True)
            text = _marked_words(page, drawn.rects, words)
        entries.append(
            Entry(
                page_number, drawn.kind, drawn.name, drawn.rect, drawn.color, _short(text, longest)
            )
        )
    for note in page_notes(doc, page_number):
        entries.append(
            Entry(
                page_number,
                note.kind,
                note.name,
                note.rect,
                note.color,
                _short(note.text, longest),
            )
        )
    entries.sort(key=lambda entry: (round(entry.rect[1]), entry.rect[0]))
    return entries


def document_entries(doc, longest: int | None = LONGEST_TEXT) -> list[Entry]:
    """Every annotation of the document, in reading order. A page that cannot
    be read is passed over."""
    entries: list[Entry] = []
    for number in range(doc.page_count):
        try:
            entries.extend(page_entries(doc, number, longest))
        except Exception:
            continue
    return entries


__all__ = [
    "DRAWINGS",
    "HIGHLIGHT",
    "INK",
    "MARKS",
    "NOTES",
    "OTHERS",
    "STRIKEOUT",
    "UNDERLINE",
    "Entry",
    "color_key",
    "colors_of",
    "same_color",
    "document_entries",
    "page_entries",
]
