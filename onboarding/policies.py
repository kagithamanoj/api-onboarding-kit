"""Policy library: versioned, reusable gateway policies.

Policies live in one versioned file with owners and change history.
Onboarding selects policies; it never authors them inline.
"""
from __future__ import annotations

import yaml


class PolicyError(ValueError):
    pass


def load_library(path: str) -> dict:
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "policies" not in data:
        raise PolicyError(f"{path}: expected a mapping with a 'policies' key")
    return data


def resolve(requested: list[str], library: dict) -> list[dict]:
    """Resolve policy references like 'rate-limit:standard' to definitions.

    Bundles (type: bundle) expand recursively into their member policies.
    Duplicates collapse: selecting a bundle and one of its members directly
    still renders each policy once.
    """
    available = library.get("policies", {})
    resolved: list[dict] = []
    seen: set[str] = set()

    def _add(ref: str) -> None:
        if ref in seen:
            return
        if ref not in available:
            raise PolicyError(
                f"unknown policy {ref!r}; available: {sorted(available)}"
            )
        seen.add(ref)
        definition = dict(available[ref])
        definition["ref"] = ref
        if definition.get("type") == "bundle":
            for member in definition.get("members", []):
                _add(member)
        else:
            resolved.append(definition)

    for ref in requested:
        _add(ref)
    return resolved


def library_version(library: dict) -> str:
    return str(library.get("version", "unversioned"))
