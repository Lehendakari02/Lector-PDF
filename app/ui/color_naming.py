"""The colour names (``app.core.color_names``) for the whole interface.

One set for the program, told when it changes so that every list of colours
can show the new name.
"""

from PySide6.QtCore import QObject, Signal

from app.core.color_names import ColorNames
from app.core.commands import Color


class _Naming(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.names = ColorNames()


_naming = _Naming()


def install(settings) -> None:
    """Read the names of these settings (the window does it on starting)."""
    _naming.names = ColorNames(settings)
    _naming.changed.emit()


def name_of(color: Color) -> str:
    return _naming.names.name_of(color)


def set_name(color: Color, name: str) -> None:
    _naming.names.set_name(color, name)
    _naming.changed.emit()


def changed():
    """The signal emitted when a name is given or taken away."""
    return _naming.changed
