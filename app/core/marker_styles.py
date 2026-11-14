"""The colour and opacity each marking tool is used with, and how they are remembered.

Nothing here has a meaning attached: they are just colours. Every tool starts
with a sensible one (``commands.DEFAULT_COLORS``) and remembers the last one
chosen, so nobody has to touch anything.
"""

from dataclasses import dataclass, field

from app.core.commands import DEFAULT_COLORS, MARKUP_KINDS, Color

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


@dataclass(frozen=True)
class MarkerStyle:
    color: Color
    opacity: float = 1.0


def _defaults() -> dict[str, MarkerStyle]:
    return {kind: MarkerStyle(DEFAULT_COLORS[kind]) for kind in MARKUP_KINDS}


@dataclass
class MarkerStyles:
    """The style of every marking tool, plus the colours chosen lately."""

    styles: dict[str, MarkerStyle] = field(default_factory=_defaults)
    recent: list[Color] = field(default_factory=list)  # the newest first

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

    def to_setting(self) -> dict:
        """As plain data, for the settings file."""
        return {
            "tools": {
                kind: {"color": to_hex(style.color), "opacity": round(style.opacity, 2)}
                for kind, style in self.styles.items()
            },
            "recent": [to_hex(color) for color in self.recent],
        }

    @classmethod
    def from_setting(cls, value: object) -> "MarkerStyles":
        """Read what ``to_setting`` wrote. Whatever cannot be understood keeps its default."""
        result = cls()
        if not isinstance(value, dict):
            return result
        tools = value.get("tools")
        if isinstance(tools, dict):
            for kind in MARKUP_KINDS:
                saved = tools.get(kind)
                if not isinstance(saved, dict):
                    continue
                color = from_hex(saved.get("color")) or DEFAULT_COLORS[kind]
                result.styles[kind] = MarkerStyle(color, clamp_opacity(saved.get("opacity", 1.0)))
        recent = value.get("recent")
        if isinstance(recent, list):
            for text in recent:
                color = from_hex(text)
                if color is not None and not any(same_color(color, c) for c in result.recent):
                    result.recent.append(color)
            del result.recent[MAX_RECENT:]
        return result
