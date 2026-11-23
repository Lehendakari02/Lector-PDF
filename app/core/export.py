"""Taking pages out as pictures, or the text of the document out as a text
file («Exportar»).

Pictures: one file for each page, PNG (sharp, for documents) or JPEG
(smaller, for photos), at the resolution asked for, with the notes and marks
drawn on them or without them. Text: the letters of the pages in reading
order, words cut with a hyphen at the end of a line joined again, with a
heading for each page. Nothing is ever written over: a name that is taken
gets « (2)». Each file is written beside its place and then put there.
"""

import os
from collections.abc import Callable
from pathlib import Path

from app.core.combine import CombineError, Source, _open, free_name, safe_name

PNG = "png"
JPEG = "jpg"
IMAGE_KINDS = (PNG, JPEG)
RESOLUTIONS = (96, 150, 300)  # screen, normal, high (points per inch)
DEFAULT_RESOLUTION = 150
JPEG_QUALITY = 90
MAX_PIXELS = 60_000_000  # a page larger than this at that resolution is drawn smaller

Progress = Callable[[int, int], bool | None]


class ExportError(CombineError):
    """A file cannot be written. (A document that cannot be read raises
    CombineError, as when joining.)"""


def _check(progress: Progress | None, done: int, total: int) -> None:
    if progress is not None and progress(done, total) is False:
        raise ExportError("stopped")


def _replace(temporary: Path, target: Path) -> None:
    try:
        os.replace(temporary, target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ExportError(f"{target.name} cannot be written: {error}") from error


def image_names(stem: str, pages: list[int], count: int, kind: str) -> list[str]:
    """«name - página 03.png» for each page (counting from 1, with as many
    figures as the document needs, so they sort in order)."""
    width = len(str(count))
    stem = safe_name(stem) or "documento"
    return [f"{stem} - página {str(page + 1).zfill(width)}.{kind}" for page in pages]


def _zoom(page, resolution: int) -> float:
    zoom = resolution / 72
    pixels = page.rect.width * zoom * page.rect.height * zoom
    if pixels > MAX_PIXELS:  # a huge plan: keep the picture to a size that opens
        zoom *= (MAX_PIXELS / pixels) ** 0.5
    return zoom


def export_images(
    source: Source,
    pages: list[int],
    targets: list[Path],
    kind: str = PNG,
    resolution: int = DEFAULT_RESOLUTION,
    annotations: bool = True,
    progress: Progress | None = None,
) -> list[Path]:
    """Draw ``pages`` (counting from 0) into the files ``targets`` (free names
    are taken when they exist). ``progress(done, total)`` may return False
    to stop. Returns the files written. Raises ExportError."""
    import pymupdf

    if kind not in IMAGE_KINDS:
        raise ExportError(f"unknown kind {kind}")
    written: list[Path] = []
    with _open(source) as doc:  # NeedsPassword, a CombineError, if it asks for one
        for done, (number, target) in enumerate(zip(pages, targets, strict=True)):
            _check(progress, done, len(pages))
            page = doc[number]
            zoom = _zoom(page, resolution)
            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(zoom, zoom), alpha=False, annots=annotations
            )
            pix.set_dpi(round(resolution), round(resolution))
            target = free_name(Path(target))
            temporary = target.with_name(f".{target.name}.tmp")
            try:
                if kind == JPEG:
                    temporary.write_bytes(pix.tobytes("jpg", jpg_quality=JPEG_QUALITY))
                else:
                    temporary.write_bytes(pix.tobytes("png"))
            except Exception as error:
                temporary.unlink(missing_ok=True)
                raise ExportError(f"{target.name} cannot be written: {error}") from error
            _replace(temporary, target)
            written.append(target)
    if progress is not None:
        progress(len(pages), len(pages))
    return written


def page_heading(number: int) -> str:
    return f"— Página {number + 1} —"


def export_text(
    source: Source,
    pages: list[int],
    target: Path,
    progress: Progress | None = None,
) -> tuple[Path, list[int]]:
    """The text of ``pages`` into the file ``target`` (UTF-8), with a heading
    for each page when there are several. Returns the file written and the
    pages that had no text (scanned and not recognised yet). Raises
    ExportError."""
    import pymupdf

    flags = pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_DEHYPHENATE
    pieces: list[str] = []
    empty: list[int] = []
    with _open(source) as doc:  # NeedsPassword, a CombineError, if it asks for one
        for done, number in enumerate(pages):
            _check(progress, done, len(pages))
            text = doc[number].get_text("text", flags=flags)
            text = "\n".join(line.rstrip() for line in text.strip("\n").splitlines())
            if not text.strip():
                empty.append(number)
            if len(pages) > 1:
                pieces.append(f"{page_heading(number)}\n\n{text}".rstrip())
            else:
                pieces.append(text)
    target = free_name(Path(target))
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text("\n\n\n".join(pieces).rstrip() + "\n", encoding="utf-8")
    except Exception as error:
        temporary.unlink(missing_ok=True)
        raise ExportError(f"{target.name} cannot be written: {error}") from error
    _replace(temporary, target)
    if progress is not None:
        progress(len(pages), len(pages))
    return target, empty
