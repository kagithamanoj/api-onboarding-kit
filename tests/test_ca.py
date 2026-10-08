"""Tests for the private certificate authority."""
from cryptography import x509

from onboarding.certs import CertificateAuthority, cert_expiry_from_pem, days_until_expiry


def test_ca_create_and_issue(tmp_path):
    store = str(tmp_path / "ca")
    ca = CertificateAuthority.create("Test Internal CA", store)
    cert_pem, key_pem = ca.issue("api.example.com")
    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert key_pem.startswith(b"-----BEGIN RSA PRIVATE KEY-----")

    cert = x509.load_pem_x509_certificate(cert_pem)
    # issued by the CA, not self-signed
    assert cert.issuer == ca.ca_cert.subject
    assert cert.subject != cert.issuer
    assert 820 <= days_until_expiry(cert_expiry_from_pem(cert_pem)) <= 825


def test_ca_reload(tmp_path):
    store = str(tmp_path / "ca")
    CertificateAuthority.create("Test CA", store)
    ca2 = CertificateAuthority(store)  # loads from disk
    cert_pem, _ = ca2.issue("other.example.com")
    assert b"BEGIN CERTIFICATE" in cert_pem


def test_revoke_and_crl(tmp_path):
    store = str(tmp_path / "ca")
    ca = CertificateAuthority.create("Test CA", store)
    cert_pem, _ = ca.issue("revoked.example.com")
    serial = x509.load_pem_x509_certificate(cert_pem).serial_number
    ca.revoke(serial)
    assert serial in ca.revoked_serials()
    crl_pem = ca.crl_pem()
    assert crl_pem.startswith(b"-----BEGIN X509 CRL-----")
    crl = x509.load_pem_x509_crl(crl_pem)
    assert crl.get_revoked_certificate_by_serial_number(serial) is not None
