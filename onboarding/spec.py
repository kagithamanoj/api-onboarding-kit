"""Consumer spec: load and validate the YAML declaration of what a consumer needs.

Environments support two forms. The simple list:

    environments: [dev, staging, prod]

Or per-environment overlays for values that differ between stages:

    environments:
      dev:     { backend: https://dev.internal }
      staging: { backend: https://staging.internal }
      prod:    { backend: https://prod.internal, expectedRps: 2000 }

Overlay keys: backend, expectedRps, burstRps, policies (replaces the list).
Use for_env() to get the effective spec for one environment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import yaml

SPEC_VERSION = "onboarding/v1"
KNOWN_ENVS = {"dev", "staging", "prod"}
KNOWN_AUTH = {"oauth2", "apikey", "mtls"}
DNS_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
OVERLAY_KEYS = {"backend", "expectedRps", "burstRps", "policies"}


class SpecError(ValueError):
    """Raised when a consumer spec is invalid."""


@dataclass
class ConsumerSpec:
    name: str
    contact: str
    environments: dict[str, dict]
    expected_rps: int
    burst_rps: int
    auth_method: str
    policies: list[str] = field(default_factory=list)
    cert_domains: list[str] = field(default_factory=list)
    cert_auto_renew: bool = True
    raw: dict = field(default_factory=dict, repr=False)


def _normalize_envs(envs, source: str) -> dict[str, dict]:
    if isinstance(envs, list):
        unknown = set(envs) - KNOWN_ENVS
        if unknown:
            raise SpecError(f"{source}: unknown environments: {sorted(unknown)}")
        if not envs:
            raise SpecError(f"{source}: consumer.environments must not be empty")
        return {e: {} for e in envs}
    if isinstance(envs, dict):
        unknown = set(envs) - KNOWN_ENVS
        if unknown:
            raise SpecError(f"{source}: unknown environments: {sorted(unknown)}")
        if not envs:
            raise SpecError(f"{source}: consumer.environments must not be empty")
        normalized = {}
        for name, overlay in envs.items():
            overlay = overlay or {}
            bad_keys = set(overlay) - OVERLAY_KEYS
            if bad_keys:
                raise SpecError(
                    f"{source}: environment {name!r} has unknown overlay keys: "
                    f"{sorted(bad_keys)} (want {sorted(OVERLAY_KEYS)})"
                )
            normalized[name] = dict(overlay)
        return normalized
    raise SpecError(f"{source}: consumer.environments must be a list or a mapping")


def load_spec(path: str) -> ConsumerSpec:
    with open(path) as f:
        data = yaml.safe_load(f)
    return parse_spec(data, source=path)


def parse_spec(data: dict, source: str = "<dict>") -> ConsumerSpec:
    if not isinstance(data, dict):
        raise SpecError(f"{source}: top level must be a mapping")
    if data.get("apiVersion") != SPEC_VERSION:
        raise SpecError(
            f"{source}: apiVersion must be {SPEC_VERSION!r}, "
            f"got {data.get('apiVersion')!r}"
        )
    consumer = data.get("consumer") or {}
    traffic = data.get("traffic") or {}
    auth = data.get("auth") or {}
    certs = data.get("certificates") or {}

    name = consumer.get("name", "")
    if not DNS_RE.match(name):
        raise SpecError(f"{source}: consumer.name {name!r} is not DNS-compatible")

    envs = _normalize_envs(consumer.get("environments"), source)

    expected = traffic.get("expectedRps", 0)
    burst = traffic.get("burstRps", 0)
    if expected <= 0:
        raise SpecError(f"{source}: traffic.expectedRps must be positive")
    if burst < expected:
        raise SpecError(f"{source}: traffic.burstRps must be >= expectedRps")

    method = auth.get("method", "")
    if method not in KNOWN_AUTH:
        raise SpecError(f"{source}: auth.method must be one of {sorted(KNOWN_AUTH)}")

    domains = certs.get("domains") or []

    return ConsumerSpec(
        name=name,
        contact=consumer.get("contact", ""),
        environments=envs,
        expected_rps=int(expected),
        burst_rps=int(burst),
        auth_method=method,
        policies=list(data.get("policies") or []),
        cert_domains=list(domains),
        cert_auto_renew=bool(certs.get("autoRenew", True)),
        raw=data,
    )


def for_env(spec: ConsumerSpec, env: str) -> ConsumerSpec:
    """Return the effective spec for one environment, overlays applied."""
    if env not in spec.environments:
        raise SpecError(
            f"unknown environment {env!r}; want one of {sorted(spec.environments)}"
        )
    overlay = spec.environments[env]
    expected = int(overlay.get("expectedRps", spec.expected_rps))
    burst = int(overlay.get("burstRps", spec.burst_rps))
    if burst < expected:
        raise SpecError(
            f"environment {env!r}: burstRps ({burst}) must be >= expectedRps ({expected})"
        )
    return replace(
        spec,
        environments={env: overlay},
        expected_rps=expected,
        burst_rps=burst,
        policies=list(overlay.get("policies", spec.policies)),
    )


def backend_for(spec: ConsumerSpec, env: str | None) -> str:
    """Backend address for an environment, overlay or default."""
    default = f"https://backend.internal/{spec.name}"
    if env is None:
        return default
    return spec.environments.get(env, {}).get("backend", default)
