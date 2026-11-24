"""Making a PDF take less space («Comprimir»).

Two levels:

- **Normal**: the file is written again tidily: what nothing uses goes, what
  repeats is kept once and everything is packed. Nothing that is seen changes.
- **Fuerte**: also the pictures (photos, scanned pages) are made lighter: at
  most 150 points per inch, which reads and prints well, as JPEG.

The result is a new file; the original stays as it was. When the copy would
hardly be smaller, it is not written (``NotSmaller``). The protection with a
password, if there is one, is kept.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.combine import CombineError, Source, _open
from app.core.protection import protection_apart

NORMAL = "normal"
STRONG = "fuerte"
LEVELS = (NORMAL, STRONG)
PICTURE_RESOLUTION = 150  # points per inch the pictures are left at
PICTURE_THRESHOLD = 200  # pictures sharper than this are made lighter
PICTURE_QUALITY = 75  # JPEG
WORTH_IT = 0.97  # the copy is written only if it is smaller than this share


class CompressError(CombineError):
    """The copy cannot be written."""


class NotSmaller(CompressError):
    """The document is already as small as it can be made."""

    def __init__(self, before: int, after: int) -> None:
        super().__init__("the document cannot be made smaller")
        self.before = before
        self.after = after


@dataclass(frozen=True)
class Result:
    target: Path
    before: int  # bytes
    after: int


def compress(
    source: Source, target: Path, level: str = NORMAL, progress: Callable[[], None] | None = None
) -> Result:
    """Write into ``target`` a smaller copy of ``source``."""
    import pymupdf

    if level not in LEVELS:
        raise CompressError(f"unknown level {level}")
    target = Path(target)
    if target.resolve() == Path(source.path).resolve():
        raise CompressError("the copy cannot go over the original")
    before = Path(source.path).stat().st_size
    doc = _open(source)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        protected = doc.xref_get_key(-1, "Encrypt")[0] != "null"
        try:
            if level == STRONG:
                doc.rewrite_images(options=_picture_options())
                if progress is not None:
                    progress()
            doc.save(
                temporary,
                garbage=4,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                # Packing objects together is left out for a protected file: its
                # protection is then added at the end as an object of its own.
                use_objstms=0 if protected else 1,
                encryption=pymupdf.PDF_ENCRYPT_KEEP,
            )
            if protected:
                protection_apart(temporary, source.password)
            with pymupdf.open(temporary, filetype="pdf") as written:
                if written.needs_pass and not written.authenticate(source.password or ""):
                    raise CompressError("the copy does not open with the password")
                if written.page_count != doc.page_count:
                    raise CompressError("the copy does not have the same pages")
        except CompressError:
            raise
        except Exception as error:  # PyMuPDF raises several unrelated error types
            raise CompressError(f"{target.name} cannot be written: {error}") from error
        after = temporary.stat().st_size
        if after > before * WORTH_IT:
            raise NotSmaller(before, after)
        try:
            os.replace(temporary, target)
        except OSError as error:
            raise CompressError(f"{target.name} cannot be written: {error}") from error
        return Result(target, before, after)
    finally:
        temporary.unlink(missing_ok=True)
        doc.close()


def _picture_options():
    """Colour and grey pictures sharper than the threshold are drawn again
    at 150 points per inch (smoothly, at any ratio) and kept as JPEG, only
    when that is smaller. Black-and-white scans are left as they are: they
    are already light, and lowering them blurs the letters."""
    from pymupdf import mupdf

    options = mupdf.PdfImageRewriterOptions()
    for kind in ("color_lossless", "color_lossy", "gray_lossless", "gray_lossy"):
        setattr(options, f"{kind}_image_recompress_method", mupdf.FZ_RECOMPRESS_JPEG)
        setattr(options, f"{kind}_image_recompress_quality", str(PICTURE_QUALITY))
        setattr(options, f"{kind}_image_subsample_method", mupdf.FZ_SUBSAMPLE_BICUBIC)
        setattr(options, f"{kind}_image_subsample_threshold", PICTURE_THRESHOLD)
        setattr(options, f"{kind}_image_subsample_to", PICTURE_RESOLUTION)
    options.recompress_when = mupdf.FZ_RECOMPRESS_WHEN_SMALLER
    return options


def size_text(size: int) -> str:
    """«850 KB», «12,4 MB»: a size as people say it (in Spanish)."""
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")
