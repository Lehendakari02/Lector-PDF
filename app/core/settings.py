"""The user's settings, kept in a small file in the program's data folder.

Saving is safe: the new file is written completely next to the old one and then
swapped in, so a power cut never leaves a half-written settings file. A missing
or damaged file simply means "use the defaults"; the program never fails to
start because of its settings.
"""

import contextlib
import json
import os
from pathlib import Path
from typing import Any

from app.core.paths import data_dir

SETTINGS_FILE_NAME = "ajustes.json"


class Settings:
    """Named values that survive closing the program."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else data_dir() / SETTINGS_FILE_NAME
        self._values: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(loaded, dict):
            self._values = loaded

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value and save at once. Problems saving are not fatal."""
        if self._values.get(key) == value:
            return
        self._values[key] = value
        self.save()

    def save(self) -> bool:
        """Write the settings file. Returns False if it could not be written."""
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as file:
                json.dump(self._values, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        except OSError:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)
            return False
        return True
