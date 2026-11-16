"""The colour and opacity each marking tool is used with, and how they are remembered.

Nothing here has a meaning attached: they are just colours. Every tool starts
with a sensible one (``commands.DEFAULT_COLORS``) and remembers the last one
chosen, so nobody has to touch anything.
"""

from dataclasses import dataclass, field

from app.core.commands import DEFAULT_COLORS, MARKUP_KINDS, Color
from app.core.drawing import (
    DEFAULT_SHAPE,
    DEFAULT_WIDTH,
    DRAW,
    DRAW_COLOR,
    SHAPE_COLOR,
    SHAPE_TOOL,
    SHAPES,
    clamp_width,
)
from app.core.notes import (
    FONTS,
    MAX_SIZE,
    MIN_SIZE,
    NOTE,
    NOTE_COLOR,
    SANS,
    TEXT_BOX,
    TEXT_COLOR,
    TEXT_SIZE,
)

# Every tool that has a colour of its own: the markers, the notes, the text,
# the pen and the shapes.
STYLED_KINDS = (*MARKUP_KINDS, NOTE, TEXT_BOX, DRAW, SHAPE_TOOL)
# The ones that draw a line, with a thickness that can be chosen.
LINE_KINDS = (DRAW, SHAPE_TOOL)
# The ones whose opacity can be chosen (a note or a text has none).
SEE_THROUGH_KINDS = (*MARKUP_KINDS, *LINE_KINDS)
START_COLORS: dict[str, Color] = {
    **DEFAULT_COLORS,
    NOTE: NOTE_COLOR,
    TEXT_BOX: TEXT_COLOR,
    DRAW: DRAW_COLOR,
    SHAPE_TOOL: SHAPE_COLOR,
}
# The sizes of letter at hand for the text written on the page.
TEXT_SIZES = (8, 10, 12, 14, 18, 24, 36)

# The colours at hand in the quick palette: six of marker, four of pen.
QUICK_COLORS: tuple[Color, ...] = (
    (1.0, 0.92, 0.23),  # yellow
    (0.56, 0.88, 0.42),  # green
    (0.47, 0.82, 1.0),  # light blue
    (1.0, 0.62, 0.81),  # pink
    (1.0, 0.72, 0.30),  # orange
    (0.79, 0.64, 1.0),  # purple
    (0.85, 0.15, 0.15),  # red
    (0.13, 0.39, 0.85),  # blue
    (0.10, 0.55, 0.25),  # dark green
    (0.10, 0.10, 0.10),  # black
)

MIN_OPACITY = 0.1  # less than this cannot be seen, and looks like a failure
MAX_RECENT = 5


def to_hex(color: Color) -> str:
    """The colour written like "#ffeb3b"."""
    return "#" + "".join(f"{round(_unit(part) * 255):02x}" for part in color)


def from_hex(text: object) -> Color | None:
    """The colour written like "#ffeb3b", or None if it is not one."""
    if not isinstance(text, str) or len(text) != 7 or text[0] != "#":
        return None
    try:
        return tuple(int(text[i : i + 2], 16) / 255 for i in (1, 3, 5))
    except ValueError:
        return None


def same_color(one: Color, other: Color) -> bool:
    """Whether two colours are the same to the eye (and once written down)."""
    return to_hex(one) == to_hex(other)


def _unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def clamp_opacity(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    if number != number:  # not a number
        return 1.0
    return max(MIN_OPACITY, min(1.0, number))


def clamp_size(value: object) -> float:
    """A size of letter that can be used, whatever was stored."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return TEXT_SIZE
    if isinstance(value, bool) or number != number:
        return TEXT_SIZE
    return max(MIN_SIZE, min(MAX_SIZE, number))


@dataclass(frozen=True)
class MarkerStyle:
    color: Color
    opacity: float = 1.0


def _defaults() -> dict[str, MarkerStyle]:
    return {kind: MarkerStyle(START_COLORS[kind]) for kind in STYLED_KINDS}


@dataclass
class MarkerStyles:
    """The style of every marking tool, plus the colours chosen lately."""

    styles: dict[str, MarkerStyle] = field(default_factory=_defaults)
    recent: list[Color] = field(default_factory=list)  # the newest first
    text_font: str = SANS  # the text written on the page: one of notes.FONTS
    text_size: float = TEXT_SIZE
    text_bold: bool = False
    # The pen and the shapes: how thick their line is, and the shape in hand.
    widths: dict[str, float] = field(
        default_factory=lambda: dict.fromkeys(LINE_KINDS, DEFAULT_WIDTH)
    )
    shape: str = DEFAULT_SHAPE
    shape_fill: bool = False  # closed shapes filled with a light tone of their colour
    shape_dashed: bool = False

    def of(self, kind: str) -> MarkerStyle:
        return self.styles[kind]

    def set_color(self, kind: str, color: Color) -> None:
        color = tuple(_unit(part) for part in color)
        self.styles[kind] = MarkerStyle(color, self.styles[kind].opacity)
        if not any(same_color(color, quick) for quick in QUICK_COLORS):
            self.recent = [color] + [c for c in self.recent if not same_color(c, color)]
            del self.recent[MAX_RECENT:]

    def set_opacity(self, kind: str, opacity: float) -> None:
        self.styles[kind] = MarkerStyle(self.styles[kind].color, clamp_opacity(opacity))

    def set_text_font(self, font: object) -> None:
        if isinstance(font, str) and font in FONTS:
            self.text_font = font

    def set_text_size(self, size: float) -> None:
        self.text_size = clamp_size(size)

    def set_text_bold(self, bold: object) -> None:
        self.text_bold = bold is True

    def width_of(self, kind: str) -> float:
        return self.widths.get(kind, DEFAULT_WIDTH)

    def set_width(self, kind: str, width: object) -> None:
        if kind in LINE_KINDS:
            self.widths[kind] = clamp_width(width)

    def set_shape(self, shape: object) -> None:
        if isinstance(shape, str) and shape in SHAPES:
            self.shape = shape

    def set_shape_fill(self, fill: object) -> None:
        self.shape_fill = fill is True

    def set_shape_dashed(self, dashed: object) -> None:
        self.shape_dashed = dashed is True

    def to_setting(self) -> dict:
        """As plain data, for the settings file."""
        return {
            "tools": {
                kind: {"color": to_hex(style.color), "opacity": round(style.opacity, 2)}
                | ({"width": self.widths[kind]} if kind in LINE_KINDS else {})
                for kind, style in self.styles.items()
            },
            "recent": [to_hex(color) for color in self.recent],
            "text": {"font": self.text_font, "size": self.text_size}
            | ({"bold": True} if self.text_bold else {}),
            "shape": self.shape,
            **({"shape_fill": True} if self.shape_fill else {}),
            **({"shape_dashed": True} if self.shape_dashed else {}),
        }

    @classmethod
    def from_setting(cls, value: object) -> "MarkerStyles":
        """Read what ``to_setting`` wrote. Whatever cannot be understood keeps its default."""
        result = cls()
        if not isinstance(value, dict):
            return result
        tools = value.get("tools")
        if isinstance(tools, dict):
            for kind in STYLED_KINDS:
                saved = tools.get(kind)
                if not isinstance(saved, dict):
                    continue
                color = from_hex(saved.get("color")) or START_COLORS[kind]
                result.styles[kind] = MarkerStyle(color, clamp_opacity(saved.get("opacity", 1.0)))
                result.set_width(kind, saved.get("width"))
        result.set_shape(value.get("shape"))
        result.set_shape_fill(value.get("shape_fill"))
        result.set_shape_dashed(value.get("shape_dashed"))
        text = value.get("text")
        if isinstance(text, dict):
            result.set_text_font(text.get("font"))
            result.text_size = clamp_size(text.get("size"))
            result.set_text_bold(text.get("bold"))
        recent = value.get("recent")
        if isinstance(recent, list):
            for text in recent:
                color = from_hex(text)
                if color is not None and not any(same_color(color, c) for c in result.recent):
                    result.recent.append(color)
            del result.recent[MAX_RECENT:]
        return result
