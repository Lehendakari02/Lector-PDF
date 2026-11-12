"""Starting the program again (after changing a setting that needs it, or an update).

The new copy is started when the old one has already saved everything and is
about to end, so the two never write the settings at the same time.
"""

import os
import subprocess
import sys
from collections.abc import Mapping

from app.core.paths import is_packaged

# Variables the running copy set for itself: the new copy must decide again.
OWN_VARIABLES_MARK = "LECTOR_PDF_VARIABLES_PROPIAS"


def relaunch_command() -> list[str]:
    """The command that starts this program again, without any document.

    The tabs come back by themselves (the session is remembered).
    """
    if is_packaged():
        return [sys.executable]
    return [sys.executable, "-m", "app.main"]


def set_own_variable(environ: dict[str, str], name: str, value: str) -> None:
    """Set a variable for this copy only: a restarted copy will not inherit it."""
    environ[name] = value
    names = [n for n in environ.get(OWN_VARIABLES_MARK, "").split(os.pathsep) if n]
    if name not in names:
        environ[OWN_VARIABLES_MARK] = os.pathsep.join([*names, name])


def relaunch_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """The environment for the new copy: as this one found it when it started."""
    fresh = dict(environ)
    for name in fresh.pop(OWN_VARIABLES_MARK, "").split(os.pathsep):
        fresh.pop(name, None)
    # The packaged program must start as a new program, not as a helper of this one.
    fresh["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return fresh


def relaunch() -> bool:
    """Start the program again. Returns False if it could not be started."""
    try:
        subprocess.Popen(  # noqa: S603 (our own program)
            relaunch_command(),
            env=relaunch_environment(os.environ),
            cwd=None,
            close_fds=True,
        )
    except OSError:
        return False
    return True
