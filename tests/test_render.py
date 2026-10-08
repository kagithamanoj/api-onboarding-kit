"""Tests for rendering: identical inputs give byte-identical outputs."""
import os

import pytest

from onboarding.policies import load_library
from onboarding.renderer import render
from onboarding.spec import parse_spec

LIB = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")
SPEC = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "demo", "contact": "a@b.c", "environments": ["dev", "prod"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard", "cors:default"],
}


def test_render_apim_deterministic():
    lib = load_library(LIB)
    first = render(parse_spec(dict(SPEC)), lib, "apim")
    second = render(parse_spec(dict(SPEC)), lib, "apim")
    assert first == second
    content = list(first.values())[0]
    assert "rate-limit-by-key" in content
    assert "Do not hand-edit" in content


def test_render_apigee():
    lib = load_library(LIB)
    out = render(parse_spec(dict(SPEC)), lib, "apigee")
    content = list(out.values())[0]
    assert "<APIProxy" in content
    assert "demo" in content


def test_unknown_gateway():
    lib = load_library(LIB)
    with pytest.raises(ValueError):
        render(parse_spec(dict(SPEC)), lib, "kong")


def test_render_gcp():
    lib = load_library(LIB)
    out = render(parse_spec(dict(SPEC)), lib, "gcp")
    content = list(out.values())[0]
    assert "x-google-backend" in content
    assert "x-google-quota" in content
    assert "demo" in content


def test_render_aws_two_files():
    import json

    lib = load_library(LIB)
    out = render(parse_spec(dict(SPEC)), lib, "aws")
    assert len(out) == 2
    openapi = out["demo.openapi.yaml"]
    plan = json.loads(out["demo.usage-plan.json"])
    assert "x-amazon-apigateway-integration" in openapi
    assert plan["name"] == "demo"
    assert plan["throttle"]["burstLimit"] == 200


def test_unknown_policy_raises():
    lib = load_library(LIB)
    bad = dict(SPEC, policies=["nope:missing"])
    with pytest.raises(Exception):
        render(parse_spec(bad), lib, "apim")
