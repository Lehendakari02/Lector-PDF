"""The user's settings, kept in a small file in the program's data folder.

Saving is safe: the new file is written completely next to the old one and then
swapped in, so a power cut never leaves a half-written settings file. A missing
or damaged file simply means "use the defaults"; the program never fails to
start because of its settings.
"""

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any

from app.core.paths import data_dir

SETTINGS_FILE_NAME = "ajustes.json"
READ_TRIES = 4
READ_PAUSE = 0.15  # seconds; an antivirus or a sync program lets go in a moment

# Why a file gave no values.
_MISSING, _HELD, _DAMAGED = object(), object(), object()


class Settings:
    """Named values that survive closing the program.

    What was remembered is never thrown away by accident:

    - A file that is there but cannot be read right now (an antivirus or a
      sync program holding it for a moment) is tried again, and it is never
      written over while it has not been read: what changes meanwhile is added
      to it as soon as it can be read.
    - A damaged file is set aside (``ajustes.dañado.json``), not deleted, and
      the last good copy (``ajustes.copia.json``) is used instead.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else data_dir() / SETTINGS_FILE_NAME
        self._values: dict[str, Any] = {}
        self._unread = False  # the file is there but could not be read yet
        self._changed: set[str] = set()  # set while the file could not be read
        self.save_failed = False  # the last try to write the file did not work
        self._load()

    @property
    def backup_path(self) -> Path:
        return self.path.with_name(f"{self.path.stem}.copia{self.path.suffix}")

    @property
    def damaged_path(self) -> Path:
        return self.path.with_name(f"{self.path.stem}.dañado{self.path.suffix}")

    def _load(self) -> None:
        loaded = self._read(self.path)
        if loaded is _MISSING:
            return
        if loaded is _HELD:
            self._unread = True
            return
        if loaded is _DAMAGED:
            # Kept aside for whoever wants to look at it; never written over.
            with contextlib.suppress(OSError):
                os.replace(self.path, self.damaged_path)
            copy = self._read(self.backup_path, tries=1)
            if isinstance(copy, dict):
                self._values = copy
                self.save()
            return
        self._values = loaded
        self._keep_copy()

    @staticmethod
    def _read(path: Path, tries: int = READ_TRIES) -> Any:
        """The values in ``path``, or why there are none."""
        for attempt in range(tries):
            try:
                text = path.read_text(encoding="utf-8")
            except (FileNotFoundError, NotADirectoryError):
                return _MISSING
            except UnicodeDecodeError:
                return _DAMAGED
            except OSError:
                if attempt + 1 < tries:
                    time.sleep(READ_PAUSE)
                continue
            try:
                loaded = json.loads(text)
            except ValueError:
                return _DAMAGED
            return loaded if isinstance(loaded, dict) else _DAMAGED
        return _HELD

    def _keep_copy(self) -> None:
        """Keep the file just read, which is good, as the copy to fall back on."""
        with contextlib.suppress(OSError):
            content = self.path.read_bytes()
            if not self.backup_path.exists() or self.backup_path.read_bytes() != content:
                temporary = self.backup_path.with_name(self.backup_path.name + ".tmp")
                temporary.write_bytes(content)
                os.replace(temporary, self.backup_path)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value and save at once. Problems saving are not fatal."""
        if self._values.get(key) == value and not self._unread:
            return
        self._values[key] = value
        if self._unread:
            self._changed.add(key)
        self.save()

    def save(self) -> bool:
        """Write the settings file. Returns False if it could not be written."""
        if self._unread and not self._catch_up():
            self.save_failed = True
            return False
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
            self.save_failed = True
            return False
        self.save_failed = False
        return True

    def _catch_up(self) -> bool:
        """Read at last the file that could not be read, and add to it what
        was set meanwhile. False if it still cannot be read: it is not touched."""
        loaded = self._read(self.path, tries=1)
        if loaded is _HELD:
            return False
        if isinstance(loaded, dict):
            fresh = {key: self._values[key] for key in self._changed if key in self._values}
            self._values = {**loaded, **fresh}
        elif loaded is _DAMAGED:
            with contextlib.suppress(OSError):
                os.replace(self.path, self.damaged_path)
        self._unread = False
        self._changed.clear()
        return True
