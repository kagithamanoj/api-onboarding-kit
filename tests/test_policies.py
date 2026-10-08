"""Tests for policy bundles and compliance lint rules."""
import os

from onboarding.policies import PolicyError, load_library, resolve
from onboarding.validator import validate

LIB = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")

BASE = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "ok", "contact": "a@b.c", "environments": ["dev"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard"],
}


def test_bundle_expands():
    lib = load_library(LIB)
    resolved = resolve(["compliance:pci-dss"], lib)
    refs = [d["ref"] for d in resolved]
    assert "auth:jwt-required" in refs
    assert "rate-limit:standard" in refs
    assert "ip-allowlist:office" in refs
    assert "compliance:pci-dss" not in refs  # bundles expand, they don't render


def test_bundle_dedupes():
    lib = load_library(LIB)
    resolved = resolve(["compliance:pci-dss", "rate-limit:standard"], lib)
    refs = [d["ref"] for d in resolved]
    assert refs.count("rate-limit:standard") == 1


def test_unknown_still_raises():
    lib = load_library(LIB)
    try:
        resolve(["nope:missing"], lib)
    except PolicyError:
        return
    raise AssertionError("expected PolicyError")


def test_compliance_with_apikey_flagged():
    bad = dict(BASE)
    bad["auth"] = {"method": "apikey"}
    bad["policies"] = ["compliance:soc2"]
    findings = validate(bad, LIB)
    assert any("apikey" in f for f in findings)


def test_compliance_prod_without_allowlist_flagged():
    bad = dict(BASE)
    bad["consumer"] = {**BASE["consumer"], "environments": ["prod"]}
    bad["policies"] = ["compliance:soc2"]  # soc2 bundle has no ip-allowlist
    findings = validate(bad, LIB)
    assert any("ip-allowlist" in f for f in findings)


def test_pci_example_validates_clean():
    path = os.path.join(os.path.dirname(__file__), "..", "examples", "pci-consumer.yaml")
    from onboarding.validator import validate_file

    assert validate_file(path, LIB) == []
