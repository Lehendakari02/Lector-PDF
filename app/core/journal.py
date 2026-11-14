"""The recovery journal: every change is written down the moment it is made.

It is a small file apart from the PDF, in the program's data folder, one per
document with changes not saved yet. It never touches the PDF. If the power
goes, the program hangs or it is closed by force, the changes are here and can
be put back the next time (``Journal.pending``). When the PDF is saved, what
was saved is taken out of the journal.

"No guardar" does not throw the changes away at once either: the journal of
that document is set aside for some days (``Journal.discarded``).

Writing is safe. A change is one line added at the end and pushed to the disk;
a line cut short by a power cut is simply not read. Whenever the file has to be
rewritten, it is written whole next to the old one and swapped in.

What is written are the orders of ``app.core.commands``, with ``to_dict``.
"""

import contextlib
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.commands import Command, CommandError, command_from_dict
from app.core.history import file_key

FOLDER_NAME = "diario"
LIVE_SUFFIX = ".jsonl"
DISCARDED_MARK = ".descartado"
KEEP_DISCARDED_DAYS = 7
VERSION = 1

Entry = tuple[Command, bool]  # an order and whether it was undone (True) or done


def net(entries: list[Entry]) -> list[Entry]:
    """What is left to do after cancelling each order with its own undoing.

    Doing an order and undoing it leaves nothing. An undoing with no doing
    before it stays: it takes away something that is already in the file.
    """
    left: list[tuple[dict, Command, bool]] = []
    for order, undone in entries:
        written = order.to_dict()
        for index in range(len(left) - 1, -1, -1):
            if left[index][0] == written and left[index][2] != undone:
                del left[index]
                break
        else:
            left.append((written, order, undone))
    return [(order, undone) for _written, order, undone in left]


@dataclass(frozen=True)
class Pending:
    """The changes of one document waiting in the journal."""

    path: Path  # the PDF
    file: Path  # the journal file
    entries: tuple[Entry, ...]  # already netted: what has to be done to bring them back
    when: float  # time of the last change (seconds since 1970)
    discarded: bool  # set aside with "No guardar" (or not recovered after a failure)

    @property
    def count(self) -> int:
        return len(self.entries)


class DocumentJournal:
    """The journal of one open document."""

    def __init__(self, folder: Path, path: str | Path) -> None:
        self.folder = Path(folder)
        self.path = Path(path)
        self._count = len(_read(self.file)[1]) if self.file.exists() else 0

    @property
    def file(self) -> Path:
        return self.folder / (_name_for(self.path) + LIVE_SUFFIX)

    @property
    def count(self) -> int:
        """How many changes are written down and not saved in the PDF yet."""
        return self._count

    def entries(self) -> list[Entry]:
        return _read(self.file)[1] if self.file.exists() else []

    def record(self, order: Command, undone: bool = False) -> bool:
        """Write down a change just made. False if it could not be written.

        Not being able to write the journal never stops the work: the change is
        still in the open document and can be saved.
        """
        line = {"what": "undo" if undone else "do", "t": time.time(), "order": order.to_dict()}
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with open(self.file, "ab+") as file:
                text = ""
                size = file.seek(0, os.SEEK_END)
                if size == 0:
                    text = _line(_header(self.path))
                else:
                    file.seek(size - 1)
                    if file.read(1) != b"\n":
                        # The last line was cut short (a power cut): close it,
                        # so that this one does not get stuck to it.
                        text = "\n"
                    file.seek(0, os.SEEK_END)
                file.write((text + _line(line)).encode("utf-8"))
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            return False
        self._count += 1
        return True

    def saved(self, count: int, path: str | Path | None = None) -> None:
        """The first ``count`` changes are in the PDF now: take them out.

        ``path`` is the file the document lives in from now on (it changes
        with "Guardar como"); the changes made while it was being saved go on
        in the journal of that file.
        """
        rest = self.entries()[max(0, count) :]
        old = self.file
        if path is not None and file_key(path) != file_key(self.path):
            self.path = Path(path)
        self._write(rest)
        if old != self.file:
            _remove(old)

    def restart(self, entries: list[Entry]) -> None:
        """Leave in the journal exactly these changes (used when recovering)."""
        self._write(list(entries))

    def discard(self) -> None:
        """ "No guardar": set the changes aside. They can be recovered for some days."""
        if not self.file.exists():
            return
        if not net(self.entries()):
            self.forget()
            return
        aside = (
            self.folder
            / f"{_name_for(self.path)}.{int(time.time() * 1000)}{DISCARDED_MARK}{LIVE_SUFFIX}"
        )
        try:
            os.replace(self.file, aside)
        except OSError:
            return
        self._count = 0

    def forget(self) -> None:
        """Throw the journal of this document away."""
        _remove(self.file)
        self._count = 0

    def _write(self, entries: list[Entry]) -> None:
        self._count = len(entries)
        if not entries:
            _remove(self.file)
            return
        lines = [_header(self.path)] + [
            {"what": "undo" if undone else "do", "t": time.time(), "order": order.to_dict()}
            for order, undone in entries
        ]
        _write_whole(self.file, lines)


class Journal:
    """The folder with the journals of every document."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def of(self, path: str | Path) -> DocumentJournal:
        return DocumentJournal(self.folder, path)

    def pending(self) -> list[Pending]:
        """Documents with changes that were never saved nor set aside:
        the program was closed by force, hung or the power went."""
        return [found for found in self._all() if not found.discarded]

    def discarded(self) -> list[Pending]:
        """Changes set aside with "No guardar", the newest first."""
        return [found for found in self._all() if found.discarded]

    def forget(self, pending: Pending) -> None:
        _remove(pending.file)

    def set_aside(self, pending: Pending) -> None:
        """Do not offer these changes at the start any more; keep them some days."""
        if not pending.discarded:
            DocumentJournal(self.folder, pending.path).discard()

    def forget_old(self, days: float = KEEP_DISCARDED_DAYS, now: float | None = None) -> int:
        """Delete the discarded changes kept for more than ``days``. Returns how many."""
        limit = (time.time() if now is None else now) - days * 86400
        gone = 0
        for found in self.discarded():
            if found.when < limit:
                _remove(found.file)
                gone += 1
        return gone

    def _all(self) -> list[Pending]:
        found = []
        try:
            files = sorted(self.folder.glob("*" + LIVE_SUFFIX))
        except OSError:
            return []
        for file in files:
            header, entries, when = _read(file)
            left = net(entries)
            if header is None or not left:
                continue
            discarded = file.name.endswith(DISCARDED_MARK + LIVE_SUFFIX)
            found.append(Pending(Path(header["path"]), file, tuple(left), when, discarded))
        return sorted(found, key=lambda pending: pending.when, reverse=True)


# ---- reading and writing the files ----------------------------------------


def _name_for(path: Path) -> str:
    return hashlib.sha256(file_key(path).encode("utf-8")).hexdigest()[:20]


def _header(path: Path) -> dict:
    return {"what": "document", "v": VERSION, "path": str(Path(path).absolute()), "t": time.time()}


def _line(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def _read(file: Path) -> tuple[dict | None, list[Entry], float]:
    """The header, the changes and the time of the last one.

    Whatever cannot be read (a line cut short, an order of a newer version)
    is left out; the rest is still good.
    """
    header: dict | None = None
    entries: list[Entry] = []
    when = 0.0
    try:
        with open(file, encoding="utf-8", errors="replace") as lines:
            text = lines.read()
    except OSError:
        return None, [], 0.0
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue  # cut short by a power cut
        if not isinstance(data, dict):
            continue
        what = data.get("what")
        if what == "document" and isinstance(data.get("path"), str):
            if header is None:
                header = data
                when = _time(data, when)
        elif what in ("do", "undo") and isinstance(data.get("order"), dict):
            try:
                order = command_from_dict(data["order"])
            except CommandError:
                continue
            entries.append((order, what == "undo"))
            when = _time(data, when)
    return header, entries, when


def _time(data: dict, default: float) -> float:
    value = data.get("t")
    return float(value) if isinstance(value, (int, float)) else default


def _write_whole(file: Path, lines: list[dict]) -> bool:
    temporary = file.with_name(file.name + ".tmp")
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(temporary, "w", encoding="utf-8") as out:
            out.writelines(_line(line) for line in lines)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, file)
    except OSError:
        _remove(temporary)
        return False
    return True


def _remove(file: Path) -> None:
    with contextlib.suppress(OSError):
        file.unlink()
