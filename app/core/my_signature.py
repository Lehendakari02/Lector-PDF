"""The saved signature and initials: made once, put with a click.

Each one is a picture (PNG with a see-through background), whether it was
drawn, written with a handwriting font or taken from a photo or a scan of a
signature on paper. They are kept only on this computer, in the program's
own folder, never sent anywhere and never inside a document until one signs.

A picture taken from a photo loses its background here: the paper (the
lightest common colour) becomes see-through and the ink keeps its colour,
with soft edges. Then everything is cut to the ink, so the signature is
placed by its own size and not by the size of the photo.
"""

from __future__ import annotations

import contextlib
import os
from collections import Counter
from pathlib import Path

SIGNATURE = "firma"
INITIALS = "iniciales"
KINDS = (SIGNATURE, INITIALS)
FOLDER = "firma"  # inside the program's data folder

LONGEST_SIDE = 1600  # pixels: sharp when printed, small to keep
INK_GAP = 60  # how much darker than the paper ink is surely ink
SOFT = 40  # the width of the soft edge between paper and ink
MARGIN = 4  # pixels left around the ink when it is cut


class SignatureError(Exception):
    """The picture cannot be read or has no ink in it."""


def picture_path(folder: Path, kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError(kind)
    return folder / f"{kind}.png"


def load(folder: Path, kind: str) -> bytes | None:
    """The saved picture of a signature or the initials, or None."""
    try:
        data = picture_path(folder, kind).read_bytes()
    except OSError:
        return None
    return data or None


def save(folder: Path, kind: str, png: bytes) -> None:
    """Keeps the picture, written whole or not at all."""
    target = picture_path(folder, kind)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with open(temporary, "wb") as file:
        file.write(png)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, target)


def forget(folder: Path, kind: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        picture_path(folder, kind).unlink()


def _open(data: bytes):
    import pymupdf

    try:
        pix = pymupdf.Pixmap(data)
    except Exception as error:
        raise SignatureError("not a picture") from error
    if pix.width < 2 or pix.height < 2:
        raise SignatureError("too small")
    return pix


def _alpha_of(pix) -> bytes:
    """The see-through value of each pixel (row after row, no padding)."""
    n = pix.n
    samples = pix.samples
    return bytes(samples[n - 1 :: n])


def _paper_level(gray: bytes) -> int:
    """How light the paper is: the most common level of the lighter half."""
    counts = Counter(gray)
    light = {level: count for level, count in counts.items() if level >= 96}
    if not light:
        raise SignatureError("no paper")
    return max(light, key=light.get)


def _ink_alpha(gray: bytes) -> bytes:
    paper = _paper_level(gray)
    solid = max(0, paper - INK_GAP - SOFT)  # darker than this: all ink
    clear = max(1, paper - INK_GAP + SOFT // 2)  # lighter than this: paper
    table = bytearray(256)
    for level in range(256):
        if level <= solid:
            table[level] = 255
        elif level < clear:
            table[level] = round(255 * (clear - level) / (clear - solid))
    return gray.translate(bytes(table))


def _ink_box(alpha: bytes, width: int, height: int):
    rows = [y for y in range(height) if alpha[y * width : (y + 1) * width].strip(b"\x00")]
    if not rows:
        raise SignatureError("no ink")
    left, right = width, 0
    for y in rows:
        row = alpha[y * width : (y + 1) * width]
        start = len(row) - len(row.lstrip(b"\x00"))
        end = len(row.rstrip(b"\x00"))
        left, right = min(left, start), max(right, end)
    return (
        max(0, left - MARGIN),
        max(0, rows[0] - MARGIN),
        min(width, right + MARGIN),
        min(height, rows[-1] + 1 + MARGIN),
    )


def clean(data: bytes, remove_background: bool = True) -> bytes:
    """A picture of a signature, ready to keep: no background (unless it has
    one see-through already, or ``remove_background`` is False), cut to the
    ink, no larger than ``LONGEST_SIDE``. Raises SignatureError."""
    import pymupdf

    pix = _open(data)
    while max(pix.width, pix.height) > 2 * LONGEST_SIDE:
        pix.shrink(1)
    if pix.colorspace is None or pix.colorspace.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    alpha = _alpha_of(pix) if pix.alpha else b""
    if alpha and min(alpha) < 255:
        with_alpha = pix  # already see-through where there is no ink
    else:
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)  # its colours alone
        gray = pymupdf.Pixmap(pymupdf.csGRAY, pix).samples
        alpha = _ink_alpha(gray) if remove_background else bytes([255]) * len(gray)
        with_alpha = pymupdf.Pixmap(pix, 1)
        with_alpha.set_alpha(alpha)
    x0, y0, x1, y1 = _ink_box(alpha, pix.width, pix.height)
    cut = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, x1 - x0, y1 - y0), 1)
    with_alpha.set_origin(-x0, -y0)
    cut.copy(with_alpha, cut.irect)  # every pixel of the cut comes from the picture
    while max(cut.width, cut.height) > LONGEST_SIDE:
        cut.shrink(1)
    return cut.tobytes("png")


def size_of(png: bytes) -> tuple[int, int]:
    """Width and height of a saved picture, in pixels."""
    pix = _open(png)
    return pix.width, pix.height
