"""CLI: init, validate, render, plan, import, cost, diff, ci-init."""
from __future__ import annotations

import os
import shutil
import sys

import click
import yaml

from .cost import compare, estimate
from .drift import diff_deployed
from .importer import import_openapi, write_spec
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
@click.option("--format", "fmt", type=click.Choice(["native", "terraform"]), default="native",
              help="native gateway config or Terraform HCL")
@click.option("--library", default=DEFAULT_LIBRARY)
@click.option("--out-dir", default="out")
def render_cmd(spec_path: str, gateway: str, fmt: str, library: str, out_dir: str) -> None:
    """Render gateway configuration files from a spec."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    try:
        files = render(spec, lib, gateway, fmt)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
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


@main.command(name="import")
@click.argument("openapi_path")
@click.option("--name", default=None, help="Consumer name (defaults to API title)")
@click.option("--out", "out_path", default=None, help="Output spec path")
def import_cmd(openapi_path: str, name: str | None, out_path: str | None) -> None:
    """Generate a starter consumer spec from an OpenAPI document."""
    try:
        spec = import_openapi(openapi_path, name)
    except (ValueError, OSError) as exc:
        click.echo(f"IMPORT ERROR: {exc}", err=True)
        sys.exit(1)
    out_path = out_path or f"{spec['consumer']['name']}.yaml"
    write_spec(spec, out_path)
    click.echo(f"wrote {out_path}")
    click.echo("Review traffic numbers and contact before onboarding: "
               "those are safe defaults, not measurements.")


@main.command()
@click.argument("spec_path")
@click.option("--gateway", default=None, help="Estimate for one gateway")
@click.option("--all", "show_all", is_flag=True, help="Compare cheapest tier per gateway")
def cost(spec_path: str, gateway: str | None, show_all: bool) -> None:
    """Estimate monthly gateway cost for a consumer spec."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    click.echo("Estimates from public list pricing; verify before budgeting.")
    if show_all or gateway is None:
        rows = compare(spec)
        click.echo(f"{'gateway':<28}{'tier':<14}{'req/mo':>12}{'/mo':>10}")
        for row in rows:
            click.echo(f"{row['label']:<28}{row['tier']:<14}"
                       f"{row['monthly_requests']:>12,.0f}"
                       f"${row['total_usd']:>9,.2f}")
    else:
        row = estimate(spec, gateway)
        click.echo(f"{row['label']} ({row['tier']}): "
                   f"${row['total_usd']:,.2f}/mo at "
                   f"{row['monthly_requests']:,.0f} req/mo")
        click.echo(f"note: {row['note']}")


@main.command()
@click.argument("spec_path")
@click.option("--gateway", type=click.Choice(["apim", "apigee", "gcp", "aws"]), default="apim")
@click.option("--format", "fmt", type=click.Choice(["native", "terraform"]), default="native")
@click.option("--deployed", required=True, help="Directory holding deployed files")
@click.option("--library", default=DEFAULT_LIBRARY)
def diff(spec_path: str, gateway: str, fmt: str, deployed: str, library: str) -> None:
    """Diff rendered output against deployed files to catch drift."""
    try:
        diffs = diff_deployed(spec_path, gateway, deployed, library, fmt)
    except (SpecError, ValueError) as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)
    if not diffs:
        click.echo("no drift: deployed matches rendered output")
        return
    for name, text in diffs.items():
        click.echo(text)
        click.echo()
    sys.exit(1)


@main.command(name="ci-init")
@click.option("--out", "out_path",
              default=".github/workflows/onboarding-ci.yaml",
              help="Workflow file path")
def ci_init(out_path: str) -> None:
    """Generate a GitHub Actions workflow that validates specs on PR."""
    src = os.path.join(os.path.dirname(__file__), "..", "templates", "ci",
                       "github-actions.yaml")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    shutil.copy(src, out_path)
    click.echo(f"wrote {out_path}; specs are expected under specs/")


if __name__ == "__main__":
    main()
