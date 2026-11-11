"""Signs PDFs with a digital certificate (PAdES, the European standard).

Two ways to reach the certificate:
- the Windows certificate store, where the FNMT certificate usually is
  (``WindowsStoreSigner``, through ``app.core.windows_store``);
- a ``.p12`` / ``.pfx`` file with its password (``load_p12_signer``).

The signature is added at the end of the file ("incremental"), so signatures
already in the document stay valid.
"""

import contextlib
import hashlib
import io
import os
import tempfile
from pathlib import Path

from asn1crypto import x509
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers
from pyhanko.sign.signers import Signer
from pyhanko_certvalidator.registry import SimpleCertificateStore

from app.core import windows_store
from app.core.windows_store import StoreCertificate

FIELD_PREFIX = "Firma"
MAX_CHAIN_LENGTH = 10


class SigningError(Exception):
    """The document could not be signed. The original file is untouched."""


class PasswordProtected(SigningError):
    """The document asks for a password; signing those comes in a later phase."""


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
        return windows_store.sign_digest(
            self.thumbprint, digest, digest_algorithm, self.key_algorithm, self.window_handle
        )


def load_p12_signer(path: str | Path, password: str) -> Signer:
    """A signer from a ``.p12`` / ``.pfx`` file. Wrong password: ``SigningError``."""
    try:
        signer = signers.SimpleSigner.load_pkcs12(str(path), passphrase=password.encode("utf-8"))
    except Exception as exc:
        raise SigningError(f"Cannot read the certificate file: {exc}") from exc
    if signer is None:
        raise SigningError("Wrong password, or the file is not a certificate with its key")
    return signer


def next_field_name(reader: PdfFileReader) -> str:
    """A name for the new signature that no field of the document uses yet."""
    used = {name for name, _value, _ref in fields.enumerate_sig_fields(reader)}
    number = 1
    while f"{FIELD_PREFIX}{number}" in used:
        number += 1
    return f"{FIELD_PREFIX}{number}"


def _open_for_signing(data: bytes) -> IncrementalPdfFileWriter:
    """Prepare the document and check that the signing library can write it."""
    writer = IncrementalPdfFileWriter(io.BytesIO(data), strict=False)
    if writer.prev.encrypted:
        raise PasswordProtected("Documents with a password cannot be signed yet")
    next_field_name(writer.prev)
    # A rehearsal without signature. It fails here, and not after Windows has
    # asked for the PIN, with documents the library cannot handle.
    IncrementalPdfFileWriter(io.BytesIO(data), strict=False).write(io.BytesIO())
    return writer


def _rewritten(data: bytes) -> bytes:
    """The same document written again, cleanly, by the PDF engine.

    Some real documents (for example the consolidated laws of the BOE) contain
    details the signing library cannot read. Writing the document again fixes
    them, but would break signatures already in it, so those are refused.
    """
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise PasswordProtected("Documents with a password cannot be signed yet")
        if doc.get_sigflags() > 0:
            raise SigningError(
                "This document already has signatures and cannot be prepared without breaking them"
            )
        return doc.tobytes(garbage=0, deflate=True)


def sign_pdf(source: str | Path, target: str | Path, signer: Signer) -> Path:
    """Write to ``target`` a copy of ``source`` with an invisible PAdES signature.

    The copy is written whole to a temporary file next to ``target`` and only
    then given its name, so a failure never leaves half a file.
    """
    source, target = Path(source), Path(target)
    temporary = None
    try:
        data = source.read_bytes()
        try:
            writer = _open_for_signing(data)
        except SigningError:
            raise
        except Exception:
            writer = _open_for_signing(_rewritten(data))
        metadata = signers.PdfSignatureMetadata(
            field_name=next_field_name(writer.prev),
            md_algorithm="sha256",
            subfilter=fields.SigSeedSubFilter.PADES,
        )
        handle, name = tempfile.mkstemp(dir=target.parent, prefix=".firmando-", suffix=".tmp")
        temporary = Path(name)
        with os.fdopen(handle, "wb+") as out:
            signers.PdfSigner(metadata, signer).sign_pdf(writer, output=out)
        os.replace(temporary, target)
    except (windows_store.SigningCancelled, SigningError):
        _remove(temporary)
        raise
    except Exception as exc:
        _remove(temporary)
        raise SigningError(f"The document could not be signed: {exc}") from exc
    return target


def _remove(path: Path | None) -> None:
    if path is not None:
        with contextlib.suppress(OSError):
            path.unlink()
