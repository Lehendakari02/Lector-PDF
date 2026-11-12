"""What the program remembers between sessions about the documents used.

- The documents that were open when the program was closed, to bring them back.
- For every document, the page that was being read and the work mode.
- The list of recent files.

Everything is kept in the settings file, on this computer only.
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.settings import Settings

RESTORE_SETTING = "volver_a_las_pestanas"  # True: reopen the tabs of the last time
SESSION_SETTING = "sesion"
PLACES_SETTING = "documentos"
RECENT_SETTING = "recientes"
MAX_RECENT = 12
MAX_PLACES = 300  # documents whose page is remembered; the oldest are forgotten


def file_key(path: str | Path) -> str:
    """Two paths with the same key are the same file (Windows ignores capitals)."""
    return os.path.normcase(os.path.abspath(path))


@dataclass(frozen=True)
class Place:
    """Where a document was left."""

    page: int = 0  # counting from 0
    mode: str = ""  # name of the work mode, empty if unknown


class History:
    """Reads and writes those memories in the settings."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ---- the tabs of the last time ---------------------------------------

    @property
    def restore_wanted(self) -> bool:
        return bool(self.settings.get(RESTORE_SETTING, True))

    def save_session(self, paths: list[Path], current: int) -> None:
        self.settings.set(SESSION_SETTING, {"abiertos": [str(p) for p in paths], "actual": current})

    def session(self) -> tuple[list[Path], int]:
        """The documents open the last time and which one was in front."""
        stored = self.settings.get(SESSION_SETTING)
        if not isinstance(stored, dict):
            return [], -1
        paths = [Path(p) for p in stored.get("abiertos", ()) if isinstance(p, str)]
        current = stored.get("actual", -1)
        return paths, current if isinstance(current, int) else -1

    # ---- where every document was left ------------------------------------

    def remember_place(self, path: str | Path, page: int, mode: str = "") -> None:
        places = self._places()
        places[file_key(path)] = {"pagina": page, "modo": mode, "visto": int(time.time())}
        if len(places) > MAX_PLACES:
            oldest = sorted(places, key=lambda key: places[key].get("visto", 0))
            for key in oldest[: len(places) - MAX_PLACES]:
                del places[key]
        self.settings.set(PLACES_SETTING, places)

    def place_of(self, path: str | Path) -> Place:
        stored = self._places().get(file_key(path))
        if not isinstance(stored, dict):
            return Place()
        page, mode = stored.get("pagina", 0), stored.get("modo", "")
        return Place(
            page if isinstance(page, int) and page >= 0 else 0,
            mode if isinstance(mode, str) else "",
        )

    def _places(self) -> dict:
        stored = self.settings.get(PLACES_SETTING)
        return dict(stored) if isinstance(stored, dict) else {}

    # ---- recent files ---------------------------------------------------------

    def add_recent(self, path: str | Path) -> None:
        """Put a file at the top of the recent list."""
        key = file_key(path)
        kept = [p for p in self._recent() if file_key(p) != key]
        self.settings.set(RECENT_SETTING, [str(Path(path).absolute()), *kept][:MAX_RECENT])

    def recent(self) -> list[Path]:
        """Recent files, newest first. Files that no longer exist are left out."""
        return [Path(p) for p in self._recent() if Path(p).is_file()]

    def forget_recent(self) -> None:
        self.settings.set(RECENT_SETTING, [])

    def _recent(self) -> list[str]:
        stored = self.settings.get(RECENT_SETTING)
        return [p for p in stored if isinstance(p, str)] if isinstance(stored, list) else []
