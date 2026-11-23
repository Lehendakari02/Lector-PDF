"""Writing a PDF to disk without ever leaving it half written.

The whole document is first written to a temporary file next to the target and
checked; only then does it take the target's place, in one step. If the
computer goes off or the program is killed at any moment, the target is either
the complete old file or the complete new one, never something in between.

If the target cannot be replaced (another program holds it, a cloud folder is
syncing it, it is read-only, the disk is full) a ``SaveError`` says why, and
nothing has been lost: the old file is untouched and the document in memory
still has its changes.

A PDF signed with a certificate is written "adding at the end" (incremental),
as Adobe Reader does: what was signed stays byte for byte as it was, followed
by the changes. Notes, marks and filled fields then keep the signatures valid.
"""

import contextlib
import errno
import os
import time
from pathlib import Path

LOCKED = "locked"  # another program (or a cloud folder syncing) holds the file
READ_ONLY = "read_only"  # the file or its folder cannot be written
NO_SPACE = "no_space"  # the disk is full
FAILED = "failed"  # anything else

TEMP_SUFFIX = ".guardando"
REPLACE_TRIES = 6
REPLACE_PAUSE = 0.25  # seconds; antivirus and sync programs let go in a moment
# Only for the automatic tests: file names that behave as if another program
# held them (separated by "|"), on systems where a file in use can be replaced.
TEST_LOCKED_FILES = "LECTOR_PDF_TEST_LOCKED_FILES"


class SaveError(Exception):
    """The PDF could not be saved. ``kind`` is one of the constants above."""

    def __init__(self, kind: str, details: str = "") -> None:
        super().__init__(f"{kind}: {details}" if details else kind)
        self.kind = kind
        self.details = details


def temp_path_for(target: str | Path) -> Path:
    """The temporary file used while saving ``target``: next to it, same disk."""
    target = Path(target)
    return target.with_name(f".{target.name}{TEMP_SUFFIX}")


def _kind_of(error: OSError, target: Path) -> str:
    if error.errno in (errno.ENOSPC, errno.EDQUOT):
        return NO_SPACE
    if error.errno == errno.EROFS:
        return READ_ONLY
    if isinstance(error, PermissionError) or error.errno in (errno.EACCES, errno.EBUSY):
        folder = target.parent
        unwritable_file = target.exists() and not os.access(target, os.W_OK)
        if unwritable_file or not os.access(folder, os.W_OK):
            return READ_ONLY
        return LOCKED
    return FAILED


def keeps_signatures(doc) -> bool:
    """Whether ``doc`` is signed with a certificate and can be saved adding the
    changes at the end, which keeps its signatures."""
    from app.core.save_checks import has_signed_field

    try:
        return bool(
            doc.get_sigflags() > 0
            and has_signed_field(doc)
            and doc.can_save_incrementally()
            and not doc.is_repaired
        )
    except Exception:  # PyMuPDF raises several unrelated error types
        return False


def _added_at_the_end(doc) -> bytes:
    """The whole file: the document as it was read, then the changes."""
    import io

    import pymupdf
    from pymupdf import mupdf

    options = mupdf.PdfWriteOptions()
    options.do_incremental = 1
    options.do_encrypt = pymupdf.PDF_ENCRYPT_KEEP
    output = io.BytesIO()
    writer = pymupdf.JM_new_output_fileptr(output)
    mupdf.pdf_write_document(pymupdf._as_pdf_document(doc), writer, options)
    writer.fz_close_output()
    return output.getvalue()


def write_copy(doc, target: str | Path, password: str | None = None) -> Path:
    """Write the open PyMuPDF document ``doc`` whole into the temporary file of ``target``.

    A signed document is written adding the changes at the end, so that its
    signatures stay valid (``keeps_signatures``).

    The copy is pushed to the disk and opened again to check it is a complete
    PDF with the same pages. Returns the temporary file; ``target`` is not touched.
    """
    import pymupdf

    target = Path(target)
    temp = temp_path_for(target)
    try:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()  # left by a save that was cut short
        # A complete rewrite; the protection (password) of the document is kept.
        # garbage=1 leaves out what nothing uses any more (a text or a note
        # taken away), so that it is really gone from the file. The objects are
        # not renumbered, and the open document keeps them for Deshacer.
        if keeps_signatures(doc):
            data = _added_at_the_end(doc)
            with open(temp, "wb") as written:
                written.write(data)
                written.flush()
                os.fsync(written.fileno())
        else:
            doc.save(str(temp), garbage=1, deflate=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
            with open(temp, "rb+") as written:
                os.fsync(written.fileno())
    except OSError as error:
        _discard(temp)
        raise SaveError(_kind_of(error, target), str(error)) from error
    except Exception as error:  # PyMuPDF raises several unrelated error types
        _discard(temp)
        kind = FAILED
        if not os.access(target.parent, os.W_OK):
            kind = READ_ONLY
        raise SaveError(kind, str(error)) from error
    try:
        with pymupdf.open(str(temp), filetype="pdf") as check:
            if check.needs_pass and not (password and check.authenticate(password)):
                raise ValueError("the copy cannot be opened with the password")
            if check.page_count != doc.page_count:
                raise ValueError("the copy does not have the same pages")
    except Exception as error:
        _discard(temp)
        raise SaveError(FAILED, f"the written copy is not right: {error}") from error
    return temp


def put_in_place(
    temp: str | Path,
    target: str | Path,
    tries: int = REPLACE_TRIES,
    pause: float = REPLACE_PAUSE,
) -> None:
    """Make the finished temporary file take the place of ``target``, in one step.

    Tried a few times: an antivirus or a sync program often holds a file only
    for an instant. On failure the temporary file is left where it is (the
    caller decides) and ``target`` is untouched.
    """
    temp, target = Path(temp), Path(target)
    error: OSError | None = None
    for attempt in range(max(1, tries)):
        try:
            if target.name in os.environ.get(TEST_LOCKED_FILES, "").split("|"):
                raise PermissionError(errno.EACCES, "held by another program (test)")
            os.replace(temp, target)
        except OSError as failed:
            error = failed
            if _kind_of(failed, target) != LOCKED:
                break
            if attempt + 1 < tries:
                time.sleep(pause)
        else:
            _sync_folder(target.parent)
            return
    raise SaveError(_kind_of(error, target), str(error)) from error


def save_to(doc, target: str | Path, password: str | None = None) -> None:
    """Save ``doc`` into ``target`` safely. ``target`` must not be open in ``doc``
    on Windows (a file in use cannot be replaced there): see ``render_service``.
    """
    temp = write_copy(doc, target, password)
    try:
        put_in_place(temp, target)
    except SaveError:
        _discard(temp)
        raise


def _discard(temp: Path) -> None:
    with contextlib.suppress(OSError):
        temp.unlink()


def _sync_folder(folder: Path) -> None:
    """Make the change of name itself reach the disk (not possible on Windows)."""
    if os.name == "nt":
        return
    with contextlib.suppress(OSError):
        handle = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
