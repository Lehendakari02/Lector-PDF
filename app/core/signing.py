"""Signs PDFs with a digital certificate (PAdES, the European standard).

Two ways to reach the certificate:
- the Windows certificate store, where the FNMT certificate usually is
  (``WindowsStoreSigner``, through ``app.core.windows_store``);
- a ``.p12`` / ``.pfx`` file with its password (``load_p12_signer``).

The signature is added at the end of the file ("incremental"), so signatures
already in the document stay valid. It can be invisible, or visible: a box on
a page with the name of who signs, the date and, if wanted, the handwritten
signature (``Visible``). A timestamp from a timestamping server can be added
(``TimestampServer``): only a fingerprint of the document is sent, never the
document itself.
"""

import contextlib
import hashlib
import io
import os
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asn1crypto import tsp, x509
from pyhanko import stamp
from pyhanko.pdf_utils import generic, layout
from pyhanko.pdf_utils.crypt import AuthStatus
from pyhanko.pdf_utils.crypt.permissions import StandardPermissions
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers
from pyhanko.sign.signers import Signer
from pyhanko.sign.timestamps import TimeStamper
from pyhanko_certvalidator.registry import SimpleCertificateStore

from app.core import windows_store
from app.core.windows_store import StoreCertificate

FIELD_PREFIX = "Firma"
MAX_CHAIN_LENGTH = 10
# A free timestamping service, trusted by Adobe Reader. It can be changed in the
# settings (for example to a qualified Spanish one).
DEFAULT_TIMESTAMP_SERVER = "http://timestamp.digicert.com"
TIMESTAMP_TIMEOUT = 15  # seconds
BOX_SIZE = (170.0, 56.0)  # a visible signature, as shown: 6 by 2 centimetres


class SigningError(Exception):
    """The document could not be signed. The original file is untouched."""


class CertificateExpired(SigningError):
    """The certificate is out of date (or not valid yet): validators refuse it."""


class NotForSigning(SigningError):
    """The certificate is meant for other uses (encrypting, logging in)."""


class PasswordProtected(SigningError):
    """The document asks for a password, and none (or a wrong one) was given."""


class NotAllowed(SigningError):
    """The author of the document does not allow filling it in or signing it."""


class TimestampFailed(SigningError):
    """The timestamping server could not be reached or gave a bad answer."""


@dataclass(frozen=True)
class Visible:
    """Where a visible signature goes and what it shows.

    ``rect`` is in the coordinates of the page as shown (turned pages too),
    like everything the view hands over. ``png`` is the handwritten signature
    to show at its left, if wanted.
    """

    page: int
    rect: tuple[float, float, float, float]
    png: bytes | None = None


class TimestampServer(TimeStamper):
    """Asks a timestamping server (RFC 3161) over HTTP, with the standard library."""

    def __init__(self, url: str, timeout: float = TIMESTAMP_TIMEOUT) -> None:
        super().__init__()
        self.url = url
        self.timeout = timeout

    async def async_request_tsa_response(self, req: tsp.TimeStampReq) -> tsp.TimeStampResp:
        request = urllib.request.Request(
            self.url,
            data=req.dump(),
            headers={"Content-Type": "application/timestamp-query"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                if "timestamp-reply" not in answer.headers.get("Content-Type", ""):
                    raise TimestampFailed("The timestamping server did not answer properly")
                return tsp.TimeStampResp.load(answer.read())
        except TimestampFailed:
            raise
        except Exception as exc:
            raise TimestampFailed(f"The timestamping server could not be reached: {exc}") from exc


def signer_name(signer: Signer) -> str:
    """The name on the certificate, as validators show it."""
    subject = signer.signing_cert.subject.native
    return str(subject.get("common_name") or subject.get("organization_name") or "")


def appearance(width: float, height: float, name: str, when: str, png: bytes | None) -> bytes:
    """A one-page PDF, the size of the box as shown, with what the visible
    signature shows: the handwritten signature at the left (if any), and who
    signs and when."""
    import pymupdf

    with pymupdf.open() as doc:
        page = doc.new_page(width=width, height=height)
        page.draw_rect(page.rect, color=(0.55, 0.6, 0.7), width=0.8)
        text_left = 4.0
        if png:
            picture = pymupdf.Rect(3, 3, width * 0.42, height - 3)
            page.insert_image(picture, stream=png, keep_proportion=True)
            text_left = width * 0.44
        text = f"Firmado digitalmente por\n{name}\nFecha: {when}"
        box = pymupdf.Rect(text_left, 3, width - 3, height - 2)
        size = 9.0
        while size > 4 and page.insert_textbox(box, text, fontsize=size, fontname="helv") < 0:
            size -= 0.5
        return doc.tobytes(garbage=3, deflate=True)


def _place(
    data: bytes, visible: Visible, picture: bytes, password: str | None = None
) -> tuple[tuple, bytes]:
    """The box in the coordinates of the PDF file (bottom up, page not turned)
    and the appearance turned to look upright on a turned page."""
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass and not doc.authenticate(password or ""):
            raise PasswordProtected("The document asks for a password")
        if not 0 <= visible.page < doc.page_count:
            raise SigningError("That page is not in the document")
        page = doc[visible.page]
        shown = pymupdf.Rect(visible.rect) & page.rect  # kept inside the page
        if shown.is_empty:
            raise SigningError("The signature box is outside the page")
        unturned = shown * page.derotation_matrix
        rotation = page.rotation
        # On a turned page PyMuPDF's matrix forgets where the page is cropped
        # (CropBox); the page not turned has it right. Only this copy changes.
        page.set_rotation(0)
        in_file = unturned * ~page.transformation_matrix
    if rotation:
        with pymupdf.open() as turned, pymupdf.open(stream=picture, filetype="pdf") as upright:
            sheet = turned.new_page(width=unturned.width, height=unturned.height)
            sheet.show_pdf_page(sheet.rect, upright, 0, rotate=rotation)
            picture = turned.tobytes(garbage=3, deflate=True)
    box = (in_file.x0, in_file.y0, in_file.x1, in_file.y1)
    return box, picture


def build_chain(
    certificate: x509.Certificate, candidates: list[x509.Certificate]
) -> list[x509.Certificate]:
    """Authorities that vouch for ``certificate``, nearest first.

    Validators (VALIDe, Adobe) want them inside the signature. The chain stops
    at a root (a certificate that vouches for itself) or when one is missing.
    """
    chain: list[x509.Certificate] = []
    current = certificate
    while len(chain) < MAX_CHAIN_LENGTH and current.subject != current.issuer:
        wanted_key = current.authority_key_identifier
        parent = next(
            (
                candidate
                for candidate in candidates
                if candidate.subject == current.issuer
                and (wanted_key is None or candidate.key_identifier in (None, wanted_key))
            ),
            None,
        )
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return chain


class WindowsStoreSigner(Signer):
    """Signs with a certificate whose private key stays inside Windows."""

    def __init__(
        self,
        certificate: StoreCertificate,
        window_handle: int | None = None,
        chain_candidates: list[bytes] | None = None,
    ) -> None:
        signing_cert = x509.Certificate.load(certificate.der)
        if chain_candidates is None:
            chain_candidates = windows_store.chain_candidates()
        authorities = []
        for der in chain_candidates:
            with contextlib.suppress(Exception):
                authorities.append(x509.Certificate.load(der))
        self.chain = build_chain(signing_cert, authorities)
        self.thumbprint = certificate.thumbprint
        self.window_handle = window_handle
        self.key_algorithm = signing_cert.public_key.algorithm
        self._signature_size = signing_cert.public_key.byte_size
        self._open_key: windows_store.OpenKey | None = None
        super().__init__(
            signing_cert=signing_cert,
            cert_registry=SimpleCertificateStore.from_certs(self.chain),
        )

    async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
        if dry_run:
            # Only the size matters here; do not make Windows ask for the PIN twice.
            extra = 0 if self.key_algorithm == "rsa" else self._signature_size + 9
            return bytes(self._signature_size + extra)
        digest = hashlib.new(digest_algorithm, data).digest()
        if self._open_key is not None:
            return self._open_key.sign(digest, digest_algorithm, self.key_algorithm)
        return windows_store.sign_digest(
            self.thumbprint, digest, digest_algorithm, self.key_algorithm, self.window_handle
        )

    @contextlib.contextmanager
    def key_kept_open(self):
        """While inside, every signature uses the same open key, so that
        Windows asks for the PIN once if the key allows it."""
        with windows_store.OpenKey(self.thumbprint, self.window_handle) as key:
            self._open_key = key
            try:
                yield self
            finally:
                self._open_key = None


def key_kept_open(signer: Signer):
    """``signer.key_kept_open()`` for a certificate of Windows; nothing to keep
    open for a file (its password was given once already)."""
    if isinstance(signer, WindowsStoreSigner):
        return signer.key_kept_open()
    return contextlib.nullcontext(signer)


def load_p12_signer(path: str | Path, password: str) -> Signer:
    """A signer from a ``.p12`` / ``.pfx`` file. Wrong password: ``SigningError``."""
    try:
        signer = signers.SimpleSigner.load_pkcs12(str(path), passphrase=password.encode("utf-8"))
    except Exception as exc:
        raise SigningError(f"Cannot read the certificate file: {exc}") from exc
    if signer is None:
        raise SigningError("Wrong password, or the file is not a certificate with its key")
    check_usable(signer.signing_cert)
    _complete_chain(signer)
    return signer


def _complete_chain(signer: Signer) -> None:
    """Add the authorities Windows knows that the file did not bring: validators
    want the whole chain inside the signature."""
    if not windows_store.is_available():
        return
    with contextlib.suppress(Exception):
        known = []
        for der in windows_store.chain_candidates():
            with contextlib.suppress(Exception):
                known.append(x509.Certificate.load(der))
        registry = signer.cert_registry
        for authority in build_chain(signer.signing_cert, list(registry) + known):
            registry.register(authority)


def check_usable(certificate: x509.Certificate, now: datetime | None = None) -> None:
    """Refuse a certificate that validators would refuse anyway: out of date,
    or not meant for signing (``CertificateExpired``, ``NotForSigning``)."""
    now = now or datetime.now(UTC)
    if not certificate.not_valid_before <= now <= certificate.not_valid_after:
        raise CertificateExpired(
            f"The certificate is valid from {certificate.not_valid_before:%d/%m/%Y} "
            f"to {certificate.not_valid_after:%d/%m/%Y}"
        )
    usage = certificate.key_usage_value
    if usage is not None and not {"digital_signature", "non_repudiation"} & set(usage.native):
        raise NotForSigning("The certificate is not meant for signing")


def next_field_name(reader: PdfFileReader) -> str:
    """A name for the new signature that no field of the document uses yet
    (a text field called «Firma1» is common in forms)."""
    used = {name for name, _value, _ref in fields.enumerate_sig_fields(reader)}
    with contextlib.suppress(Exception):
        for field in reader.root["/AcroForm"]["/Fields"]:
            with contextlib.suppress(Exception):
                used.add(str(field.get_object()["/T"]))
    number = 1
    while f"{FIELD_PREFIX}{number}" in used:
        number += 1
    return f"{FIELD_PREFIX}{number}"


# What the author of a protected document must allow for it to be signed:
# adding annotations and filling in, or at least filling in (which includes
# signing), as Adobe Reader asks.
_SIGNING_ALLOWED = (
    StandardPermissions.ALLOW_ANNOTS_FORM_FILLING | StandardPermissions.ALLOW_FORM_FILLING
)


def _unlock(writer: IncrementalPdfFileWriter, password: str | None) -> None:
    """Open a protected document with its password (none for one that only
    has permissions). The signature is then written protected the same way."""
    if not writer.prev.encrypted:
        return
    try:
        result = writer.encrypt(password or "")
    except Exception as exc:
        raise SigningError(f"This protection is not supported: {exc}") from exc
    if result.status == AuthStatus.FAILED:
        raise PasswordProtected("The document asks for a password")
    if result.status == AuthStatus.USER and not result.permission_flags & _SIGNING_ALLOWED:
        raise NotAllowed("The author of the document does not allow signing it")
    if not isinstance(writer._encrypt, generic.IndirectObject):
        # Some programs (PyMuPDF among them) write the protection inside the
        # file's trailer. The signing library needs it as an object of its own:
        # the new part of the file gets one. Tried with Adobe's rules and
        # PyMuPDF; with an opening password the result cannot be read by
        # PyMuPDF, so those are refused rather than spoilt.
        if password:
            raise SigningError("This protection with a password is not supported")
        writer._encrypt = writer.add_object(writer._encrypt)


def _open_for_signing(data: bytes, password: str | None = None) -> IncrementalPdfFileWriter:
    """Prepare the document and check that the signing library can write it."""
    writer = IncrementalPdfFileWriter(io.BytesIO(data), strict=False)
    _unlock(writer, password)
    next_field_name(writer.prev)
    # A rehearsal without signature. It fails here, and not after Windows has
    # asked for the PIN, with documents the library cannot handle.
    rehearsal = IncrementalPdfFileWriter(io.BytesIO(data), strict=False)
    _unlock(rehearsal, password)
    rehearsal.write(io.BytesIO())
    return writer


def _rewritten(data: bytes) -> bytes:
    """The same document written again, cleanly, by the PDF engine.

    Some real documents (for example the consolidated laws of the BOE) contain
    details the signing library cannot read. Writing the document again fixes
    them, but would break signatures already in it, so those are refused.
    """
    import pymupdf

    from app.core.save_checks import has_signed_field

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise PasswordProtected("The document asks for a password")
        if doc.xref_get_key(-1, "Encrypt")[0] != "null":
            # Written again it would lose its protection.
            raise SigningError("This protected document cannot be prepared for signing")
        if doc.get_sigflags() > 0 and has_signed_field(doc):
            raise SigningError(
                "This document already has signatures and cannot be prepared without breaking them"
            )
        return doc.tobytes(garbage=0, deflate=True)


def sign_pdf(
    source: str | Path,
    target: str | Path,
    signer: Signer,
    visible: Visible | None = None,
    timestamp_server: str = "",
    password: str | None = None,
) -> Path:
    """Write to ``target`` a copy of ``source`` with a PAdES signature:
    invisible, or visible where ``visible`` says; with a timestamp from
    ``timestamp_server`` if one is given (``TimestampFailed`` if it fails).
    ``password``: the one the document was opened with, if it has one.

    A problem with the key (a wrong PIN, the card out of its reader) comes
    out as the ``StoreError`` of Windows, not as a problem of the document.

    The copy is written whole to a temporary file next to ``target`` and only
    then given its name, so a failure never leaves half a file.
    """
    source, target = Path(source), Path(target)
    temporary = picture_file = None
    try:
        data = source.read_bytes()
        try:
            writer = _open_for_signing(data, password)
        except SigningError:
            raise
        except Exception:
            writer = _open_for_signing(_rewritten(data))
        field_name = next_field_name(writer.prev)
        metadata = signers.PdfSignatureMetadata(
            field_name=field_name,
            md_algorithm="sha256",
            subfilter=fields.SigSeedSubFilter.PADES,
            name=signer_name(signer) or None,
        )
        options = {}
        if visible is not None:
            width, height = visible.rect[2] - visible.rect[0], visible.rect[3] - visible.rect[1]
            when = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
            upright = appearance(width, height, signer_name(signer), when, visible.png)
            box, picture = _place(writer_bytes(writer), visible, upright, password)
            handle, name = tempfile.mkstemp(prefix="lectorpdf-aspecto-", suffix=".pdf")
            picture_file = Path(name)
            with os.fdopen(handle, "wb") as out:
                out.write(picture)
            options["new_field_spec"] = fields.SigFieldSpec(
                field_name, on_page=visible.page, box=box
            )
            options["stamp_style"] = stamp.StaticStampStyle.from_pdf_file(
                str(picture_file),
                border_width=0,
                background_opacity=1.0,
                background_layout=layout.SimpleBoxLayoutRule(
                    x_align=layout.AxisAlignment.ALIGN_MID,
                    y_align=layout.AxisAlignment.ALIGN_MID,
                    margins=layout.Margins(0, 0, 0, 0),
                ),
            )
        if timestamp_server:
            options["timestamper"] = TimestampServer(timestamp_server)
        handle, name = tempfile.mkstemp(dir=target.parent, prefix=".firmando-", suffix=".tmp")
        temporary = Path(name)
        with os.fdopen(handle, "wb+") as out:
            signers.PdfSigner(metadata, signer, **options).sign_pdf(writer, output=out)
        os.replace(temporary, target)
    except (windows_store.StoreError, SigningError):
        _remove(temporary)
        raise
    except Exception as exc:
        _remove(temporary)
        cause = exc
        while cause is not None and not isinstance(cause, (SigningError, windows_store.StoreError)):
            cause = cause.__cause__ or cause.__context__
        if isinstance(cause, TimestampFailed):
            raise TimestampFailed(str(cause)) from exc
        if isinstance(cause, windows_store.StoreError):
            raise cause from exc  # the key, not the document
        raise SigningError(f"The document could not be signed: {exc}") from exc
    finally:
        _remove(picture_file)
    return target


def writer_bytes(writer: IncrementalPdfFileWriter) -> bytes:
    """The document the writer adds to, as it was read."""
    stream = writer.prev.stream
    position = stream.tell()
    stream.seek(0)
    data = stream.read()
    stream.seek(position)
    return data


def _remove(path: Path | None) -> None:
    if path is not None:
        with contextlib.suppress(OSError):
            path.unlink()
