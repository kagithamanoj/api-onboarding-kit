"""OpenAPI import: generate a starter consumer spec from an existing definition.

Brownfield teams already have APIs. This reads their OpenAPI document and
produces a spec that captures what can be inferred (identity, auth model),
with safe defaults for what cannot (traffic). The result is a starting
point for review, not a finished spec.
"""
from __future__ import annotations

import re

import yaml


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "imported-api"


def _detect_auth(doc: dict) -> str:
    schemes = (doc.get("components") or {}).get("securitySchemes") or {}
    method = "oauth2"  # safest default
    for scheme in schemes.values():
        stype = (scheme.get("type") or "").lower()
        if stype == "oauth2":
            return "oauth2"
        if stype == "apikey":
            method = "apikey"
        if stype == "mutualtls" or "x5c" in str(scheme):
            method = "mtls"
    return method


def import_openapi(path: str, name: str | None = None) -> dict:
    """Read an OpenAPI file and return a consumer spec dict."""
    with open(path) as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict) or "openapi" not in doc and "swagger" not in doc:
        raise ValueError(f"{path}: does not look like an OpenAPI document")
    info = doc.get("info") or {}
    consumer_name = _slug(name or info.get("title", "imported-api"))
    paths = doc.get("paths") or {}
    return {
        "apiVersion": "onboarding/v1",
        "consumer": {
            "name": consumer_name,
            "contact": "team@example.com",
            "environments": ["dev", "staging"],
        },
        "traffic": {"expectedRps": 100, "burstRps": 300},
        "auth": {"method": _detect_auth(doc)},
        "policies": ["rate-limit:standard"],
        "certificates": {"domains": [], "autoRenew": True},
        "x-imported": {
            "from": path,
            "title": info.get("title", ""),
            "version": str(info.get("version", "")),
            "pathCount": len(paths),
            "note": "Review traffic numbers and contact before onboarding.",
        },
    }


def write_spec(spec: dict, out_path: str) -> None:
    with open(out_path, "w") as f:
        yaml.safe_dump(spec, f, sort_keys=False)
