"""Certificate lifecycle: issuance for dev, expiry tracking, renewal checks.

Certificates are a lifecycle, not an event. Every consumer gets expiry
tracking from day one; renewals are hooks you wire to your CA or ACME
client. Nothing here touches production credentials.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

RENEWAL_WINDOW_DAYS = 30


def days_until_expiry(not_valid_after: datetime) -> int:
    now = datetime.now(timezone.utc)
    if not_valid_after.tzinfo is None:
        not_valid_after = not_valid_after.replace(tzinfo=timezone.utc)
    return (not_valid_after - now).days


def renewal_due(not_valid_after: datetime, window_days: int = RENEWAL_WINDOW_DAYS) -> bool:
    return days_until_expiry(not_valid_after) <= window_days


def generate_dev_cert(domain: str, valid_days: int = 90) -> tuple[bytes, bytes]:
    """Self-signed cert for dev/staging only. Never use for production."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def cert_expiry_from_pem(cert_pem: bytes) -> datetime:
    cert = x509.load_pem_x509_certificate(cert_pem)
    return cert.not_valid_after_utc
