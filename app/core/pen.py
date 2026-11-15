"""The pen and the fingers on a touch screen: what the user may choose.

Nobody has to touch anything: a pen that feels pressure draws thicker where
the hand presses more, and the fingers do what is expected of them. On a
screen with no pen, a finger uses the tool in hand; from the day a pen is used
on the program, the fingers only move the page and change its size, so that
the hand can rest on the screen while writing.

Whatever is stored is read with care: a value that is not one of the choices
counts as the default.
"""

from app.core.settings import Settings

# Whether a stroke is thicker where the pen pressed more.
PRESSURE_SETTING = "lapiz_presion"

# What a finger does while a tool is in hand.
FINGER_SETTING = "dedo"
AUTO = "auto"  # it uses the tool until a pen is seen; from then on, it only moves
DRAWS = "dibuja"  # it always uses the tool
MOVES = "mueve"  # it only moves the page
FINGER_CHOICES = (AUTO, DRAWS, MOVES)

# Remembered once a pen has touched a page: with AUTO, the fingers stop drawing.
PEN_SEEN_SETTING = "lapiz_visto"

# For this long after the pen was on or near the screen, a touch is the hand
# that holds it and not a finger.
PALM_SECONDS = 0.7


def pressure_wanted(settings: Settings) -> bool:
    return settings.get(PRESSURE_SETTING, True) is not False


def finger_mode(settings: Settings) -> str:
    value = settings.get(FINGER_SETTING, AUTO)
    return value if value in FINGER_CHOICES else AUTO


def pen_seen(settings: Settings) -> bool:
    return settings.get(PEN_SEEN_SETTING, False) is True


def finger_uses_tool(mode: str, seen: bool) -> bool:
    """Whether a finger on the page uses the tool in hand (or only moves the page)."""
    if mode == DRAWS:
        return True
    if mode == MOVES:
        return False
    return not seen


def palm(since_pen: float, pen_down: bool = False) -> bool:
    """Whether a touch is the hand resting, given the seconds since the pen
    was last on or near the screen."""
    return pen_down or since_pen < PALM_SECONDS
