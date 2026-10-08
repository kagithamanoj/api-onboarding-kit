"""Validator: the CI gate. Schema, lint rules, and dry-run checks.

The same checks run locally and in CI, so a spec that passes on a laptop
passes in the pipeline. No human in the path where drift used to enter.
"""
from __future__ import annotations

from .policies import PolicyError, load_library, resolve
from .spec import ConsumerSpec, SpecError, parse_spec


def _lint(spec: ConsumerSpec, library: dict) -> list[str]:
    findings: list[str] = []
    available = set((library.get("policies") or {}).keys())

    for ref in spec.policies:
        if ref not in available:
            findings.append(f"policy {ref!r} is not in the library")

    try:
        expanded = [d["ref"] for d in resolve(spec.policies, library)]
    except PolicyError:
        expanded = [p for p in spec.policies if p in available]

    if not any(p.startswith("rate-limit") for p in expanded):
        findings.append("no rate-limit policy selected; every consumer needs one")

    if spec.auth_method == "apikey" and "prod" in spec.environments:
        findings.append(
            "apikey auth for prod is discouraged; prefer oauth2 or mtls"
        )

    if spec.cert_domains and not spec.cert_auto_renew:
        findings.append(
            "certificates without auto-renew will expire into an outage; "
            "enable autoRenew or document the manual process"
        )

    if spec.expected_rps > 10000:
        findings.append(
            f"expectedRps={spec.expected_rps} is high; confirm capacity review"
        )

    compliance = [p for p in spec.policies if p.startswith("compliance:")]
    if compliance:
        if spec.auth_method == "apikey":
            findings.append(
                f"{', '.join(compliance)} selected but auth is apikey; "
                "compliance packs require oauth2 or mtls"
            )
        if "prod" in spec.environments and not any(
            p.startswith("ip-allowlist") for p in expanded
        ):
            findings.append(
                f"{', '.join(compliance)} with prod should include an "
                "ip-allowlist policy"
            )

    return findings


def validate(data: dict, library_path: str, source: str = "<dict>") -> list[str]:
    """Validate a raw spec dict. Returns lint findings; raises SpecError on schema errors."""
    spec = parse_spec(data, source=source)
    library = load_library(library_path)
    return _lint(spec, library)


def validate_file(spec_path: str, library_path: str) -> list[str]:
    import yaml

    with open(spec_path) as f:
        data = yaml.safe_load(f)
    try:
        return validate(data, library_path, source=spec_path)
    except SpecError as exc:
        return [f"SCHEMA ERROR: {exc}"]
