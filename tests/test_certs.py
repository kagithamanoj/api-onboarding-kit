"""Tests for certificate lifecycle helpers."""
from datetime import datetime, timedelta, timezone

from onboarding.certs import (
    cert_expiry_from_pem,
    days_until_expiry,
    generate_dev_cert,
    renewal_due,
)


def test_dev_cert_roundtrip():
    cert_pem, key_pem = generate_dev_cert("api.example.com", valid_days=90)
    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert key_pem.startswith(b"-----BEGIN RSA PRIVATE KEY-----")
    expiry = cert_expiry_from_pem(cert_pem)
    assert 89 <= days_until_expiry(expiry) <= 90
    assert not renewal_due(expiry)


def test_renewal_due_soon():
    soon = datetime.now(timezone.utc) + timedelta(days=10)
    assert renewal_due(soon)
    later = datetime.now(timezone.utc) + timedelta(days=300)
    assert not renewal_due(later)
