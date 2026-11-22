"""What has to be looked at before saving over a PDF.

Three things deserve a warning every time, whatever the settings say:

- the PDF is signed: saving it with changes makes the signature invalid;
- another program has changed the file since it was opened: saving here would
  throw away what that program did;
- the file lives in a temporary folder (an attachment opened from the mail):
  what is saved there can disappear by itself.

Nothing here asks anything: it only tells. The window decides what to do.
"""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

SIGNED = "signed"
CHANGED_OUTSIDE = "changed_outside"
TEMPORARY = "temporary"

# Folders where mail programs and browsers leave what is opened from them.
_TEMPORARY_PARTS = (
    "content.outlook",
    "inetcache",
    "temporary internet files",
    "appdata/local/temp",
    "appdata/local/microsoft/windows/inetcache",
)


@dataclass(frozen=True)
class FileStamp:
    """Enough of a file to notice that somebody has written it."""

    size: int
    modified: int  # nanoseconds


def stamp_of(path: str | Path) -> FileStamp | None:
    """The stamp of the file as it is now, or None if it is not there."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return FileStamp(status.st_size, status.st_mtime_ns)


def changed_outside(path: str | Path, known: FileStamp | None) -> bool:
    """Whether the file is no longer as it was when ``known`` was taken.

    A file that has disappeared counts as changed. With nothing known there is
    nothing to compare: False.
    """
    if known is None:
        return False
    return stamp_of(path) != known


def is_signed(path: str | Path, password: str | None = None) -> bool:
    """Whether the PDF carries at least one signature made with a certificate.

    An empty signature field (a place to sign, not signed yet) does not count.
    A file that cannot be read is taken as not signed: saving will say what
    is wrong with it.
    """
    import pymupdf

    try:
        with pymupdf.open(str(path), filetype="pdf") as doc:
            if doc.needs_pass and not (password and doc.authenticate(password)):
                return False
            if doc.get_sigflags() <= 0:
                return False
            # The form's own list of fields, not every page: it is asked at
            # every save, and a document of hundreds of pages must not wait.
            return _has_signed_field(doc)
    except Exception:  # PyMuPDF raises several unrelated error types
        return False


_REFERENCE = re.compile(r"(\d+)\s+0\s+R")


def _has_signed_field(doc) -> bool:
    """Whether a field of the form is a signature with a value (signed)."""
    kind, value = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")
    if kind == "xref":
        kind, value = "array", doc.xref_object(int(value.split()[0]), compressed=True)
    if kind != "array":
        return False
    waiting = [(int(xref), False) for xref in _REFERENCE.findall(value)]
    seen: set[int] = set()
    while waiting:
        xref, inherited_sig = waiting.pop()
        if xref in seen or not 0 < xref < doc.xref_length() or len(seen) > 100_000:
            continue
        seen.add(xref)
        field_type = doc.xref_get_key(xref, "FT")
        is_sig = field_type == ("name", "/Sig") or (field_type[0] == "null" and inherited_sig)
        if is_sig and doc.xref_get_key(xref, "V")[0] in ("xref", "dict"):
            return True
        kids_kind, kids = doc.xref_get_key(xref, "Kids")
        if kids_kind == "xref":
            kids_kind, kids = "array", doc.xref_object(int(kids.split()[0]), compressed=True)
        if kids_kind == "array":
            waiting += [(int(kid), is_sig) for kid in _REFERENCE.findall(kids)]
    return False


def in_temporary_folder(path: str | Path, temp_dir: str | Path | None = None) -> bool:
    """Whether the file is somewhere the system may clear by itself."""
    full = Path(path).absolute()
    folder = Path(temp_dir if temp_dir is not None else tempfile.gettempdir()).absolute()
    whole = _comparable(full)
    base = _comparable(folder)
    if base and (whole == base or whole.startswith(base + "/")):
        return True
    return any(f"/{part}/" in whole for part in _TEMPORARY_PARTS)


def _comparable(path: Path) -> str:
    return os.path.normcase(str(path)).replace("\\", "/").lower().rstrip("/")


def warnings_for(
    path: str | Path,
    known: FileStamp | None,
    password: str | None = None,
    temp_dir: str | Path | None = None,
) -> list[str]:
    """Every reason to stop and ask before saving over ``path``, the gravest first."""
    found = []
    if changed_outside(path, known):
        found.append(CHANGED_OUTSIDE)
    if is_signed(path, password):
        found.append(SIGNED)
    if in_temporary_folder(path, temp_dir):
        found.append(TEMPORARY)
    return found
