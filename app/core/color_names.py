"""Names the user gives to colours ("Amarillo: definiciones"), if they want.

Nothing comes named: a colour without a name is just a colour. The names live
in the settings of this computer, not in the documents, and every document
uses them. A colour read back from a PDF is a little rounded, so it finds its
name when it is near enough.
"""

from app.core.annotation_list import same_color as near_enough
from app.core.commands import Color
from app.core.marker_styles import from_hex, to_hex

SETTING = "colors/names"
LONGEST_NAME = 40


class ColorNames:
    """The names, kept in ``settings`` (anything with ``get`` and ``set``)."""

    def __init__(self, settings=None) -> None:
        self.settings = settings
        self._names: dict[str, str] = {}
        stored = settings.get(SETTING, {}) if settings is not None else {}
        if isinstance(stored, dict):
            for key, name in stored.items():
                if from_hex(key) is not None and isinstance(name, str) and name.strip():
                    self._names[key] = name.strip()[:LONGEST_NAME]

    def name_of(self, color: Color) -> str:
        """The name of a colour, or "" if it has none."""
        exact = self._names.get(to_hex(color))
        if exact:
            return exact
        for key, name in self._names.items():
            if near_enough(from_hex(key), color):
                return name
        return ""

    def set_name(self, color: Color, name: str) -> None:
        """Name a colour; an empty name takes the name away."""
        name = " ".join(str(name).split())[:LONGEST_NAME]
        for key in [k for k in self._names if near_enough(from_hex(k), color)]:
            del self._names[key]
        if name:
            self._names[to_hex(color)] = name
        if self.settings is not None:
            self.settings.set(SETTING, dict(self._names))

    def named(self) -> dict[str, str]:
        return dict(self._names)
