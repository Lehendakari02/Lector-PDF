"""Putting a password on a PDF, taking it off or changing it («Contraseña»).

The result is always a new file: the original stays as it was, so a password
that is forgotten never locks the only copy. The protection is AES-256, the
strongest the PDF standard has, which Adobe Reader, browsers and other
viewers open. Whoever knows the password can do everything with the
document (print it, copy from it, fill it in, sign it).

PyMuPDF writes the protection inside the last part of the file (the
trailer). The signing library needs it as an object of its own, as most
programs write it, so a small part is added at the end of the file with the
same protection as an object (``protection_apart``). Thus a document
protected here can be signed with a certificate afterwards.
"""

import os
import re
from pathlib import Path

from app.core.combine import CombineError, NeedsPassword, Source, _open

MIN_LENGTH = 4  # characters


class ProtectionError(CombineError):
    """The protection cannot be changed or the copy cannot be written."""


def state_of(path: str | Path) -> str:
    """«none» (anyone opens it), «password» (it asks for one to open it) or
    «restricted» (it opens, but its author keeps some things from being done
    and only the author's password changes that)."""
    import pymupdf

    try:
        with pymupdf.open(path, filetype="pdf") as doc:
            if doc.xref_get_key(-1, "Encrypt")[0] == "null":
                return "none"
            return "password" if doc.needs_pass else "restricted"
    except Exception as error:  # PyMuPDF raises several unrelated error types
        raise ProtectionError(f"{Path(path).name} cannot be read: {error}") from error


def protect(source: Source, target: Path, password: str) -> Path:
    """A copy of ``source`` that asks for ``password`` to be opened."""
    import pymupdf

    if len(password) < MIN_LENGTH:
        raise ProtectionError("the password is too short")
    return _write_copy(
        source,
        target,
        password,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw=password,
        user_pw=password,
        permissions=-1,  # who opens it may do everything
    )


def unprotect(source: Source, target: Path) -> Path:
    """A copy of ``source`` (opened with its password) that asks for none."""
    import pymupdf

    return _write_copy(source, target, None, encryption=pymupdf.PDF_ENCRYPT_NONE)


def _write_copy(source: Source, target: Path, password: str | None, **options) -> Path:
    target = Path(target)
    if target.resolve() == Path(source.path).resolve():
        raise ProtectionError("the copy cannot go over the original")
    doc = _open(source)
    try:
        if state_of(source.path) == "restricted":
            raise ProtectionError("only its author can change this protection")
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            doc.save(temporary, garbage=3, deflate=True, **options)
            if password:
                protection_apart(temporary, password)
            _check(temporary, password, doc.page_count)
            os.replace(temporary, target)
        except (ProtectionError, NeedsPassword):
            temporary.unlink(missing_ok=True)
            raise
        except Exception as error:  # PyMuPDF raises several unrelated error types
            temporary.unlink(missing_ok=True)
            raise ProtectionError(f"{target.name} cannot be written: {error}") from error
    finally:
        doc.close()
    return target


def _check(path: Path, password: str | None, pages: int) -> None:
    import pymupdf

    with pymupdf.open(path, filetype="pdf") as written:
        if bool(written.needs_pass) != bool(password):
            raise ProtectionError("the copy is not protected as it should be")
        if password and not written.authenticate(password):
            raise ProtectionError("the copy does not open with the password")
        if written.page_count != pages:
            raise ProtectionError("the copy does not have the same pages")


_STARTXREF = re.compile(rb"startxref\s+(\d+)\s+%%EOF\s*$")


def protection_apart(path: str | Path, password: str | None = None) -> bool:
    """If the protection of the PDF at ``path`` is written inside its
    trailer (as PyMuPDF writes it), add at the end of the file a part with
    the same protection as an object of its own. Returns whether it did.

    Nothing of the document changes: the protection is the same, only where
    it is written. Only for files that end with a classic cross-reference
    table, as PyMuPDF writes them without object streams."""
    import pymupdf

    path = Path(path)
    data = path.read_bytes()
    found = _STARTXREF.search(data[-64:])
    if found is None:
        return False
    previous = int(found.group(1))
    if data[previous : previous + 4] != b"xref":
        return False
    with pymupdf.open(path, filetype="pdf") as doc:
        if doc.needs_pass and not (password and doc.authenticate(password)):
            raise ProtectionError("the file does not open with the password")
        kind, protection = doc.xref_get_key(-1, "Encrypt")
        if kind != "dict":
            return False
        number = doc.xref_length()
        trailer = doc.pdf_trailer()
    keys = []
    for key in ("Root", "Info"):
        reference = re.search(rf"/{key}\s+(\d+\s+\d+\s+R)", trailer)
        if reference:
            keys.append(f"/{key} {reference.group(1)}")
    identifier = re.search(r"/ID\s*\[[^\]]*\]", trailer)
    if identifier:
        keys.append(identifier.group(0))
    start = len(data) + 1  # after the new line below
    part = f"\n{number} 0 obj\n{protection}\nendobj\n".encode("latin-1")
    table = len(data) + len(part)
    ending = (
        f"xref\n0 1\n0000000000 65535 f \n{number} 1\n{start:010d} 00000 n \n"
        f"trailer\n<</Size {number + 1}/Prev {previous}{''.join(keys)}"
        f"/Encrypt {number} 0 R>>\nstartxref\n{table}\n%%EOF\n"
    ).encode("latin-1")
    with open(path, "ab") as file:
        file.write(part + ending)
        file.flush()
        os.fsync(file.fileno())
    return True
