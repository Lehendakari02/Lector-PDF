"""Where the program keeps its own files (settings, recovery journal, versions).

Installed version: the user's local application data folder.
Portable version: a folder next to the program, never ``%APPDATA%``, so it can
run from a USB stick or a work computer without leaving anything behind.
A build is portable when the file ``portable.txt`` sits next to the program.
"""

import os
import sys
from pathlib import Path

DATA_FOLDER_NAME = "Lector-PDF"
PORTABLE_MARKER = "portable.txt"
PORTABLE_DATA_FOLDER = "datos"


def is_packaged() -> bool:
    """True when running as the built Windows program, not from source code."""
    return bool(getattr(sys, "frozen", False))


def program_dir() -> Path:
    """Folder that contains the program (the ``.exe``, or the source code)."""
    if is_packaged():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def is_portable() -> bool:
    """True for the portable version (see the module description)."""
    return is_packaged() and (program_dir() / PORTABLE_MARKER).is_file()


def data_dir() -> Path:
    """Folder for the program's own files. It is not created here."""
    if is_portable():
        return program_dir() / PORTABLE_DATA_FOLDER
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path.home() / ".local" / "share"
    return root / DATA_FOLDER_NAME
