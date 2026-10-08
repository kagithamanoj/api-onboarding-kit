"""Tests for the audit ledger and Backstage catalog."""
import os

from onboarding.catalog import render_catalog
from onboarding.ledger import history, record
from onboarding.spec import parse_spec

SPEC = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "demo", "contact": "team@example.com",
                 "environments": ["dev", "prod"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard"],
}


def test_ledger_roundtrip(tmp_path):
    ledger = str(tmp_path / "ledger.jsonl")
    record("render", "demo", {"gateway": "aws"}, ledger_path=ledger)
    record("promote", "demo", {"from": "dev", "to": "prod"}, ledger_path=ledger)
    entries = history(ledger_path=ledger)
    assert len(entries) == 2
    assert entries[0]["action"] == "render"
    assert entries[1]["details"]["to"] == "prod"
    assert history("other", ledger_path=ledger) == []


def test_ledger_empty(tmp_path):
    assert history(ledger_path=str(tmp_path / "missing.jsonl")) == []


def test_catalog_renders():
    spec = parse_spec(dict(SPEC))
    content = render_catalog(spec, "1.0.0")
    assert "kind: API" in content
    assert "name: demo" in content
    assert "lifecycle: production" in content  # prod in envs
    assert "owner: team" in content
