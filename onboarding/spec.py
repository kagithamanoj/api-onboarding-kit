"""Consumer spec: load and validate the YAML declaration of what a consumer needs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

SPEC_VERSION = "onboarding/v1"
KNOWN_ENVS = {"dev", "staging", "prod"}
KNOWN_AUTH = {"oauth2", "apikey", "mtls"}
DNS_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


class SpecError(ValueError):
    """Raised when a consumer spec is invalid."""


@dataclass
class ConsumerSpec:
    name: str
    contact: str
    environments: list[str]
    expected_rps: int
    burst_rps: int
    auth_method: str
    policies: list[str] = field(default_factory=list)
    cert_domains: list[str] = field(default_factory=list)
    cert_auto_renew: bool = True
    raw: dict = field(default_factory=dict, repr=False)


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

    envs = consumer.get("environments") or []
    unknown = set(envs) - KNOWN_ENVS
    if not envs:
        raise SpecError(f"{source}: consumer.environments must not be empty")
    if unknown:
        raise SpecError(f"{source}: unknown environments: {sorted(unknown)}")

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
    for d in domains:
        if not DNS_RE.match(d.replace(".", "-").replace("*", "w")) and "." not in d:
            raise SpecError(f"{source}: certificate domain {d!r} looks invalid")

    return ConsumerSpec(
        name=name,
        contact=consumer.get("contact", ""),
        environments=list(envs),
        expected_rps=int(expected),
        burst_rps=int(burst),
        auth_method=method,
        policies=list(data.get("policies") or []),
        cert_domains=list(domains),
        cert_auto_renew=bool(certs.get("autoRenew", True)),
        raw=data,
    )
