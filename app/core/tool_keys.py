"""One key for each tool, to change tools without the mouse.

They are single letters, the first one of the Spanish name where it is free
(R for "Resaltar", S for "Subrayar"…), and they only count while the page has
the keyboard: in the search box or in a note, a letter is still a letter.
The digits take the favourite tools, in the order of their bar.

They can be turned off in the settings, for whoever finds that a key pressed
by mistake does too much.
"""

from app.core.settings import Settings

TOOL_KEYS_SETTING = "atajos_herramientas"

# The key of each tool, by the name of its function (``app.ui.features``).
TOOL_KEYS: dict[str, str] = {
    "highlight": "R",  # Resaltar
    "underline": "S",  # Subrayar
    "strikeout": "T",  # Tachar
    "note": "N",  # Nota
    "text_box": "X",  # cuadro de teXto (the T is taken)
    "draw": "D",  # Dibujar
    "shapes": "F",  # Formas
    "eraser": "B",  # Borrador
    "hide_annotations": "O",  # Ocultar anotaciones
}

FAVOURITE_KEYS = "123456789"  # the first nine favourites


def tool_keys_wanted(settings: Settings) -> bool:
    return settings.get(TOOL_KEYS_SETTING, True) is not False
