"""Certificate lifecycle: dev certs, expiry tracking, and a private CA.

Two layers:
  1. generate_dev_cert(): self-signed, for dev/staging only. Never production.
  2. CertificateAuthority: a real private CA for internal mTLS. init once,
     issue per service, revoke, publish CRLs. Standard X.509, no magic.

Private keys never leave the machine that runs these commands. The CA key
lives in the store directory; protect it like production credentials.
"""
from __future__ import annotations

import os
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


class CertificateAuthority:
    """A private CA: create once, issue per service, revoke, publish CRLs."""

    def __init__(self, store_dir: str):
        self.store_dir = store_dir
        with open(os.path.join(store_dir, "ca-cert.pem"), "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read())
        with open(os.path.join(store_dir, "ca-key.pem"), "rb") as f:
            self.ca_key = serialization.load_pem_private_key(f.read(), password=None)

    @classmethod
    def create(cls, common_name: str, store_dir: str, valid_days: int = 3650) -> "CertificateAuthority":
        os.makedirs(store_dir, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=valid_days))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False, content_commitment=False,
                    key_encipherment=False, data_encipherment=False,
                    key_agreement=False, key_cert_sign=True, crl_sign=True,
                    encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )
        with open(os.path.join(store_dir, "ca-cert.pem"), "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(os.path.join(store_dir, "ca-key.pem"), "wb") as f:
            os.chmod(f.fileno(), 0o600)
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))
        open(os.path.join(store_dir, "issued.txt"), "a").close()
        open(os.path.join(store_dir, "revoked.txt"), "a").close()
        return cls(store_dir)

    def issue(self, domain: str, valid_days: int = 825) -> tuple[bytes, bytes]:
        """Issue a server certificate for a domain, signed by this CA."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)]))
            .issuer_name(self.ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=valid_days))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(domain)]), critical=False
            )
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(self.ca_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        with open(os.path.join(self.store_dir, "issued.txt"), "a") as f:
            f.write(f"{cert.serial_number} {domain} {now.date().isoformat()}\n")
        return cert_pem, key_pem

    def revoke(self, serial_number: int) -> None:
        with open(os.path.join(self.store_dir, "revoked.txt"), "a") as f:
            f.write(f"{serial_number}\n")

    def revoked_serials(self) -> set[int]:
        serials = set()
        path = os.path.join(self.store_dir, "revoked.txt")
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        serials.add(int(line))
        return serials

    def crl_pem(self) -> bytes:
        now = datetime.now(timezone.utc)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(self.ca_cert.subject)
            .last_update(now)
            .next_update(now + timedelta(days=7))
        )
        for serial in self.revoked_serials():
            builder = builder.add_revoked_certificate(
                x509.RevokedCertificateBuilder()
                .serial_number(serial)
                .revocation_date(now)
                .build()
            )
        crl = builder.sign(private_key=self.ca_key, algorithm=hashes.SHA256())
        return crl.public_bytes(serialization.Encoding.PEM)
