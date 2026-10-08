"""Tests for Terraform rendering."""
import os

import pytest

from onboarding.policies import load_library
from onboarding.renderer import render, supported_targets
from onboarding.spec import parse_spec

LIB = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")
SPEC = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "demo-tf", "contact": "a@b.c", "environments": ["dev", "prod"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard"],
}


def test_supported_targets():
    targets = supported_targets()
    assert ("apim", "terraform") in targets
    assert ("aws", "terraform") in targets
    assert ("gcp", "terraform") in targets


def test_apim_terraform():
    lib = load_library(LIB)
    out = render(parse_spec(dict(SPEC)), lib, "apim", "terraform")
    content = list(out.values())[0]
    assert 'resource "azurerm_api_management_api"' in content
    assert 'resource "azurerm_api_management_api_policy"' in content
    assert "demo-tf.policy.xml" in content  # references the native file


def test_aws_terraform():
    lib = load_library(LIB)
    out = render(parse_spec(dict(SPEC)), lib, "aws", "terraform")
    content = list(out.values())[0]
    assert 'resource "aws_api_gateway_rest_api"' in content
    assert 'resource "aws_api_gateway_usage_plan"' in content
    assert "burst_limit = 200" in content


def test_gcp_terraform():
    lib = load_library(LIB)
    out = render(parse_spec(dict(SPEC)), lib, "gcp", "terraform")
    content = list(out.values())[0]
    assert 'resource "google_api_gateway_gateway"' in content


def test_terraform_deterministic():
    lib = load_library(LIB)
    spec = parse_spec(dict(SPEC))
    assert render(spec, lib, "aws", "terraform") == render(spec, lib, "aws", "terraform")


def test_apigee_terraform_unsupported():
    lib = load_library(LIB)
    with pytest.raises(ValueError):
        render(parse_spec(dict(SPEC)), lib, "apigee", "terraform")
