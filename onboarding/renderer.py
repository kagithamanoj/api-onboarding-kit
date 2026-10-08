"""Renderer: turn a consumer spec + policy library into gateway configuration.

Everything renders from versioned Jinja2 templates. Two consumers with
identical requirements get byte-identical output: drift is structurally
impossible, not merely discouraged.

Two output formats per gateway:
  native     the gateway's own configuration (policy XML, OpenAPI, ...)
  terraform  Terraform HCL that provisions the gateway resources and
             references the native files, so both stay in one pipeline.
"""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .policies import library_version, resolve
from .spec import ConsumerSpec, backend_for, for_env

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

# (gateway, format) -> [(template, output_name), ...]. Populated per spec
# by _layouts_for() below; kept here as documentation of supported targets.
LAYOUTS_DOCUMENTED = [
    ("apim", "native"), ("apigee", "native"), ("gcp", "native"),
    ("aws", "native"), ("apim", "terraform"), ("aws", "terraform"),
    ("gcp", "terraform"),
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(os.path.abspath(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _layouts_for(spec: ConsumerSpec) -> dict[tuple[str, str], list[tuple[str, str]]]:
    return {
        ("apim", "native"): [("apim/policy.xml.j2", f"{spec.name}.policy.xml")],
        ("apigee", "native"): [("apigee/proxy.xml.j2", f"{spec.name}.proxy.xml")],
        ("gcp", "native"): [("gcp/openapi.yaml.j2", f"{spec.name}.openapi.yaml")],
        ("aws", "native"): [
            ("aws/openapi.yaml.j2", f"{spec.name}.openapi.yaml"),
            ("aws/usage-plan.json.j2", f"{spec.name}.usage-plan.json"),
        ],
        ("apim", "terraform"): [("terraform/apim.tf.j2", f"{spec.name}.apim.tf")],
        ("aws", "terraform"): [("terraform/aws.tf.j2", f"{spec.name}.aws.tf")],
        ("gcp", "terraform"): [("terraform/gcp.tf.j2", f"{spec.name}.gcp.tf")],
    }


def supported_targets() -> list[tuple[str, str]]:
    return [
        ("apim", "native"), ("apigee", "native"), ("gcp", "native"),
        ("aws", "native"), ("apim", "terraform"), ("aws", "terraform"),
        ("gcp", "terraform"),
    ]


def render(
    spec: ConsumerSpec,
    library: dict,
    gateway: str,
    format: str = "native",
    env: str | None = None,
) -> dict[str, str]:
    """Render all files for one gateway/format, optionally for one environment.

    When env is given, the environment overlay is applied first, so the
    output reflects that stage's backend, traffic, and policies.
    """
    layouts = _layouts_for(spec)
    key = (gateway, format)
    if key not in layouts:
        want = ", ".join(f"{g}/{f}" for g, f in sorted(layouts))
        raise ValueError(f"unknown target {gateway}/{format}; want one of: {want}")
    effective = for_env(spec, env) if env else spec
    env_config = dict(effective.environments.get(env, {})) if env else {}
    jinja_env = _env()
    policies = resolve(effective.policies, library)
    context = {
        "spec": effective,
        "policies": policies,
        "policy_library_version": library_version(library),
        "env": env or "default",
        "env_config": env_config,
        "backend": backend_for(spec, env),
    }
    out: dict[str, str] = {}
    for template_file, out_name in layouts[key]:
        template = jinja_env.get_template(template_file)
        out[out_name] = template.render(context)
    return out
