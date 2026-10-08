"""Renderer: turn a consumer spec + policy library into gateway configuration.

Everything renders from versioned Jinja2 templates. Two consumers with
identical requirements get byte-identical output: drift is structurally
impossible, not merely discouraged.
"""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .policies import library_version, resolve
from .spec import ConsumerSpec

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(os.path.abspath(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(spec: ConsumerSpec, library: dict, gateway: str) -> dict[str, str]:
    """Render all files for one gateway. Returns {relative_path: content}."""
    env = _env()
    policies = resolve(spec.policies, library)
    context = {
        "spec": spec,
        "policies": policies,
        "policy_library_version": library_version(library),
    }
    # Each gateway maps to a list of (template, output_name) pairs.
    layouts: dict[str, list[tuple[str, str]]] = {
        "apim": [("apim/policy.xml.j2", f"{spec.name}.policy.xml")],
        "apigee": [("apigee/proxy.xml.j2", f"{spec.name}.proxy.xml")],
        "gcp": [("gcp/openapi.yaml.j2", f"{spec.name}.openapi.yaml")],
        "aws": [
            ("aws/openapi.yaml.j2", f"{spec.name}.openapi.yaml"),
            ("aws/usage-plan.json.j2", f"{spec.name}.usage-plan.json"),
        ],
    }
    if gateway not in layouts:
        raise ValueError(
            f"unknown gateway {gateway!r}; want one of {sorted(layouts)}"
        )
    out: dict[str, str] = {}
    for template_file, out_name in layouts[gateway]:
        template = env.get_template(template_file)
        out[out_name] = template.render(context)
    return out
