"""Tests for the validator: lint findings, not just schema."""
import os

from onboarding.validator import validate, validate_file

LIB = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")
EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "consumer.yaml")

GOOD = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "ok", "contact": "a@b.c", "environments": ["dev"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard"],
}


def test_clean_spec_has_no_findings():
    assert validate(dict(GOOD), LIB) == []


def test_missing_rate_limit_flagged():
    findings = validate({**GOOD, "policies": ["cors:default"]}, LIB)
    assert any("rate-limit" in f for f in findings)


def test_unknown_policy_flagged():
    findings = validate({**GOOD, "policies": ["bogus:one"]}, LIB)
    assert any("bogus:one" in f for f in findings)


def test_apikey_in_prod_flagged():
    bad = dict(GOOD)
    bad["consumer"] = {**GOOD["consumer"], "environments": ["prod"]}
    bad["auth"] = {"method": "apikey"}
    findings = validate(bad, LIB)
    assert any("apikey" in f for f in findings)


def test_example_file_validates():
    findings = validate_file(EXAMPLE, LIB)
    assert findings == [], findings
