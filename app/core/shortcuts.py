"""The keys of every function, which each person can change ("like the
controls of a video game").

Every function of the program can have up to two keys or key combinations.
Most come with the usual ones (Ctrl+S, Ctrl+Z…), the tools of Estudiar with a
single letter (see ``app.core.tool_keys``) and the rest with none, ready to be
given one. What each person changes is kept in the settings; the rest follow
the defaults, so a new version can bring new keys without losing theirs.

A key without Ctrl or Alt (a letter, a digit) only counts while the document
has the keyboard: in the search box or in a text, a letter is still a letter.
Combinations with Ctrl or Alt, and keys such as F11, work everywhere.

Some keys can never be given: the ones that move through the document and
answer windows (arrows, Page Up, Space, Esc, Enter, Tab…).

The keys are written as Qt writes them in English ("Ctrl+Shift+S"), the same
on every system; the interface shows them in its own way.
"""

from app.core.settings import Settings
from app.core.tool_keys import FAVOURITE_KEYS, TOOL_KEYS

SETTING = "teclas"  # only the functions whose keys were changed: {id: [keys]}
MAX_KEYS = 2  # a key and another one, like the controls of a game

# The keys every function has unless they are changed. A function that is not
# here has none (it can be given one).
DEFAULTS: dict[str, tuple[str, ...]] = {
    # Archivo
    "open": ("Ctrl+O",),
    "close_tab": ("Ctrl+W",),
    "next_tab": ("Ctrl+Tab",),
    "previous_tab": ("Ctrl+Shift+Tab",),
    "save": ("Ctrl+S",),
    "save_as": ("Ctrl+Shift+S",),
    "print": ("Ctrl+P",),
    "settings": ("Ctrl+,",),
    # Editar
    "undo": ("Ctrl+Z",),
    "redo": ("Ctrl+Y", "Ctrl+Shift+Z"),
    "copy": ("Ctrl+C",),
    "paste": ("Ctrl+V",),
    "duplicate": ("Ctrl+D",),
    "delete": ("Del",),
    "select_all": ("Ctrl+A",),
    # Ver
    "mode_1": ("Ctrl+1",),
    "mode_2": ("Ctrl+2",),
    "mode_3": ("Ctrl+3",),
    "mode_4": ("Ctrl+4",),
    "fullscreen": ("F11",),
    "reading_cursor": ("F7",),
    "go_to_page": ("Ctrl+G",),
    "bookmark": ("Ctrl+M",),
    "rotate_view": ("Ctrl+R",),
    "side_panel": ("F4",),
    "fit_comfortable": ("Ctrl+0",),
    "zoom_in": ("Ctrl++", "Ctrl+="),
    "zoom_out": ("Ctrl+-",),
    "search": ("Ctrl+F",),
    "finder": ("Ctrl+K",),
    # The tools of Estudiar, one letter each, and the favourite tools, a digit.
    **{feature_id: (key,) for feature_id, key in TOOL_KEYS.items()},
    **{f"favourite_{index}": (key,) for index, key in enumerate(FAVOURITE_KEYS, start=1)},
}

# Keys that are never given to a function: they move through the document, or
# answer windows and texts.
RESERVED = frozenset(
    {
        "Esc",
        "Return",
        "Enter",
        "Tab",
        "Backtab",
        "Space",
        "Backspace",
        "Up",
        "Down",
        "Left",
        "Right",
        "PgUp",
        "PgDown",
        "Home",
        "End",
        "Shift+Tab",
        "Shift+Return",
        "Shift+Enter",
    }
)

_MODIFIERS = ("Ctrl+", "Alt+", "Meta+")


def defaults_of(command_id: str) -> tuple[str, ...]:
    return DEFAULTS.get(command_id, ())


def _changed(settings: Settings) -> dict[str, list[str]]:
    kept = settings.get(SETTING, {})
    return kept if isinstance(kept, dict) else {}


def keys_of(settings: Settings, command_id: str) -> tuple[str, ...]:
    """The keys of a function now: the ones chosen, or its usual ones."""
    chosen = _changed(settings).get(command_id)
    if isinstance(chosen, list) and all(isinstance(key, str) for key in chosen):
        return tuple(key for key in chosen if key)[:MAX_KEYS]
    return defaults_of(command_id)


def is_changed(settings: Settings, command_id: str) -> bool:
    return keys_of(settings, command_id) != defaults_of(command_id)


def set_keys(settings: Settings, command_id: str, keys) -> None:
    """Give a function these keys (none: it has no key)."""
    keys = tuple(dict.fromkeys(key for key in keys if key))[:MAX_KEYS]
    changed = dict(_changed(settings))
    if keys == defaults_of(command_id):
        changed.pop(command_id, None)
    else:
        changed[command_id] = list(keys)
    settings.set(SETTING, changed)


def reset(settings: Settings, command_id: str | None = None) -> None:
    """Back to the usual keys: of one function, or of all of them."""
    if command_id is None:
        settings.set(SETTING, {})
    else:
        changed = dict(_changed(settings))
        changed.pop(command_id, None)
        settings.set(SETTING, changed)


def is_plain(key: str) -> bool:
    """A key without Ctrl, Alt or the Windows key, that writes something (a
    letter, a digit, a sign): it only counts while the document has the keyboard."""
    if key.startswith(_MODIFIERS) or "+" in key.removeprefix("Shift+").rstrip("+"):
        return False
    bare = key.removeprefix("Shift+")
    return len(bare) == 1


def is_reserved(key: str) -> bool:
    return key in RESERVED


def users_of(settings: Settings, key: str, command_ids, but: str | None = None) -> list[str]:
    """The functions (among ``command_ids``) that already have this key."""
    return [
        command_id
        for command_id in command_ids
        if command_id != but and key in keys_of(settings, command_id)
    ]


def clashes(settings: Settings, command_ids) -> dict[str, list[str]]:
    """Keys given to more than one function: none of them would work."""
    by_key: dict[str, list[str]] = {}
    for command_id in command_ids:
        for key in keys_of(settings, command_id):
            by_key.setdefault(key, []).append(command_id)
    return {key: ids for key, ids in by_key.items() if len(ids) > 1}
