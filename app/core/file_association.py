"""Offering the program to Windows as a program that opens PDFs.

What is written is the usual, per-user registration (no administrator rights):
the program appears in "Abrir con" and in the Windows list of default programs.
Windows does not let a program make itself the default one: the user confirms
it in the Windows settings, which this module can open at the right place.

The installer writes these same entries (``packaging/instalador.iss``); the
portable version writes them only if the user asks for it, and can remove them.
"""

import contextlib
import os
import sys
from pathlib import Path

from app.core.paths import is_packaged

PROG_ID = "LectorPDF.Documento"
PROGRAM = "Lector-PDF"
EXE_NAME = "Lector-PDF.exe"
_CLASSES = r"Software\Classes"
_CAPABILITIES = rf"Software\{PROGRAM}\Capabilities"
_REGISTERED = r"Software\RegisteredApplications"

# Keys that belong only to this program: removed whole when unregistering.
OWN_KEYS = (
    rf"{_CLASSES}\{PROG_ID}",
    rf"{_CLASSES}\Applications\{EXE_NAME}",
    _CAPABILITIES,
)
# Values written inside keys shared with other programs: only the value is removed.
SHARED_VALUES = (
    (rf"{_CLASSES}\.pdf\OpenWithProgids", PROG_ID),
    (_REGISTERED, PROGRAM),
)


def available() -> bool:
    """True where registering makes sense: the built program, on Windows."""
    return sys.platform == "win32" and is_packaged()


def open_command(program: str | Path) -> str:
    return f'"{program}" "%1"'


def registry_entries(program: str | Path) -> list[tuple[str, str, str]]:
    """Every (key, value name, value) to write under the current user's registry."""
    command = open_command(program)
    return [
        (rf"{_CLASSES}\{PROG_ID}", "", "Documento PDF"),
        (rf"{_CLASSES}\{PROG_ID}\DefaultIcon", "", f'"{program}",0'),
        (rf"{_CLASSES}\{PROG_ID}\shell\open\command", "", command),
        (rf"{_CLASSES}\.pdf\OpenWithProgids", PROG_ID, ""),
        (rf"{_CLASSES}\Applications\{EXE_NAME}", "FriendlyAppName", PROGRAM),
        (rf"{_CLASSES}\Applications\{EXE_NAME}\shell\open\command", "", command),
        (rf"{_CLASSES}\Applications\{EXE_NAME}\SupportedTypes", ".pdf", ""),
        (_CAPABILITIES, "ApplicationName", PROGRAM),
        (
            _CAPABILITIES,
            "ApplicationDescription",
            "Lee, estudia, rellena y firma tus PDF. Todo se queda en tu ordenador.",
        ),
        (rf"{_CAPABILITIES}\FileAssociations", ".pdf", PROG_ID),
        (_REGISTERED, PROGRAM, _CAPABILITIES),
    ]


def _tell_windows() -> None:
    """Ask Windows to read the associations again (icons, "Abrir con")."""
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED


def register(program: str | Path | None = None, prefix: str = "") -> bool:
    """Write the entries for ``program`` (this program by default). False if it failed.

    ``prefix`` moves everything under another registry key; the tests use it so
    that they never touch the real associations.
    """
    if sys.platform != "win32":
        return False
    import winreg

    program = program if program is not None else sys.executable
    try:
        for key, name, value in registry_entries(program):
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, prefix + key, 0, winreg.KEY_SET_VALUE
            ) as handle:
                winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)
    except OSError:
        return False
    if not prefix:
        _tell_windows()
    return True


def is_registered(program: str | Path | None = None, prefix: str = "") -> bool:
    """True if Windows already offers ``program`` (this one by default) for PDFs."""
    if sys.platform != "win32":
        return False
    import winreg

    program = program if program is not None else sys.executable
    try:
        for key, name, value in registry_entries(program):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, prefix + key) as handle:
                if winreg.QueryValueEx(handle, name)[0] != value:
                    return False
    except OSError:
        return False
    return True


def _delete_tree(winreg, key: str) -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as handle:
            while True:
                try:
                    child = winreg.EnumKey(handle, 0)
                except OSError:
                    break
                _delete_tree(winreg, rf"{key}\{child}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
    except OSError:
        return


def unregister(prefix: str = "") -> bool:
    """Remove everything ``register`` wrote. Other programs' entries are not touched."""
    if sys.platform != "win32":
        return False
    import winreg

    for key in OWN_KEYS:
        _delete_tree(winreg, prefix + key)
    for key, name in SHARED_VALUES:
        with (
            contextlib.suppress(OSError),
            winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, prefix + key, 0, winreg.KEY_SET_VALUE
            ) as handle,
        ):
            winreg.DeleteValue(handle, name)
    if not prefix:
        _tell_windows()
    return True


def open_windows_default_programs() -> bool:
    """Open the Windows settings page where the default programs are chosen."""
    if sys.platform != "win32":
        return False
    try:
        os.startfile("ms-settings:defaultapps")  # noqa: S606 (a Windows settings page)
    except OSError:
        return False
    return True
