"""Tests for the bridge to the Windows certificate store (task 0.8).

The tests marked ``windows`` install throw-away certificates in the personal
store of the test machine, sign with them through Windows and remove them.
They run on GitHub's Windows machines; elsewhere they are skipped.
"""

import ctypes
import sys
from datetime import UTC, datetime

import pytest
from asn1crypto import x509 as asn1_x509
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from app.core import windows_store
from app.core.signing import WindowsStoreSigner, sign_pdf
from app.core.windows_store import StoreError, describe
from tests import certificates

windows = pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows store")

# ---- reading certificates (any system) ------------------------------------------


def test_describe_gives_what_a_person_needs_to_choose():
    key = certificates.new_key()
    authority = certificates.make_certificate("AC de Prueba", key, authority=True)
    person_key = certificates.new_key()
    person = certificates.make_certificate(
        "PRUEBA PRUEBA ANA - 00000000T", person_key, authority, key
    )
    info = describe(certificates.der(person))
    assert info.name == "PRUEBA PRUEBA ANA - 00000000T"
    assert info.issuer == "AC de Prueba"
    assert info.for_signing
    assert info.is_valid_now()
    assert info.valid_from < datetime.now(UTC) < info.valid_until
    assert len(info.thumbprint) == 40
    assert info.der == certificates.der(person)


def test_describe_tells_expired_and_not_for_signing():
    key = certificates.new_key()
    expired = certificates.make_certificate("Caducado", key, days_valid=-1, started_days_ago=30)
    assert not describe(certificates.der(expired)).is_valid_now()
    cipher_only = certificates.make_certificate("Solo cifrado", key, for_signing=False)
    assert not describe(certificates.der(cipher_only)).for_signing


@pytest.mark.skipif(sys.platform == "win32", reason="checks the answer outside Windows")
def test_outside_windows_it_says_so_instead_of_failing_badly():
    assert not windows_store.is_available()
    with pytest.raises(StoreError):
        windows_store.list_certificates()
    with pytest.raises(StoreError):
        windows_store.sign_digest("00" * 20, b"\0" * 32, "sha256", "rsa")
    assert windows_store.chain_candidates() == []


# ---- the real Windows store ------------------------------------------------------

_CRYPT_USER_KEYSET = 0x00001000
_PKCS12_ALWAYS_CNG_KSP = 0x00000200
_CERT_STORE_ADD_REPLACE_EXISTING = 3


def install_in_personal_store(p12: bytes, modern_key_storage: bool) -> None:
    """What happens when a person installs a .p12: certificate and key go to Windows."""
    crypt32, _ncrypt = windows_store._windows()
    void_p, context_p = ctypes.c_void_p, ctypes.POINTER(windows_store._CertContext)
    crypt32.PFXImportCertStore.restype = void_p
    crypt32.PFXImportCertStore.argtypes = [void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    crypt32.CertAddCertificateContextToStore.restype = ctypes.c_int
    crypt32.CertAddCertificateContextToStore.argtypes = [void_p, context_p, ctypes.c_uint32, void_p]

    buffer = ctypes.create_string_buffer(p12, len(p12))
    blob = windows_store._Blob(len(p12), ctypes.cast(buffer, void_p))
    flags = _CRYPT_USER_KEYSET | (_PKCS12_ALWAYS_CNG_KSP if modern_key_storage else 0)
    imported = crypt32.PFXImportCertStore(ctypes.byref(blob), certificates.PASSWORD, flags)
    assert imported, f"Windows could not read the .p12 (error {ctypes.get_last_error()})"
    personal = crypt32.CertOpenSystemStoreW(None, windows_store.PERSONAL_STORE)
    try:
        context = crypt32.CertEnumCertificatesInStore(imported, None)
        assert context, "the .p12 had no certificate"
        while context:
            assert crypt32.CertAddCertificateContextToStore(
                personal, context, _CERT_STORE_ADD_REPLACE_EXISTING, None
            )
            context = crypt32.CertEnumCertificatesInStore(imported, context)
    finally:
        crypt32.CertCloseStore(personal, 0)
        crypt32.CertCloseStore(imported, 0)


def remove_from_personal_store(thumbprint: str) -> None:
    crypt32, _ncrypt = windows_store._windows()
    crypt32.CertDeleteCertificateFromStore.restype = ctypes.c_int
    crypt32.CertDeleteCertificateFromStore.argtypes = [ctypes.POINTER(windows_store._CertContext)]
    personal = crypt32.CertOpenSystemStoreW(None, windows_store.PERSONAL_STORE)
    try:
        raw = bytes.fromhex(thumbprint)
        buffer = ctypes.create_string_buffer(raw, len(raw))
        blob = windows_store._Blob(len(raw), ctypes.cast(buffer, ctypes.c_void_p))
        context = crypt32.CertFindCertificateInStore(
            personal,
            windows_store._ENCODING,
            0,
            windows_store._CERT_FIND_SHA1_HASH,
            ctypes.byref(blob),
            None,
        )
        if context:
            crypt32.CertDeleteCertificateFromStore(context)  # also frees the context
    finally:
        crypt32.CertCloseStore(personal, 0)


# How the key ends up stored in Windows. "old" is the classic storage that
# certificates installed years ago (many FNMT ones) still use.
KINDS = {
    "rsa-modern": ("rsa", True),
    "rsa-old": ("rsa", False),
    "ec-modern": ("ec", True),
}


@pytest.fixture(params=sorted(KINDS))
def installed(request):
    """A throw-away certificate installed in the personal store of Windows."""
    key_kind, modern = KINDS[request.param]
    key = certificates.new_key(key_kind)
    name = f"Lector-PDF prueba {request.param}"
    certificate = certificates.make_certificate(name, key)
    der = certificates.der(certificate)
    info = describe(der)
    install_in_personal_store(certificates.make_p12(name, key, certificate), modern)
    yield info
    remove_from_personal_store(info.thumbprint)


@windows
def test_installed_certificate_is_listed(installed):
    listed = {c.thumbprint: c for c in windows_store.list_certificates()}
    assert installed.thumbprint in listed
    found = listed[installed.thumbprint]
    assert found.name == installed.name
    assert found.for_signing and found.is_valid_now()


@windows
def test_signing_with_a_certificate_of_the_windows_store(installed, sample, tmp_path):
    signer = WindowsStoreSigner(installed)
    target = sign_pdf(sample("formulario.pdf"), tmp_path / "firmado.pdf", signer)
    trusted = asn1_x509.Certificate.load(installed.der)
    with target.open("rb") as handle:
        (signature,) = PdfFileReader(handle).embedded_signatures
        status = validate_pdf_signature(signature, ValidationContext(trust_roots=[trusted]))
        assert status.intact and status.valid and status.trusted
        assert signature.sig_object["/SubFilter"] == "/ETSI.CAdES.detached"
        assert signature.signer_cert.dump() == installed.der


@windows
def test_a_removed_certificate_gives_a_clear_error(installed):
    remove_from_personal_store(installed.thumbprint)
    with pytest.raises(StoreError):
        windows_store.sign_digest(installed.thumbprint, b"\0" * 32, "sha256", "rsa")


@windows
def test_windows_knows_authorities_to_complete_the_chain():
    roots = windows_store.store_certificates(windows_store.ROOT_STORE)
    assert len(roots) > 5
    assert all(describe(der).name for der in roots[:5])
    assert len(windows_store.chain_candidates()) >= len(roots)


@windows
def test_certificates_without_private_key_are_not_offered():
    with_key = set(windows_store.store_certificates(windows_store.ROOT_STORE, True))
    everything = set(windows_store.store_certificates(windows_store.ROOT_STORE))
    assert len(with_key) < len(everything)
