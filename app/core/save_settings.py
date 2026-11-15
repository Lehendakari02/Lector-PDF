"""The preferences about saving: what the user may choose, and the defaults.

Nobody has to touch them: without any setting the program asks when closing
with changes, never saves by itself, keeps ten earlier versions of each
document (1 GB at most) and keeps the discarded changes a week.

Whatever is stored is read with care: a value that is not one of the choices
(a settings file edited by hand, or written by a later version) counts as the
default.
"""

from app.core.settings import Settings

# What to do when closing with changes not saved.
CLOSE_SETTING = "al_cerrar"
ASK = "preguntar"
SAVE = "guardar"
DISCARD = "no_guardar"
CLOSE_CHOICES = (ASK, SAVE, DISCARD)

# Saving by itself while working: off unless asked for.
AUTOSAVE_SETTING = "guardar_solo"
AUTOSAVE_SECONDS_SETTING = "guardar_solo_segundos"
AUTOSAVE_SECONDS_CHOICES = (10, 30, 60, 120, 300)
AUTOSAVE_SECONDS = 30

# Earlier versions: how many of each document, and the room for all of them.
VERSIONS_COUNT_SETTING = "versiones_por_documento"
VERSIONS_COUNT_CHOICES = (3, 5, 10, 20, 50)
VERSIONS_COUNT = 10
VERSIONS_ROOM_SETTING = "versiones_espacio_mb"
VERSIONS_ROOM_CHOICES = (250, 500, 1024, 2048, 5120)
VERSIONS_ROOM = 1024

# Days the changes discarded with "No guardar" are kept.
DISCARDED_DAYS_SETTING = "dias_cambios_descartados"
DISCARDED_DAYS_CHOICES = (1, 3, 7, 14, 30)
DISCARDED_DAYS = 7

MEGABYTE = 1024 * 1024


def _choice(settings: Settings, name: str, choices: tuple, default):
    stored = settings.get(name, default)
    # True == 1 in Python: a boolean is never one of the numbers.
    if isinstance(stored, bool) or stored not in choices:
        return default
    return stored


def close_choice(settings: Settings) -> str:
    """What the user has chosen for closing with changes."""
    return _choice(settings, CLOSE_SETTING, CLOSE_CHOICES, ASK)


def autosave_wanted(settings: Settings) -> bool:
    return settings.get(AUTOSAVE_SETTING, False) is True


def autosave_seconds(settings: Settings) -> int:
    return _choice(settings, AUTOSAVE_SECONDS_SETTING, AUTOSAVE_SECONDS_CHOICES, AUTOSAVE_SECONDS)


def when_closing(settings: Settings) -> str:
    """What really happens when closing with changes.

    Whoever lets the program save by itself is not asked when closing either:
    the changes are saved, as they would have been a moment later.
    """
    if autosave_wanted(settings):
        return SAVE
    return close_choice(settings)


def versions_count(settings: Settings) -> int:
    return _choice(settings, VERSIONS_COUNT_SETTING, VERSIONS_COUNT_CHOICES, VERSIONS_COUNT)


def versions_room_mb(settings: Settings) -> int:
    return _choice(settings, VERSIONS_ROOM_SETTING, VERSIONS_ROOM_CHOICES, VERSIONS_ROOM)


def versions_room_bytes(settings: Settings) -> int:
    return versions_room_mb(settings) * MEGABYTE


def discarded_days(settings: Settings) -> int:
    return _choice(settings, DISCARDED_DAYS_SETTING, DISCARDED_DAYS_CHOICES, DISCARDED_DAYS)
