"""The syllabus library: the folder with all the topics of an exam.

The user chooses a folder once. Every PDF in it (and in its folders) is a
topic: the library lists them with how far each one is studied, and searches
all of them at once with the rules of the document search (accents, the ñ,
words split at the end of a line…).

Reading many documents holds Python while PyMuPDF works, so the work is done
in a process of its own (``LibraryWork``) that sends back what it finds bit by
bit; it can be stopped at any time.
"""

from __future__ import annotations

import collections
import contextlib
import multiprocessing
import os
from dataclasses import dataclass
from pathlib import Path

from app.core.commands import MARKUP_KINDS
from app.core.search import DEFAULT_OPTIONS, SearchOptions, search_document

FOLDER_SETTING = "biblioteca/carpeta"
MOST_HITS_PER_DOCUMENT = 200  # more are not useful in a list: open the document
MOST_DOCUMENTS = 2000  # a folder chosen by mistake (the whole disk) stops here
MOST_ENTRIES = 50000  # files and folders looked at, at most (a few seconds at worst)


def topics_in(folder: str | Path | None, most_entries: int | None = None) -> list[Path]:
    """The PDFs of a folder and its folders, in the order of their names
    ("Tema 2" before "Tema 10"). Hidden folders and files are left out.

    A folder chosen by mistake (the whole disk) is not walked to the end: the
    look stops after ``most_entries`` files and folders, so the window never
    stays waiting."""
    if not folder:
        return []
    root = Path(folder)
    most = MOST_ENTRIES if most_entries is None else most_entries
    found: list[Path] = []
    looked = 0
    waiting = collections.deque([root])  # the nearest folders first
    while waiting and len(found) < MOST_DOCUMENTS and looked < most:
        here = waiting.popleft()
        try:
            with os.scandir(here) as entries:
                for entry in entries:
                    looked += 1
                    if looked > most:
                        break
                    if entry.name.startswith((".", "~$", "$")):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            waiting.append(Path(entry.path))
                        elif entry.name.lower().endswith(".pdf") and entry.is_file():
                            found.append(Path(entry.path))
                    except OSError:
                        continue
        except OSError:
            continue
    found = found[:MOST_DOCUMENTS]
    return sorted(found, key=lambda path: natural_key(path.relative_to(root)))


def natural_key(path: Path) -> list:
    """Sort "Tema 2" before "Tema 10", without caring about capitals."""
    key: list = []
    for part in path.parts:
        number, pieces = "", []
        for char in part.lower():
            if char.isdigit():
                number += char
                continue
            if number:
                pieces.append((0, int(number), ""))
                number = ""
            pieces.append((1, 0, char))
        if number:
            pieces.append((0, int(number), ""))
        key.append(pieces)
    return key


@dataclass(frozen=True)
class TopicInfo:
    """What the library shows of a topic besides its name."""

    path: Path
    pages: int  # 0 if it could not be opened
    marks: int  # highlights, underlines and strike-throughs in the file
    problem: str = ""  # "password", "damaged" or ""


@dataclass(frozen=True)
class LibraryHit:
    path: Path
    page: int
    before: str
    match: str
    after: str


def topic_info(path: Path) -> TopicInfo:
    import pymupdf

    try:
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                return TopicInfo(path, 0, 0, "password")
            marks = 0
            for page in doc:
                for annot in page.annots() or ():
                    if annot.type[1].lower() in MARKUP_KINDS:
                        marks += 1
            return TopicInfo(path, doc.page_count, marks)
    except Exception:
        return TopicInfo(path, 0, 0, "damaged")


def search_topic(path: Path, query: str, options: SearchOptions = DEFAULT_OPTIONS):
    """Yield the hits of one topic (as ``LibraryHit``), at most a few hundred."""
    import pymupdf

    try:
        doc = pymupdf.open(path)
    except Exception:
        return
    try:
        if doc.needs_pass:
            return
        count = 0
        for _number, hits in search_document(doc, query, options):
            for hit in hits:
                yield LibraryHit(path, hit.page, hit.before, hit.match, hit.after)
                count += 1
                if count >= MOST_HITS_PER_DOCUMENT:
                    return
    except Exception:
        return  # a damaged page: what was found so far stays
    finally:
        doc.close()


# ---- the work, in a process of its own ---------------------------------------


def _work(connection, paths: list[str], query: str | None, options: SearchOptions) -> None:
    """Look at every topic (``query`` None) or search them all, telling as it goes:
    ("info", TopicInfo), ("hit", LibraryHit), ("done_one", index), ("done",)."""
    try:
        for index, raw in enumerate(paths):
            path = Path(raw)
            if query is None:
                connection.send(("info", topic_info(path)))
            else:
                for hit in search_topic(path, query, options):
                    connection.send(("hit", hit))
            connection.send(("done_one", index))
        connection.send(("done",))
    except (BrokenPipeError, EOFError, OSError):
        pass  # stopped from the other side
    finally:
        connection.close()


class LibraryWork:
    """A look at the topics, or a search in all of them, in a process of its own.

    ``messages()`` gives what has arrived so far without waiting; ``stop()``
    ends it at once.
    """

    def __init__(self, paths: list[Path], query: str | None = None, options=DEFAULT_OPTIONS):
        context = multiprocessing.get_context("spawn")
        self._connection, sender = context.Pipe(duplex=False)
        self._process = context.Process(
            target=_work,
            args=(sender, [str(path) for path in paths], query, options),
            daemon=True,
        )
        self._process.start()
        sender.close()
        self.finished = False
        self.completed = False  # it said "done": every topic was looked at

    def messages(self, most: int = 500) -> list[tuple]:
        found: list[tuple] = []
        try:
            while len(found) < most and self._connection.poll():
                message = self._connection.recv()
                found.append(message)
                if message[0] == "done":
                    self.finished = self.completed = True
                    break
        except (EOFError, OSError):
            self.finished = True  # the process ended (or was stopped)
        return found

    def stop(self) -> None:
        self.finished = True
        if self._process.is_alive():
            self._process.terminate()
        self._process.join(timeout=2)
        with contextlib.suppress(OSError):
            self._connection.close()
