"""Look at the signatures a PDF already has: who signed, when, and whether the
signature still holds.

Everything is checked on this computer, without the internet (principle 1):
- the signature matches the document as it was signed (nobody has changed
  those bytes), and what was added afterwards (more signatures, filled fields,
  annotations, or real changes);
- whether the certificate comes from an authority this computer trusts (the
  ones Windows trusts, which include the FNMT and the DNIe ones when their
  roots are installed).

It does not ask whether the certificate was revoked: that needs the internet.
For the official check there is VALIDe, and the window says so.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# What happened to the document after a signature.
UNCHANGED = "sin cambios"  # the signature covers the whole file
MORE_SIGNATURES = "mas firmas"  # only other signatures or validation data were added
FORM_FILLED = "campos"  # fields filled in or more signatures added afterwards (allowed)
ANNOTATED = "anotaciones"  # annotations were added (usually allowed)
CHANGED = "cambiado"  # the document was really changed after signing


@dataclass(frozen=True)
class SignatureReport:
    field: str
    signer: str
    issuer: str
    signed_at: datetime | None
    timestamped: bool
    intact: bool  # the signed bytes are exactly as signed and the maths holds
    trusted: bool  # the certificate comes from an authority this computer trusts
    after: str  # one of UNCHANGED, MORE_SIGNATURES, FORM_FILLED, ANNOTATED, CHANGED
    page: int | None = None  # where it is seen, if it is visible
    problem: str = ""  # it could not be checked at all

    @property
    def good(self) -> bool:
        """Intact, nothing serious changed afterwards and from a known authority."""
        return self.intact and self.trusted and self.after != CHANGED and not self.problem


def trusted_roots() -> list:
    """The root authorities this computer trusts (Windows' list), as asn1crypto
    certificates. Elsewhere, none."""
    from asn1crypto import x509

    from app.core import windows_store

    if not windows_store.is_available():
        return []
    roots = []
    try:
        found = windows_store.store_certificates(windows_store.ROOT_STORE)
    except windows_store.StoreError:
        return []
    for der in found:
        try:
            roots.append(x509.Certificate.load(der))
        except Exception:  # noqa: S112 - one unreadable root must not hide the rest
            continue
    return roots


def known_authorities() -> list:
    """The intermediate authorities this computer knows (Windows' list): many
    signatures made with other programs do not carry them inside."""
    from asn1crypto import x509

    from app.core import windows_store

    if not windows_store.is_available():
        return []
    try:
        found = windows_store.store_certificates(windows_store.INTERMEDIATE_STORE)
    except windows_store.StoreError:
        return []
    authorities = []
    for der in found:
        try:
            authorities.append(x509.Certificate.load(der))
        except Exception:  # noqa: S112 - one unreadable certificate must not hide the rest
            continue
    return authorities


def _name(name) -> str:
    fields = name.native
    for key in ("common_name", "organization_name"):
        value = fields.get(key)
        if value:
            return value if isinstance(value, str) else ", ".join(value)
    return name.human_friendly


def _after(status) -> str:
    from pyhanko.sign.diff_analysis import ModificationLevel
    from pyhanko.sign.validation.status import SignatureCoverageLevel

    if status.coverage == SignatureCoverageLevel.ENTIRE_FILE:
        return UNCHANGED
    if status.coverage != SignatureCoverageLevel.ENTIRE_REVISION:
        return CHANGED
    level = status.modification_level
    if level in (None, ModificationLevel.NONE, ModificationLevel.LTA_UPDATES):
        return MORE_SIGNATURES
    if level == ModificationLevel.FORM_FILLING:
        return FORM_FILLED
    if level == ModificationLevel.ANNOTATIONS:
        return ANNOTATED
    return CHANGED


def _pages_of_fields(path: Path) -> dict[str, int]:
    """On which page each signature can be seen (fields with a box)."""
    import pymupdf

    found: dict[str, int] = {}
    try:
        with pymupdf.open(path) as doc:
            for number, page in enumerate(doc):
                for widget in page.widgets() or ():
                    if widget.field_type_string == "Signature" and not widget.rect.is_empty:
                        found.setdefault(widget.field_name, number)
    except Exception:
        return {}
    return found


def check_signatures(
    path: str | Path, roots: list | None = None, intermediates: list | None = None
) -> list[SignatureReport]:
    """Every signature of the document, in the order they were made.

    ``roots``: the authorities to trust (by default, the ones of Windows);
    ``intermediates``: others that may complete a chain (the same).
    A document without signatures gives an empty list; one that cannot be
    read raises ``OSError`` or ``ValueError``.
    """
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import KeyUsageConstraints, validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    path = Path(path)
    if roots is None:
        roots = trusted_roots()
    if intermediates is None:
        intermediates = known_authorities()
    # Either mark makes a certificate good for signing, as Adobe takes it
    # (the library asks for «non-repudiation» alone by default).
    usage = KeyUsageConstraints(
        key_usage={"digital_signature", "non_repudiation"}, match_all_key_usages=False
    )
    pages = _pages_of_fields(path)
    reports = []
    with path.open("rb") as handle:
        try:
            reader = PdfFileReader(handle, strict=False)
            signatures = list(reader.embedded_signatures)
        except Exception as exc:
            raise ValueError(f"The signatures cannot be read: {exc}") from exc
        for signature in signatures:
            field = signature.field_name or ""
            try:
                certificate = signature.signer_cert
                signer, issuer = _name(certificate.subject), _name(certificate.issuer)
            except Exception:
                signer = issuer = ""
            try:
                context = ValidationContext(
                    trust_roots=roots,
                    other_certs=intermediates,
                    allow_fetching=False,
                    revocation_mode="soft-fail",
                )
                status = validate_pdf_signature(signature, context, key_usage_settings=usage)
            except Exception as exc:
                reports.append(
                    SignatureReport(
                        field, signer, issuer, None, False, False, False, CHANGED,
                        pages.get(field), problem=str(exc) or type(exc).__name__,
                    )
                )  # fmt: skip
                continue
            stamp = status.timestamp_validity
            when = stamp.timestamp if stamp is not None else status.signer_reported_dt
            reports.append(
                SignatureReport(
                    field=field,
                    signer=signer,
                    issuer=issuer,
                    signed_at=when,
                    timestamped=stamp is not None,
                    intact=bool(status.intact and status.valid),
                    trusted=bool(status.trusted),
                    after=_after(status),
                    page=pages.get(field),
                )
            )
    return reports
