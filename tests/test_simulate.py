"""Tests for the traffic simulator."""
import os

from onboarding.policies import load_library
from onboarding.simulate import simulate
from onboarding.spec import parse_spec

LIB = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")
SPEC = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "demo", "contact": "a@b.c", "environments": ["dev"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard"],  # 1000 calls / 60s
}


def test_load_under_limit_no_rejections():
    lib = load_library(LIB)
    result = simulate(parse_spec(dict(SPEC)), lib, offered_rps=10, duration_s=60)
    assert result["rejected_429"] == 0
    assert result["rejection_pct"] == 0.0


def test_load_over_limit_rejects():
    lib = load_library(LIB)
    # 100 rps offered vs ~16.7 sustained: most gets rejected after burst drains
    result = simulate(parse_spec(dict(SPEC)), lib, offered_rps=100, duration_s=120)
    assert result["rejected_429"] > 0
    assert result["rejection_pct"] > 50


def test_burst_absorbs_short_spike():
    lib = load_library(LIB)
    # 100 rps for 5s = 500 requests, within the 1000-call bucket
    result = simulate(parse_spec(dict(SPEC)), lib, offered_rps=100, duration_s=5)
    assert result["rejected_429"] == 0


def test_result_shape():
    lib = load_library(LIB)
    result = simulate(parse_spec(dict(SPEC)), lib, offered_rps=50)
    assert result["sustained_rps"] == round(1000 / 60, 1)
    assert result["burst_capacity"] == 1000
    assert result["policy"] == "rate-limit:standard"
