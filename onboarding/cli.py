"""CLI: init, validate, render, plan."""
from __future__ import annotations

import os
import sys

import click
import yaml

from .policies import load_library
from .renderer import render
from .spec import SpecError, load_spec
from .validator import validate_file

DEFAULT_LIBRARY = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")


@click.group()
def main() -> None:
    """Self-service API consumer onboarding."""


@main.command()
@click.argument("name")
def init(name: str) -> None:
    """Scaffold a new consumer spec."""
    content = f"""apiVersion: onboarding/v1
consumer:
  name: {name}
  contact: team@example.com
  environments: [dev, staging]
traffic:
  expectedRps: 100
  burstRps: 300
auth:
  method: oauth2
policies:
  - rate-limit:standard
  - cors:default
certificates:
  domains: []
  autoRenew: true
"""
    path = f"{name}.yaml"
    with open(path, "w") as f:
        f.write(content)
    click.echo(f"wrote {path}; edit it, then run: onboard validate {path}")


@main.command()
@click.argument("spec_path")
@click.option("--library", default=DEFAULT_LIBRARY, help="Policy library path")
def validate(spec_path: str, library: str) -> None:
    """Validate a consumer spec (schema + lint). Exits non-zero on findings."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    findings = validate_file(spec_path, library)
    if findings:
        click.echo(f"spec {spec.name}: {len(findings)} finding(s)")
        for finding in findings:
            click.echo(f"  - {finding}")
        sys.exit(1)
    click.echo(f"spec {spec.name}: OK")


@main.command(name="render")
@click.argument("spec_path")
@click.option("--gateway", type=click.Choice(["apim", "apigee", "gcp", "aws"]), default="apim")
@click.option("--library", default=DEFAULT_LIBRARY)
@click.option("--out-dir", default="out")
def render_cmd(spec_path: str, gateway: str, library: str, out_dir: str) -> None:
    """Render gateway configuration files from a spec."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    files = render(spec, lib, gateway)
    os.makedirs(out_dir, exist_ok=True)
    for rel, content in files.items():
        path = os.path.join(out_dir, rel)
        with open(path, "w") as f:
            f.write(content)
        click.echo(f"wrote {path}")


@main.command()
@click.argument("spec_path")
@click.option("--library", default=DEFAULT_LIBRARY)
def plan(spec_path: str, library: str) -> None:
    """Dry-run: show what onboarding would provision, without writing anything."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    click.echo(f"consumer:  {spec.name} ({spec.contact})")
    click.echo(f"envs:      {', '.join(spec.environments)}")
    click.echo(f"traffic:   {spec.expected_rps} rps expected, {spec.burst_rps} burst")
    click.echo(f"auth:      {spec.auth_method}")
    click.echo(f"policies:  {', '.join(spec.policies) or '(none)'}  [library v{lib.get('version')}]")
    if spec.cert_domains:
        auto = "auto-renew ON" if spec.cert_auto_renew else "auto-renew OFF"
        click.echo(f"certs:     {', '.join(spec.cert_domains)} ({auto})")
    else:
        click.echo("certs:     (none requested)")
    findings = validate_file(spec_path, library)
    if findings:
        click.echo("lint findings:")
        for finding in findings:
            click.echo(f"  - {finding}")
    else:
        click.echo("lint:      clean")


if __name__ == "__main__":
    main()
