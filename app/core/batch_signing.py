"""Sign several documents at once with the same certificate.

The certificate is chosen once, and with a certificate of Windows its key is
held open for the whole batch, so the PIN is asked once when the key allows
it. Every document becomes a copy «name-firmado.pdf» in its own folder; the
originals are never touched. The signature is invisible or visible in the
same place of each document: a corner of its first or last page.

A document that cannot be signed (a password, a damaged file) is left out and
told; the others go on. Cancelling the PIN window stops the batch.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from pyhanko.sign.signers import Signer

from app.core.signing import (
    BOX_SIZE,
    PasswordProtected,
    SigningError,
    TimestampFailed,
    Visible,
    key_kept_open,
    sign_pdf,
)

FIRST, LAST = "primera", "ultima"
PAGES = (LAST, FIRST)
BOTTOM_RIGHT, BOTTOM_LEFT, TOP_RIGHT, TOP_LEFT = (
    "abajo-derecha",
    "abajo-izquierda",
    "arriba-derecha",
    "arriba-izquierda",
)
CORNERS = (BOTTOM_RIGHT, BOTTOM_LEFT, TOP_RIGHT, TOP_LEFT)
MARGIN = 36.0  # points between the box and the edges of the page: half an inch

# What went wrong with one document.
SIGNED, PASSWORD, FAILED = "firmado", "contraseña", "fallo"


@dataclass(frozen=True)
class Placement:
    """Where a visible signature goes in every document."""

    page: str = LAST
    corner: str = BOTTOM_RIGHT


@dataclass(frozen=True)
class Outcome:
    source: Path
    target: Path | None
    result: str  # SIGNED, PASSWORD or FAILED
    details: str = ""


def signed_copy_name(source: Path) -> Path:
    """«name-firmado.pdf» beside it; with a number if that name is taken."""
    stem = source.stem if source.stem.lower().endswith("-firmado") else f"{source.stem}-firmado"
    target = source.with_name(f"{stem}.pdf")
    number = 2
    while target.exists():
        target = source.with_name(f"{stem} ({number}).pdf")
        number += 1
    return target


def visible_in(path: Path, placement: Placement, png: bytes | None) -> Visible:
    """The box in the chosen corner of the chosen page of a document, as shown."""
    import pymupdf

    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise PasswordProtected("Documents with a password cannot be signed yet")
        number = 0 if placement.page == FIRST else doc.page_count - 1
        if number < 0:
            raise SigningError("The document has no pages")
        page = doc[number].rect
    width = min(BOX_SIZE[0], page.width)
    height = min(BOX_SIZE[1], page.height)
    margin_x = min(MARGIN, (page.width - width) / 2)
    margin_y = min(MARGIN, (page.height - height) / 2)
    left = placement.corner in (BOTTOM_LEFT, TOP_LEFT)
    top = placement.corner in (TOP_LEFT, TOP_RIGHT)
    x0 = margin_x if left else page.width - margin_x - width
    y0 = margin_y if top else page.height - margin_y - height
    return Visible(number, (x0, y0, x0 + width, y0 + height), png)


def sign_many(
    sources: Iterable[Path],
    signer: Signer,
    placement: Placement | None = None,
    png: bytes | None = None,
    timestamp_server: str = "",
    without_timestamp: Callable[[], bool] = lambda: False,
    progress: Callable[[int, Path], bool] = lambda _done, _path: True,
) -> list[Outcome]:
    """Sign each document into its «-firmado» copy. ``placement`` None:
    invisible. If the timestamping server fails, ``without_timestamp()`` says
    whether to go on without it (once for the whole batch). ``progress(n,
    path)`` is told before each one and stops the batch by answering False.
    Cancelling the PIN raises ``SigningCancelled`` with the outcomes so far
    in its ``outcomes``."""
    from app.core.windows_store import SigningCancelled

    outcomes: list[Outcome] = []
    with key_kept_open(signer):
        for done, source in enumerate(map(Path, sources)):
            if not progress(done, source):
                break
            target = signed_copy_name(source)
            try:
                visible = None if placement is None else visible_in(source, placement, png)
                try:
                    sign_pdf(source, target, signer, visible, timestamp_server)
                except TimestampFailed:
                    if not without_timestamp():
                        raise
                    timestamp_server = ""
                    sign_pdf(source, target, signer, visible)
            except SigningCancelled as cancelled:
                cancelled.outcomes = outcomes
                raise
            except PasswordProtected as error:
                outcomes.append(Outcome(source, None, PASSWORD, str(error)))
            except TimestampFailed as error:
                cancelled = SigningCancelled(str(error))
                cancelled.outcomes = outcomes
                raise cancelled from error
            except Exception as error:
                outcomes.append(Outcome(source, None, FAILED, str(error)))
            else:
                outcomes.append(Outcome(source, target, SIGNED))
    return outcomes
