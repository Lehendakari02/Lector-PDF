"""The size of the interface (buttons, menus and letters), chosen in the settings.

The size is given to Qt before the window exists, so changing it needs the
program to start again.
"""

from app.core.restart import set_own_variable
from app.core.settings import Settings

SIZE_SETTING = "tamano_interfaz"  # a percentage: 100 is the normal size
SIZES = (100, 110, 125, 150, 175)
NORMAL_SIZE = 100
_QT_VARIABLE = "QT_SCALE_FACTOR"


def size_from_setting(value: object) -> int:
    """A size the program offers; the normal one if the value is unknown."""
    return value if isinstance(value, int) and value in SIZES else NORMAL_SIZE


def wanted_size(settings: Settings) -> int:
    return size_from_setting(settings.get(SIZE_SETTING))


def apply_before_start(settings: Settings, environ: dict[str, str]) -> int:
    """Tell Qt the size, before the application is created. Returns the size.

    A size already set from outside (by whoever started the program) is kept.
    """
    size = wanted_size(settings)
    if size != NORMAL_SIZE and _QT_VARIABLE not in environ:
        set_own_variable(environ, _QT_VARIABLE, f"{size / 100:g}")
    return size
