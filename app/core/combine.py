"""Joining documents into one, cutting one into several, and taking some pages
out into a new document.

The originals are never touched: the result is always a new file, written
whole beside its place and then put there (nothing is left half written).
What is written on the pages (notes, marks, filled fields, links between
them) goes with them, and so does the outline: when joining, each document
becomes an entry with its own sections inside; when cutting, each part keeps
the sections of its pages.
"""

import os
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

EVERY = "cada"  # cut every so many pages
RANGES = "rangos"  # cut where the user says: "1-3, 4-10, 11-"
OUTLINE = "indice"  # cut at the main sections of the outline
WAYS = (EVERY, RANGES, OUTLINE)

MAX_NAME = 80  # letters of a section title used in a file name


class CombineError(Exception):
    """A document cannot be read or the result cannot be written."""


class NeedsPassword(CombineError):
    """A document asks for a password and the right one was not given."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"{path.name} asks for a password")
        self.path = path


@dataclass(frozen=True)
class Source:
    path: Path
    password: str | None = None


def _open(source: Source):
    import pymupdf

    try:
        doc = pymupdf.open(source.path, filetype="pdf")
    except Exception as error:  # PyMuPDF raises several unrelated error types
        raise CombineError(f"{source.path.name} cannot be read: {error}") from error
    if doc.needs_pass and not (source.password and doc.authenticate(source.password)):
        doc.close()
        raise NeedsPassword(source.path)
    if doc.page_count == 0:
        doc.close()
        raise CombineError(f"{source.path.name} has no pages")
    return doc


def _write(doc, target: Path) -> None:
    """Write the whole file beside its place, then put it there."""
    target = Path(target)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        doc.save(temporary, garbage=3, deflate=True)
        os.replace(temporary, target)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        raise CombineError(f"{target.name} cannot be written: {error}") from error


def free_name(target: Path) -> Path:
    """``target``, or «name (2).pdf», «name (3).pdf»… if it is taken."""
    target = Path(target)
    number = 2
    found = target
    while found.exists():
        found = target.with_name(f"{target.stem} ({number}){target.suffix}")
        number += 1
    return found


# ---- outline -------------------------------------------------------------


def _clean_outline(entries: list[list]) -> list[list]:
    """An outline PyMuPDF accepts: it starts at level 1 and never jumps
    more than one level down."""
    clean = []
    last = 0
    for level, title, page, *rest in entries:
        level = max(1, min(level, last + 1))
        clean.append([level, title, page, *rest])
        last = level
    return clean


def _outline_of(doc, pages: list[int]) -> list[list]:
    """The entries of the outline of ``doc`` that point to ``pages``, with the
    page numbers they have in a document made of those pages (from 1)."""
    place = {page: index for index, page in enumerate(pages)}
    found = []
    for level, title, page, *_rest in doc.get_toc(simple=True):
        if page - 1 in place:
            found.append([level, title, place[page - 1] + 1])
    if not found:
        return []
    top = min(entry[0] for entry in found)
    return [[level - top + 1, title, page] for level, title, page in found]


# ---- joining ---------------------------------------------------------------


def merge(sources: list[Source], target: Path, titles: list[str] | None = None) -> int:
    """Join the documents, in that order, into ``target``. Returns how many
    pages it has. Each document is an entry of the outline (``titles``, or the
    name of its file), with its own sections inside."""
    import pymupdf

    if not sources:
        raise CombineError("no documents to join")
    _not_over(target, sources)
    result = pymupdf.open()
    outline: list[list] = []
    try:
        for index, source in enumerate(sources):
            doc = _open(source)
            with doc:
                start = result.page_count
                try:
                    result.insert_pdf(doc)
                except Exception as error:
                    raise CombineError(f"{source.path.name} cannot be joined: {error}") from error
                title = titles[index] if titles and index < len(titles) else source.path.stem
                outline.append([1, title, start + 1])
                for level, name, page in _outline_of(doc, list(range(doc.page_count))):
                    outline.append([level + 1, name, start + page])
        with suppress(Exception):  # an outline that cannot be made is not worth failing
            result.set_toc(_clean_outline(outline))
        _write(result, target)
        return result.page_count
    finally:
        result.close()


# ---- cutting ---------------------------------------------------------------


def parse_ranges(text: str, count: int) -> list[list[int]]:
    """The parts the user wrote ("1-3, 5, 7-", counting from 1), as lists of
    pages counting from 0. Each part separated by a comma is one part.
    Raises ``ValueError`` saying what is wrong."""
    parts = []
    pieces = [piece.strip() for piece in re.split(r"[,;]", text) if piece.strip()]
    if not pieces:
        raise ValueError("empty")
    for piece in pieces:
        match = re.fullmatch(r"(\d*)\s*[-–]\s*(\d*)|(\d+)", piece)
        if not match:
            raise ValueError(piece)
        if match.group(3):
            first = last = int(match.group(3))
        else:
            if not match.group(1) and not match.group(2):
                raise ValueError(piece)
            first = int(match.group(1)) if match.group(1) else 1
            last = int(match.group(2)) if match.group(2) else count
        if not 1 <= first <= last <= count:
            raise ValueError(piece)
        parts.append(list(range(first - 1, last)))
    return parts


def every(count: int, size: int) -> list[list[int]]:
    """Parts of ``size`` pages (the last one may be shorter)."""
    size = max(1, int(size))
    return [list(range(start, min(start + size, count))) for start in range(0, count, size)]


def outline_parts(path: Path, password: str | None = None) -> list[tuple[str, list[int]]]:
    """The main sections of the outline, each with its pages. When the outline
    has a single entry on top (the title of a law), the sections are those
    inside it. Pages before the first section join it; sections that start on
    the same page go together. Empty if there are not two sections."""
    doc = _open(Source(Path(path), password))
    with doc:
        count = doc.page_count
        outline = [
            (level, title.strip(), page - 1)
            for level, title, page in doc.get_toc(simple=True)
            if 1 <= page <= count
        ]
    for depth in sorted({level for level, _title, _page in outline}):
        starts: list[tuple[str, int]] = []
        for level, title, page in outline:
            if level != depth:
                continue
            if starts and starts[-1][1] >= page:
                continue  # on the same page as the one before: one part
            starts.append((title, page))
        if len(starts) >= 2:
            break
    else:
        return []
    parts = []
    for index, (title, first) in enumerate(starts):
        first = 0 if index == 0 else first
        last = starts[index + 1][1] if index + 1 < len(starts) else count
        parts.append((title, list(range(first, last))))
    return parts


def safe_name(text: str) -> str:
    """A piece of a file name Windows accepts."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:MAX_NAME].strip(" .")


def part_names(stem: str, count: int, titles: list[str] | None = None) -> list[str]:
    """«name - parte 1.pdf» (numbered with as many figures as needed), or
    «name - 1 Título.pdf» with the titles of the sections."""
    width = len(str(count))
    names = []
    for index in range(count):
        number = str(index + 1).zfill(width)
        title = safe_name(titles[index]) if titles and index < len(titles) else ""
        names.append(f"{stem} - {number} {title}.pdf" if title else f"{stem} - parte {number}.pdf")
    return names


def _not_over(target: Path, sources: list[Source]) -> None:
    for source in sources:
        try:
            same = Path(target).resolve() == Path(source.path).resolve()
        except OSError:
            same = False
        if same:
            raise CombineError(f"{Path(target).name} is one of the documents used")


def split(
    source: Source,
    parts: list[list[int]],
    folder: Path,
    names: list[str],
    overwrite: bool = False,
) -> list[Path]:
    """One new document for each part, in ``folder``, with those names (a name
    already taken gets a number, unless ``overwrite``). Returns the files made."""
    import pymupdf

    folder = Path(folder)
    for name in names:
        _not_over(folder / name, [source])
    made = []
    doc = _open(source)
    with doc:
        for pages, name in zip(parts, names, strict=True):
            if not pages or min(pages) < 0 or max(pages) >= doc.page_count:
                raise CombineError("a part with pages that are not in the document")
            part = pymupdf.open()
            try:
                for page in pages:
                    part.insert_pdf(doc, from_page=page, to_page=page)
                with suppress(Exception):
                    part.set_toc(_clean_outline(_outline_of(doc, pages)))
                target = folder / name if overwrite else free_name(folder / name)
                _write(part, target)
            except CombineError:
                raise
            except Exception as error:
                raise CombineError(f"{name} cannot be made: {error}") from error
            finally:
                part.close()
            made.append(target)
    return made


def extract(source: Source, pages: list[int], target: Path) -> Path:
    """A new document with those pages, in that order (``target`` is
    replaced if it exists: the user chose it)."""
    target = Path(target)
    return split(source, [list(pages)], target.parent, [target.name], overwrite=True)[0]
