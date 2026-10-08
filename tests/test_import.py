"""Tests for OpenAPI import."""
import os

import pytest

from onboarding.importer import import_openapi
from onboarding.spec import parse_spec

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "openapi-sample.yaml")


def test_import_detects_oauth2():
    spec = import_openapi(SAMPLE)
    assert spec["apiVersion"] == "onboarding/v1"
    assert spec["consumer"]["name"] == "inventory-service"
    assert spec["auth"]["method"] == "oauth2"
    assert spec["x-imported"]["pathCount"] == 2
    # the imported dict must itself be a valid spec (minus x-imported metadata)
    parse_spec({k: v for k, v in spec.items() if not k.startswith("x-")})


def test_import_name_override():
    spec = import_openapi(SAMPLE, name="Custom Name!")
    assert spec["consumer"]["name"] == "custom-name"


def test_import_rejects_non_openapi(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("just: a yaml file\n")
    with pytest.raises(ValueError):
        import_openapi(str(bad))
