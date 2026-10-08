"""Tests for spec parsing."""
import pytest

from onboarding.spec import SpecError, backend_for, for_env, parse_spec

BASE = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "my-team", "contact": "a@b.c", "environments": ["dev"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
}


def test_valid_spec():
    spec = parse_spec(dict(BASE))
    assert spec.name == "my-team"
    assert spec.environments == {"dev": {}}


def test_overlay_form():
    data = dict(BASE)
    data["consumer"] = {
        "name": "my-team", "contact": "a@b.c",
        "environments": {
            "dev": {"backend": "https://dev.internal"},
            "prod": {"backend": "https://prod.internal", "expectedRps": 2000,
                     "burstRps": 2500},
        },
    }
    spec = parse_spec(data)
    assert spec.environments["prod"]["backend"] == "https://prod.internal"
    prod = for_env(spec, "prod")
    assert prod.expected_rps == 2000
    assert prod.burst_rps == 2500
    dev = for_env(spec, "dev")
    assert dev.expected_rps == 100  # base value when no overlay
    assert backend_for(spec, "prod") == "https://prod.internal"
    assert backend_for(spec, None) == "https://backend.internal/my-team"


def test_overlay_bad_key():
    data = dict(BASE)
    data["consumer"] = {**BASE["consumer"],
                        "environments": {"dev": {"bogus": 1}}}
    with pytest.raises(SpecError):
        parse_spec(data)


def test_for_env_unknown():
    spec = parse_spec(dict(BASE))
    with pytest.raises(SpecError):
        for_env(spec, "prod")


def test_bad_version():
    with pytest.raises(SpecError):
        parse_spec({**BASE, "apiVersion": "v9"})


def test_bad_name():
    bad = dict(BASE, consumer={**BASE["consumer"], "name": "Not_A_DNS_Name!"})
    with pytest.raises(SpecError):
        parse_spec(bad)


def test_burst_below_expected():
    bad = dict(BASE, traffic={"expectedRps": 500, "burstRps": 100})
    with pytest.raises(SpecError):
        parse_spec(bad)


def test_unknown_env():
    bad = dict(BASE, consumer={**BASE["consumer"], "environments": ["moon"]})
    with pytest.raises(SpecError):
        parse_spec(bad)


def test_unknown_auth():
    bad = dict(BASE, auth={"method": "telepathy"})
    with pytest.raises(SpecError):
        parse_spec(bad)
