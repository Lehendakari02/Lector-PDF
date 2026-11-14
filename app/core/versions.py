"""Earlier versions of a PDF: the safety net under "Guardar".

The first time a PDF is saved in each session, a copy of the file as it was is
kept here, apart from the PDF, in the program's data folder. Any of those copies
can be looked at or put back ("Archivo → Versiones anteriores"), so saving
something by mistake can always be undone.

Each document has its own folder with the copies (``<moment>.pdf``) and a small
note with the path of the document. Copies are written whole to a temporary
file and then given their name: a power cut never leaves a broken version.
"""

import contextlib
import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.history import file_key

FOLDER_NAME = "versiones"
NOTE_NAME = "documento.json"
MAX_PER_DOCUMENT = 10  # versions kept of each document
MAX_TOTAL_BYTES = 1024 * 1024 * 1024  # room all the versions may take: 1 GB
CHUNK = 1024 * 1024


class VersionError(Exception):
    """A version could not be kept or put back."""


@dataclass(frozen=True)
class Version:
    """One earlier version of a document."""

    document: Path  # the PDF it is a version of
    file: Path  # the copy
    when: float  # when the copy was made (seconds since 1970)
    size: int  # bytes


class Versions:
    """The folder with the earlier versions of every document."""

    def __init__(
        self,
        folder: str | Path,
        max_per_document: int = MAX_PER_DOCUMENT,
        max_total_bytes: int = MAX_TOTAL_BYTES,
    ) -> None:
        self.folder = Path(folder)
        self.max_per_document = max_per_document
        self.max_total_bytes = max_total_bytes

    # ---- keeping -------------------------------------------------------

    def keep(self, document: str | Path, now: float | None = None) -> Version | None:
        """Keep a copy of ``document`` as it is on disk right now.

        Returns the version, or None when there was nothing to keep: the file
        does not exist yet, or it is identical to the newest version kept.
        Raises ``VersionError`` if the copy could not be made (disk full…).
        """
        document = Path(document)
        if not document.is_file():
            return None
        folder = self._folder_of(document)
        newest = next(iter(self.of(document)), None)
        try:
            size = document.stat().st_size
            if newest is not None and newest.size == size and _same(newest.file, document):
                return None
            folder.mkdir(parents=True, exist_ok=True)
            note = folder / NOTE_NAME
            if not note.exists():
                _write_text(
                    note, json.dumps({"path": str(document.absolute())}, ensure_ascii=False)
                )
            moment = time.time() if now is None else now
            target = folder / f"{int(moment * 1000):015d}.pdf"
            while target.exists():  # two in the same millisecond
                moment += 0.001
                target = folder / f"{int(moment * 1000):015d}.pdf"
            temporary = target.with_name(target.name + ".tmp")
            try:
                with open(document, "rb") as source, open(temporary, "wb") as out:
                    shutil.copyfileobj(source, out, CHUNK)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, target)
            except OSError:
                _remove(temporary)
                raise
        except OSError as error:
            raise VersionError(str(error)) from error
        version = Version(document.absolute(), target, int(target.stem) / 1000, size)
        self.tidy(keep=version)
        return version

    # ---- looking -------------------------------------------------------

    def of(self, document: str | Path) -> list[Version]:
        """The versions kept of ``document``, the newest first."""
        return self._in(self._folder_of(Path(document)), Path(document).absolute())

    def all(self) -> list[Version]:
        """Every version of every document, the newest first."""
        found: list[Version] = []
        try:
            folders = [entry for entry in self.folder.iterdir() if entry.is_dir()]
        except OSError:
            return []
        for folder in folders:
            document = _noted_document(folder)
            if document is not None:
                found.extend(self._in(folder, document))
        return sorted(found, key=lambda version: version.when, reverse=True)

    def total_bytes(self) -> int:
        return sum(version.size for version in self.all())

    # ---- putting back ----------------------------------------------------

    def restore(self, version: Version, target: str | Path | None = None) -> Path:
        """Make ``target`` (the document itself, if none is given) be that version.

        How the file is right now is kept first as one more version, so that
        putting a version back can be undone too. The file is replaced in one
        step. Raises ``VersionError`` if it cannot be done; nothing is lost then.
        """
        target = Path(target) if target is not None else version.document
        if not version.file.is_file():
            raise VersionError("that version is no longer there")
        self.keep(target)
        temporary = target.with_name(f".{target.name}.restaurando")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(version.file, "rb") as source, open(temporary, "wb") as out:
                shutil.copyfileobj(source, out, CHUNK)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, target)
        except OSError as error:
            _remove(temporary)
            raise VersionError(str(error)) from error
        return target

    def forget(self, version: Version) -> None:
        _remove(version.file)
        self._drop_if_empty(version.file.parent)

    # ---- not taking too much room ----------------------------------------

    def tidy(self, keep: Version | None = None) -> int:
        """Delete the oldest versions beyond the limits. Returns how many.

        ``keep`` is never deleted (the one just made): the safety net of the
        save going on matters more than the limit of room.
        """
        gone = 0
        everything = self.all()
        by_document: dict[str, list[Version]] = {}
        for version in everything:
            by_document.setdefault(file_key(version.document), []).append(version)
        doomed: list[Version] = []
        for versions in by_document.values():
            doomed.extend(versions[max(1, self.max_per_document) :])
        left = [version for version in everything if version not in doomed]
        total = sum(version.size for version in left)
        for version in reversed(left):  # the oldest first
            if total <= self.max_total_bytes:
                break
            if keep is not None and version.file == keep.file:
                continue
            doomed.append(version)
            total -= version.size
        for version in doomed:
            if keep is not None and version.file == keep.file:
                continue
            self.forget(version)
            gone += 1
        return gone

    # ---- inside ------------------------------------------------------------

    def _folder_of(self, document: Path) -> Path:
        name = hashlib.sha256(file_key(document).encode("utf-8")).hexdigest()[:20]
        return self.folder / name

    @staticmethod
    def _in(folder: Path, document: Path) -> list[Version]:
        found = []
        try:
            files = list(folder.glob("*.pdf"))
        except OSError:
            return []
        for file in files:
            try:
                when = int(file.stem) / 1000
                size = file.stat().st_size
            except (ValueError, OSError):
                continue
            found.append(Version(document, file, when, size))
        return sorted(found, key=lambda version: version.when, reverse=True)

    @staticmethod
    def _drop_if_empty(folder: Path) -> None:
        with contextlib.suppress(OSError):
            if not any(folder.glob("*.pdf")):
                _remove(folder / NOTE_NAME)
                folder.rmdir()


def _noted_document(folder: Path) -> Path | None:
    try:
        note = json.loads((folder / NOTE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    path = note.get("path") if isinstance(note, dict) else None
    return Path(path) if isinstance(path, str) else None


def _same(one: Path, other: Path) -> bool:
    """Whether two files hold exactly the same bytes."""
    with open(one, "rb") as first, open(other, "rb") as second:
        while True:
            a, b = first.read(CHUNK), second.read(CHUNK)
            if a != b:
                return False
            if not a:
                return True


def _write_text(file: Path, text: str) -> None:
    temporary = file.with_name(file.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, file)


def _remove(file: Path) -> None:
    with contextlib.suppress(OSError):
        file.unlink()
