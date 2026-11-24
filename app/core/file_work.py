"""Writing a whole copy of a document («Comprimir», «Contraseña») in a
process of its own.

PyMuPDF stops the rest of Python while it works, and making the pictures of
a long scanned document lighter takes a while: in its own process the window
keeps answering, and «Cancelar» ends it at once (its temporary file is taken
away; the original is never touched).
"""

import contextlib
import multiprocessing
from pathlib import Path

COMPRESS = "compress"
PROTECT = "protect"
UNPROTECT = "unprotect"
# «Comparar» reads two documents here too: `path` is the old version and
# `target` the new one (nothing is written), `extra` the password of the new.
COMPARE = "compare"


def run(what: str, path: str, password: str | None, target: str, extra: str | None):
    """Do the work here, in this process. Returns the message the window gets:
    ("done", target, before, after), ("not_smaller", before, after),
    ("needs_password",) or ("failed", description)."""
    from app.core.combine import CombineError, NeedsPassword, Source
    from app.core.compress import NotSmaller, compress
    from app.core.protection import protect, unprotect

    source = Source(Path(path), password)
    if what == COMPARE:
        return _compare(source, Source(Path(target), extra))
    before = Path(path).stat().st_size if Path(path).exists() else 0
    try:
        if what == COMPRESS:
            result = compress(source, Path(target), extra or "normal")
            return ("done", str(result.target), result.before, result.after)
        if what == PROTECT:
            written = protect(source, Path(target), extra or "")
        elif what == UNPROTECT:
            written = unprotect(source, Path(target))
        else:
            return ("failed", f"unknown work {what}")
        return ("done", str(written), before, written.stat().st_size)
    except NotSmaller as small:
        return ("not_smaller", small.before, small.after)
    except NeedsPassword:
        return ("needs_password",)
    except CombineError as error:
        return ("failed", str(error))
    except Exception as error:  # nothing may stop the answer from arriving
        return ("failed", f"{type(error).__name__}: {error}")


def _compare(old, new) -> tuple:
    """("compared", Comparison), ("needs_password", path), ("no_text", path)
    or ("failed", description)."""
    from app.core.combine import CombineError, NeedsPassword
    from app.core.compare import NoText, compare_files

    try:
        return ("compared", compare_files(old, new))
    except NeedsPassword as locked:
        return ("needs_password", str(locked.path))
    except NoText as empty:
        return ("no_text", str(empty.path))
    except CombineError as error:
        return ("failed", str(error))
    except Exception as error:  # nothing may stop the answer from arriving
        return ("failed", f"{type(error).__name__}: {error}")


def _main(connection, what, path, password, target, extra) -> None:
    try:
        connection.send(run(what, path, password, target, extra))
    except (BrokenPipeError, EOFError, OSError):
        pass  # stopped from the other side
    finally:
        connection.close()


class FileWork:
    """One copy being written in a process of its own. ``answer()`` gives the
    message once it has arrived (None until then); ``stop()`` ends it."""

    def __init__(
        self,
        what: str,
        path: Path,
        password: str | None,
        target: Path,
        extra: str | None = None,
    ) -> None:
        context = multiprocessing.get_context("spawn")
        self._connection, sender = context.Pipe(duplex=False)
        self._process = context.Process(
            target=_main,
            args=(sender, what, str(path), password, str(target), extra),
            daemon=True,
        )
        self._process.start()
        sender.close()
        self._answer: tuple | None = None
        self._target = Path(target)
        self.finished = False

    def answer(self) -> tuple | None:
        if self._answer is None and not self.finished:
            try:
                if self._connection.poll():
                    self._answer = self._connection.recv()
                    self.finished = True
                elif not self._process.is_alive():
                    # It may have answered just before ending.
                    if self._connection.poll():
                        self._answer = self._connection.recv()
                    else:
                        self._answer = ("failed", "the process stopped")
                    self.finished = True
            except (EOFError, OSError):
                self._answer = ("failed", "the process stopped")
                self.finished = True
        return self._answer

    def stop(self) -> None:
        self.finished = True
        if self._process.is_alive():
            self._process.terminate()
        self._process.join(timeout=2)
        with contextlib.suppress(OSError):
            self._connection.close()
        with contextlib.suppress(OSError):
            self._target.with_name(f".{self._target.name}.tmp").unlink(missing_ok=True)
