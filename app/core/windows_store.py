"""Bridge to the certificate store of Windows.

Certificates installed in Windows (for example the FNMT one, installed with
the browser or with the FNMT configurator) live in the "Personal" store of the
user, and their private key cannot be taken out: Windows only agrees to sign
with it. pyHanko cannot use that store by itself, so this module asks Windows,
through its own functions (crypt32 and ncrypt), to list the certificates and
to sign a digest. If the key is protected, Windows itself shows the password
or PIN window; this program never sees it.

Everything here works only on Windows. On other systems ``is_available()``
is False and the other functions raise ``StoreError``.
"""

import ctypes
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from asn1crypto import algos, x509

PERSONAL_STORE = "MY"
INTERMEDIATE_STORE = "CA"
ROOT_STORE = "ROOT"

_ENCODING = 0x00010001  # X509_ASN_ENCODING | PKCS_7_ASN_ENCODING
_CERT_KEY_PROV_INFO_PROP_ID = 2
_CERT_FIND_SHA1_HASH = 0x00010000
_CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG = 0x00040000
_BCRYPT_PAD_PKCS1 = 0x00000002
_NCRYPT_WINDOW_HANDLE_PROPERTY = "HWND Handle"
# Answers of Windows that mean "the person pressed Cancel".
_CANCELLED = {0x8010006E, 0x80090036, 0x000004C7, 0x800704C7}
_HASH_NAMES = {"sha1": "SHA1", "sha256": "SHA256", "sha384": "SHA384", "sha512": "SHA512"}


class StoreError(Exception):
    """Windows could not list the certificates or sign."""


class SigningCancelled(StoreError):
    """The person closed the password or PIN window of Windows."""


@dataclass(frozen=True)
class StoreCertificate:
    """A certificate of the Windows store that has a private key."""

    thumbprint: str  # SHA-1 of the certificate, how Windows identifies it
    name: str
    issuer: str
    valid_from: datetime
    valid_until: datetime
    for_signing: bool  # False for certificates meant only for other uses
    der: bytes
    personal: bool = True  # False for the ones Windows makes for the computer itself

    @property
    def usable(self) -> bool:
        """Good for signing a document as a person, today."""
        return self.for_signing and self.personal and self.is_valid_now()

    def is_valid_now(self) -> bool:
        return self.valid_from <= datetime.now(UTC) <= self.valid_until


def describe(der: bytes) -> StoreCertificate:
    """Read the facts of a certificate that the person needs to choose it."""
    certificate = x509.Certificate.load(der)
    usage = certificate.key_usage_value
    for_signing = usage is None or bool({"digital_signature", "non_repudiation"} & usage.native)
    return StoreCertificate(
        thumbprint=hashlib.sha1(der, usedforsecurity=False).hexdigest(),
        name=_display_name(certificate.subject),
        issuer=_display_name(certificate.issuer),
        valid_from=certificate.not_valid_before,
        valid_until=certificate.not_valid_after,
        for_signing=for_signing,
        der=der,
        personal=not _belongs_to_the_computer(certificate),
    )


_GUID = re.compile(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.IGNORECASE)
_COMPUTER_ISSUERS = ("ms-organization", "microsoft intune", "microsoft azure")


def _belongs_to_the_computer(certificate: x509.Certificate) -> bool:
    """Windows keeps its own certificates among the personal ones.

    Work and Microsoft accounts add certificates that identify the computer or
    the account to a server. They can sign, but the signature names nobody:
    their name is a long code. Found in the first real test (12/11/2026).
    """
    name = _display_name(certificate.subject)
    issuer = _display_name(certificate.issuer).lower()
    return bool(_GUID.fullmatch(name.strip())) or issuer.startswith(_COMPUTER_ISSUERS)


def _display_name(name: x509.Name) -> str:
    fields = name.native
    for key in ("common_name", "organization_name", "organizational_unit_name"):
        value = fields.get(key)
        if value:
            return value if isinstance(value, str) else ", ".join(value)
    return name.human_friendly


def is_available() -> bool:
    return sys.platform == "win32"


# ---- Windows functions ---------------------------------------------------------


class _CertContext(ctypes.Structure):
    _fields_ = [
        ("dwCertEncodingType", ctypes.c_uint32),
        ("pbCertEncoded", ctypes.c_void_p),
        ("cbCertEncoded", ctypes.c_uint32),
        ("pCertInfo", ctypes.c_void_p),
        ("hCertStore", ctypes.c_void_p),
    ]


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]


class _Pkcs1Padding(ctypes.Structure):
    _fields_ = [("pszAlgId", ctypes.c_wchar_p)]


_libraries = None


def _windows():
    """Load crypt32 and ncrypt and declare the functions used, once."""
    global _libraries
    if not is_available():
        raise StoreError("The Windows certificate store only exists on Windows")
    if _libraries is not None:
        return _libraries
    void_p, u32, context_p = ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_CertContext)
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    ncrypt = ctypes.WinDLL("ncrypt", use_last_error=True)

    def declare(library, name, result, *arguments):
        function = getattr(library, name)
        function.restype, function.argtypes = result, arguments

    declare(crypt32, "CertOpenSystemStoreW", void_p, void_p, ctypes.c_wchar_p)
    declare(crypt32, "CertCloseStore", ctypes.c_int, void_p, u32)
    declare(crypt32, "CertEnumCertificatesInStore", context_p, void_p, context_p)
    declare(crypt32, "CertFreeCertificateContext", ctypes.c_int, context_p)
    declare(
        crypt32,
        "CertGetCertificateContextProperty",
        ctypes.c_int,
        context_p,
        u32,
        void_p,
        ctypes.POINTER(u32),
    )
    declare(
        crypt32,
        "CertFindCertificateInStore",
        context_p,
        void_p,
        u32,
        u32,
        u32,
        void_p,
        context_p,
    )
    declare(
        crypt32,
        "CryptAcquireCertificatePrivateKey",
        ctypes.c_int,
        context_p,
        u32,
        void_p,
        ctypes.POINTER(void_p),
        ctypes.POINTER(u32),
        ctypes.POINTER(ctypes.c_int),
    )
    declare(
        ncrypt,
        "NCryptSignHash",
        ctypes.c_int32,
        void_p,
        void_p,
        ctypes.c_char_p,
        u32,
        ctypes.c_char_p,
        u32,
        ctypes.POINTER(u32),
        u32,
    )
    declare(ncrypt, "NCryptSetProperty", ctypes.c_int32, void_p, ctypes.c_wchar_p, void_p, u32, u32)
    declare(ncrypt, "NCryptFreeObject", ctypes.c_int32, void_p)
    _libraries = (crypt32, ncrypt)
    return _libraries


def _open_store(crypt32, name: str):
    store = crypt32.CertOpenSystemStoreW(None, name)
    if not store:
        raise StoreError(f"Windows could not open the certificate store {name!r}")
    return store


def _has_private_key(crypt32, context) -> bool:
    size = ctypes.c_uint32(0)
    return bool(
        crypt32.CertGetCertificateContextProperty(
            context, _CERT_KEY_PROV_INFO_PROP_ID, None, ctypes.byref(size)
        )
    )


def store_certificates(store_name: str, only_with_private_key: bool = False) -> list[bytes]:
    """The certificates of one store of the current user, as DER bytes."""
    crypt32, _ncrypt = _windows()
    store = _open_store(crypt32, store_name)
    found = []
    try:
        context = crypt32.CertEnumCertificatesInStore(store, None)
        while context:  # asking for the next one frees the previous one
            if not only_with_private_key or _has_private_key(crypt32, context):
                found.append(
                    ctypes.string_at(context.contents.pbCertEncoded, context.contents.cbCertEncoded)
                )
            context = crypt32.CertEnumCertificatesInStore(store, context)
    finally:
        crypt32.CertCloseStore(store, 0)
    return found


def list_certificates() -> list[StoreCertificate]:
    """Personal certificates with a private key, the ones to sign with first."""
    certificates = []
    for der in store_certificates(PERSONAL_STORE, only_with_private_key=True):
        try:
            certificates.append(describe(der))
        except Exception:  # noqa: S112 - one unreadable certificate must not hide the rest
            continue
    certificates.sort(key=lambda c: (not c.usable, not c.personal, c.name.lower()))
    return certificates


def chain_candidates() -> list[bytes]:
    """Certificates of authorities known to Windows, to complete the chain."""
    found = []
    for store in (INTERMEDIATE_STORE, ROOT_STORE):
        try:
            found.extend(store_certificates(store))
        except StoreError:
            continue
    return found


def sign_digest(
    thumbprint: str,
    digest: bytes,
    digest_algorithm: str,
    key_algorithm: str,
    window_handle: int | None = None,
) -> bytes:
    """Ask Windows to sign ``digest`` with the private key of a certificate.

    ``key_algorithm`` is "rsa" or "ec". For RSA the result is a PKCS#1 v1.5
    signature; for EC, the two numbers as DER, which is what PDF needs.
    """
    crypt32, ncrypt = _windows()
    if key_algorithm not in ("rsa", "ec"):
        raise StoreError(f"Keys of type {key_algorithm!r} are not supported")
    store = _open_store(crypt32, PERSONAL_STORE)
    context = key = None
    try:
        raw = bytes.fromhex(thumbprint)
        buffer = ctypes.create_string_buffer(raw, len(raw))
        blob = _Blob(len(raw), ctypes.cast(buffer, ctypes.c_void_p))
        context = crypt32.CertFindCertificateInStore(
            store, _ENCODING, 0, _CERT_FIND_SHA1_HASH, ctypes.byref(blob), None
        )
        if not context:
            raise StoreError("The certificate is no longer in the Windows store")

        key = ctypes.c_void_p()
        key_spec = ctypes.c_uint32()
        must_free = ctypes.c_int()
        acquired = crypt32.CryptAcquireCertificatePrivateKey(
            context,
            _CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG,
            None,
            ctypes.byref(key),
            ctypes.byref(key_spec),
            ctypes.byref(must_free),
        )
        if not acquired:
            _fail("Windows could not get the private key", ctypes.get_last_error())
        if not must_free.value:
            key_to_free, key = None, key
        else:
            key_to_free = key

        try:
            if window_handle:
                handle = ctypes.c_void_p(window_handle)
                ncrypt.NCryptSetProperty(
                    key,
                    _NCRYPT_WINDOW_HANDLE_PROPERTY,
                    ctypes.byref(handle),
                    ctypes.sizeof(handle),
                    0,
                )
            padding = flags = None
            if key_algorithm == "rsa":
                if digest_algorithm not in _HASH_NAMES:
                    raise StoreError(f"Digest {digest_algorithm!r} is not supported")
                padding = ctypes.byref(_Pkcs1Padding(_HASH_NAMES[digest_algorithm]))
                flags = _BCRYPT_PAD_PKCS1
            size = ctypes.c_uint32(0)
            status = ncrypt.NCryptSignHash(
                key, padding, digest, len(digest), None, 0, ctypes.byref(size), flags or 0
            )
            if status != 0:
                _fail("Windows refused to sign", status)
            signature = ctypes.create_string_buffer(size.value)
            status = ncrypt.NCryptSignHash(
                key,
                padding,
                digest,
                len(digest),
                signature,
                size.value,
                ctypes.byref(size),
                flags or 0,
            )
            if status != 0:
                _fail("Windows refused to sign", status)
            result = signature.raw[: size.value]
        finally:
            if key_to_free is not None:
                ncrypt.NCryptFreeObject(key_to_free)
    finally:
        if context:
            crypt32.CertFreeCertificateContext(context)
        crypt32.CertCloseStore(store, 0)
    if key_algorithm == "ec":
        return algos.DSASignature.from_p1363(result).dump()
    return result


def _fail(what: str, code: int) -> None:
    code &= 0xFFFFFFFF
    if code in _CANCELLED:
        raise SigningCancelled(f"{what}: cancelled (0x{code:08X})")
    raise StoreError(f"{what} (0x{code:08X})")
