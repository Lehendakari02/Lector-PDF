"""What the program says about itself: its licence and the software it is built on."""

from pathlib import Path

from app.core.paths import is_packaged, program_dir

SOURCE_URL = "https://github.com/Lehendakari02/Lector-PDF"
OWN_LICENCE_NAME = "AGPL-3.0.txt"
NOTICES_NAME = "AVISOS.txt"
# In the built program the licences sit in plain view, next to the ``.exe``.
BUILT_FOLDER_NAME = "licencias"

_SOURCE_FOLDER = Path(__file__).resolve().parents[1] / "recursos" / "licencias"


def licence_folder() -> Path:
    """Folder with the notices and the text of every licence."""
    if is_packaged():
        return program_dir() / BUILT_FOLDER_NAME
    return _SOURCE_FOLDER


def own_licence_file() -> Path:
    """The licence of Lector-PDF itself."""
    if is_packaged():
        return licence_folder() / OWN_LICENCE_NAME
    return _SOURCE_FOLDER.parents[2] / "LICENSE"


def notices_text() -> str:
    """The list of third-party software, in plain words. Empty if it is missing."""
    try:
        return (licence_folder() / NOTICES_NAME).read_text(encoding="utf-8")
    except OSError:
        return ""
