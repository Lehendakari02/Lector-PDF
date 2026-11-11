"""Makes throw-away certificates for the signing tests. Nothing here is real."""

from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

PASSWORD = "prueba"


def new_key(kind: str = "rsa"):
    if kind == "ec":
        return ec.generate_private_key(ec.SECP256R1())
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_certificate(
    name: str,
    key,
    issuer=None,
    issuer_key=None,
    authority: bool = False,
    days_valid: int = 30,
    started_days_ago: int = 1,
    for_signing: bool = True,
):
    """A certificate for ``key``; self-signed unless an issuer is given."""
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.subject if issuer is not None else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=started_days_ago))
        .not_valid_after(now + timedelta(days=days_valid))
        .add_extension(x509.BasicConstraints(ca=authority, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=for_signing and not authority,
                content_commitment=for_signing and not authority,
                key_encipherment=not for_signing and not authority,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=authority,
                crl_sign=authority,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )
    if issuer is not None:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            critical=False,
        )
    return builder.sign(issuer_key if issuer_key is not None else key, hashes.SHA256())


def der(certificate) -> bytes:
    return certificate.public_bytes(serialization.Encoding.DER)


def make_p12(name: str, key, certificate, others=None) -> bytes:
    """A ``.p12`` protected the old way, which every Windows version can read."""
    protection = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(2000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1())  # noqa: S303 - test data, old format on purpose
        .build(PASSWORD.encode())
    )
    return pkcs12.serialize_key_and_certificates(
        name.encode(), key, certificate, others, protection
    )
