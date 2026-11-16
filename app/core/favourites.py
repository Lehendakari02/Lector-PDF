"""Favourite tools: a tool together with the way it is used, kept at hand.

"Yellow highlighter", "thick red pen", "blue arrow"… Each one is a tool
(``marker_styles.STYLED_KINDS``) with its colour and, where the tool has them,
its opacity, its thickness, its shape or its letter. Taking one sets that tool
that way, in one click.

They live in the settings, as plain data. What cannot be understood there is
left out, so a damaged file never breaks the bar.
"""

from dataclasses import dataclass, replace

from app.core.commands import Color
from app.core.drawing import DEFAULT_SHAPE, DEFAULT_WIDTH, SHAPE_TOOL, SHAPES, clamp_width
from app.core.marker_styles import (
    LINE_KINDS,
    SEE_THROUGH_KINDS,
    STYLED_KINDS,
    MarkerStyles,
    clamp_opacity,
    clamp_size,
    from_hex,
    same_color,
    to_hex,
)
from app.core.notes import FONTS, SANS, TEXT_BOX, TEXT_SIZE

MAX_FAVOURITES = 12  # more than this is not a quick bar any more
MAX_NAME = 30


@dataclass(frozen=True)
class Favourite:
    """One tool, the way someone likes it."""

    kind: str  # one of STYLED_KINDS
    color: Color
    opacity: float = 1.0
    width: float = DEFAULT_WIDTH  # the pen and the shapes
    shape: str = DEFAULT_SHAPE  # the shapes
    font: str = SANS  # the text
    size: float = TEXT_SIZE  # the text
    name: str = ""  # given by the user; empty: the program describes it
    fill: bool = False  # the shapes
    dashed: bool = False  # the shapes

    def same_tool(self, other: "Favourite") -> bool:
        """Whether both are the same tool used the same way (the name aside)."""
        return replace(self, name="", color=(0, 0, 0)) == replace(
            other, name="", color=(0, 0, 0)
        ) and same_color(self.color, other.color)

    def to_setting(self) -> dict:
        data: dict = {"tool": self.kind, "color": to_hex(self.color)}
        if self.kind in SEE_THROUGH_KINDS:
            data["opacity"] = round(self.opacity, 2)
        if self.kind in LINE_KINDS:
            data["width"] = self.width
        if self.kind == SHAPE_TOOL:
            data["shape"] = self.shape
            if self.fill:
                data["fill"] = True
            if self.dashed:
                data["dashed"] = True
        if self.kind == TEXT_BOX:
            data["font"], data["size"] = self.font, self.size
        if self.name:
            data["name"] = self.name
        return data

    @classmethod
    def from_setting(cls, data: object) -> "Favourite | None":
        """Read what ``to_setting`` wrote. None if it is not a favourite."""
        if not isinstance(data, dict) or data.get("tool") not in STYLED_KINDS:
            return None
        kind = data["tool"]
        color = from_hex(data.get("color"))
        if color is None:
            return None
        shape, font, name = data.get("shape"), data.get("font"), data.get("name")
        shaped = kind == SHAPE_TOOL
        return cls(
            kind,
            color,
            clamp_opacity(data.get("opacity", 1.0)) if kind in SEE_THROUGH_KINDS else 1.0,
            clamp_width(data.get("width")) if kind in LINE_KINDS else DEFAULT_WIDTH,
            shape if kind == SHAPE_TOOL and shape in SHAPES else DEFAULT_SHAPE,
            font if kind == TEXT_BOX and font in FONTS else SANS,
            clamp_size(data.get("size")) if kind == TEXT_BOX else TEXT_SIZE,
            clean_name(name),
            shaped and data.get("fill") is True,
            shaped and data.get("dashed") is True,
        )


def clean_name(name: object) -> str:
    """A name fit for a button: one line, not too long."""
    if not isinstance(name, str):
        return ""
    return " ".join(name.split())[:MAX_NAME].strip()


def favourite_of(styles: MarkerStyles, kind: str) -> Favourite:
    """The favourite that is a tool as it is set right now."""
    style = styles.of(kind)
    return Favourite(
        kind,
        style.color,
        style.opacity if kind in SEE_THROUGH_KINDS else 1.0,
        styles.width_of(kind) if kind in LINE_KINDS else DEFAULT_WIDTH,
        styles.shape if kind == SHAPE_TOOL else DEFAULT_SHAPE,
        styles.text_font if kind == TEXT_BOX else SANS,
        styles.text_size if kind == TEXT_BOX else TEXT_SIZE,
        fill=kind == SHAPE_TOOL and styles.shape_fill,
        dashed=kind == SHAPE_TOOL and styles.shape_dashed,
    )


def apply_to(styles: MarkerStyles, favourite: Favourite) -> None:
    """Set a tool the way a favourite has it."""
    kind = favourite.kind
    styles.set_color(kind, favourite.color)
    if kind in SEE_THROUGH_KINDS:
        styles.set_opacity(kind, favourite.opacity)
    if kind in LINE_KINDS:
        styles.set_width(kind, favourite.width)
    if kind == SHAPE_TOOL:
        styles.set_shape(favourite.shape)
        styles.set_shape_fill(favourite.fill)
        styles.set_shape_dashed(favourite.dashed)
    if kind == TEXT_BOX:
        styles.set_text_font(favourite.font)
        styles.set_text_size(favourite.size)


class Favourites:
    """The favourite tools, in the order they are shown."""

    def __init__(self, items: list[Favourite] | None = None) -> None:
        self.items: list[Favourite] = list(items or [])[:MAX_FAVOURITES]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index: int) -> Favourite:
        return self.items[index]

    @property
    def full(self) -> bool:
        return len(self.items) >= MAX_FAVOURITES

    def find(self, favourite: Favourite) -> int:
        """Where the same tool used the same way is, or -1."""
        for index, item in enumerate(self.items):
            if item.same_tool(favourite):
                return index
        return -1

    def add(self, favourite: Favourite) -> int:
        """Keep a favourite. Returns where it is, or -1 if there is no room.

        The same tool used the same way is not kept twice.
        """
        index = self.find(favourite)
        if index >= 0:
            return index
        if self.full:
            return -1
        self.items.append(favourite)
        return len(self.items) - 1

    def remove(self, index: int) -> bool:
        if not 0 <= index < len(self.items):
            return False
        del self.items[index]
        return True

    def rename(self, index: int, name: object) -> bool:
        """Give a favourite a name (an empty one gives back its description)."""
        if not 0 <= index < len(self.items):
            return False
        self.items[index] = replace(self.items[index], name=clean_name(name))
        return True

    def move(self, index: int, by: int) -> int:
        """Move a favourite along the bar. Returns where it ends up."""
        if not 0 <= index < len(self.items):
            return index
        target = max(0, min(len(self.items) - 1, index + by))
        self.items.insert(target, self.items.pop(index))
        return target

    def to_setting(self) -> list[dict]:
        return [item.to_setting() for item in self.items]

    @classmethod
    def from_setting(cls, value: object) -> "Favourites":
        found: list[Favourite] = []
        if isinstance(value, list):
            for data in value:
                favourite = Favourite.from_setting(data)
                if favourite is not None and not any(favourite.same_tool(f) for f in found):
                    found.append(favourite)
        return cls(found)
