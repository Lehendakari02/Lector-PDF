"""Opening PDF files and reading their basic facts."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf


class PdfOpenError(Exception):
    """The file could not be opened as a PDF (missing, damaged or not a PDF)."""


@dataclass(frozen=True)
class DocumentInfo:
    """Basic facts about a PDF file."""

    path: Path
    page_count: int
    needs_password: bool


def read_document_info(path: str | Path) -> DocumentInfo:
    """Open the PDF at ``path`` just long enough to read its basic facts.

    Raises ``PdfOpenError`` instead of letting library errors escape, so callers
    can show a friendly message and the program never closes on a bad file.
    """
    path = Path(path)
    if not path.is_file():
        raise PdfOpenError(f"File not found: {path}")
    try:
        with pymupdf.open(path, filetype="pdf") as doc:
            return DocumentInfo(
                path=path,
                page_count=doc.page_count,
                needs_password=bool(doc.needs_pass),
            )
    except Exception as exc:  # PyMuPDF raises several unrelated error types
        raise PdfOpenError(f"Cannot open {path.name}: {exc}") from exc


@dataclass(frozen=True)
class PageSize:
    """Size of a page in points (1/72 inch), as it is shown (rotation applied)."""

    width: float
    height: float


class PdfDocument:
    """An open PDF: what the interface needs to lay out its pages.

    Drawing the pages is done elsewhere (``app.core.render_service``), in a
    separate process, so this object stays cheap and never blocks the window.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise PdfOpenError(f"File not found: {self.path}")
        try:
            self._doc = pymupdf.open(self.path, filetype="pdf")
        except Exception as exc:  # PyMuPDF raises several unrelated error types
            raise PdfOpenError(f"Cannot open {self.path.name}: {exc}") from exc
        self.needs_password = bool(self._doc.needs_pass)
        self._sizes: list[PageSize] | None = None

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def page_sizes(self) -> list[PageSize]:
        """Sizes of all pages. Read once; fast even with hundreds of pages."""
        if self._sizes is None:
            try:
                self._sizes = [PageSize(page.rect.width, page.rect.height) for page in self._doc]
            except Exception as exc:
                raise PdfOpenError(f"Cannot read {self.path.name}: {exc}") from exc
        return self._sizes

    def close(self) -> None:
        if not self._doc.is_closed:
            self._doc.close()

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def engine_version() -> str:
    """Return the version of the PDF engine, for the error report and "About"."""
    return pymupdf.VersionBind
