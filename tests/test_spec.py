"""Tests for spec parsing."""
import pytest

from onboarding.spec import SpecError, parse_spec

BASE = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "my-team", "contact": "a@b.c", "environments": ["dev"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
}


def test_valid_spec():
    spec = parse_spec(dict(BASE))
    assert spec.name == "my-team"
    assert spec.environments == ["dev"]


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
