"""CLI: init, validate, render, plan, import, cost, diff, ci-init."""
from __future__ import annotations

import os
import shutil
import sys

import click
import yaml

from .catalog import render_catalog
from .certs import CertificateAuthority
from .cost import compare, estimate
from .drift import diff_deployed
from .importer import import_openapi, write_spec
from .ledger import history as ledger_history
from .ledger import record as ledger_record
from .policies import library_version, load_library
from .renderer import render
from .simulate import simulate
from .spec import SpecError, for_env, load_spec
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
@click.option("--env", default=None, help="Render for one environment (applies overlays)")
@click.option("--library", default=DEFAULT_LIBRARY)
@click.option("--out-dir", default="out")
def render_cmd(spec_path: str, gateway: str, fmt: str, env: str | None,
               library: str, out_dir: str) -> None:
    """Render gateway configuration files from a spec."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    try:
        files = render(spec, lib, gateway, fmt, env)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    for rel, content in files.items():
        path = os.path.join(out_dir, rel)
        with open(path, "w") as f:
            f.write(content)
        click.echo(f"wrote {path}")
    ledger_record("render", spec.name, {
        "gateway": gateway, "format": fmt, "env": env or "default",
        "files": sorted(files),
        "policy_library": library_version(lib),
    })


@main.command()
@click.argument("spec_path")
@click.option("--library", default=DEFAULT_LIBRARY)
@click.option("--env", default=None, help="Show the effective spec for one environment")
def plan(spec_path: str, library: str, env: str | None) -> None:
    """Dry-run: show what onboarding would provision, without writing anything."""
    try:
        spec = load_spec(spec_path)
        effective = for_env(spec, env) if env else spec
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    click.echo(f"consumer:  {spec.name} ({spec.contact})")
    if env:
        from .spec import backend_for
        click.echo(f"env:       {env} (backend {backend_for(spec, env)})")
    click.echo(f"envs:      {', '.join(spec.environments)}")
    click.echo(f"traffic:   {effective.expected_rps} rps expected, {effective.burst_rps} burst")
    click.echo(f"auth:      {effective.auth_method}")
    click.echo(f"policies:  {', '.join(effective.policies) or '(none)'}  [library v{lib.get('version')}]")
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
@click.option("--env", default=None, help="Diff for one environment (applies overlays)")
@click.option("--deployed", required=True, help="Directory holding deployed files")
@click.option("--library", default=DEFAULT_LIBRARY)
def diff(spec_path: str, gateway: str, fmt: str, env: str | None,
         deployed: str, library: str) -> None:
    """Diff rendered output against deployed files to catch drift."""
    try:
        diffs = diff_deployed(spec_path, gateway, deployed, library, fmt, env)
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


@main.command()
@click.argument("spec_path")
@click.option("--to", "to_env", required=True, help="Environment to promote to")
@click.option("--from", "from_env", required=True, help="Environment promoting from")
@click.option("--library", default=DEFAULT_LIBRARY)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def promote(spec_path: str, to_env: str, from_env: str, library: str, yes: bool) -> None:
    """Promote a consumer from one environment to the next.

    Validates the spec, renders every gateway for the target environment
    as a pre-flight check, and records the promotion in the audit ledger.
    """
    try:
        spec = load_spec(spec_path)
        for_env(spec, from_env)
        target = for_env(spec, to_env)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    findings = validate_file(spec_path, library)
    if findings:
        click.echo("cannot promote: spec has findings")
        for finding in findings:
            click.echo(f"  - {finding}")
        sys.exit(1)
    lib = load_library(library)
    for gateway in ("apim", "apigee", "gcp", "aws"):
        render(target, lib, gateway, "native", to_env)  # pre-flight, raises on error
    click.echo(f"promoting {spec.name}: {from_env} -> {to_env}")
    click.echo(f"  traffic: {target.expected_rps} rps expected, {target.burst_rps} burst")
    click.echo(f"  policies: {', '.join(target.policies)}")
    if not yes and not click.confirm("proceed?"):
        click.echo("aborted")
        sys.exit(1)
    ledger_record("promote", spec.name, {
        "from": from_env, "to": to_env,
        "policy_library": library_version(lib),
    })
    click.echo(f"promoted {spec.name} to {to_env}; recorded in the audit ledger")


@main.command(name="ca-init")
@click.option("--cn", required=True, help="CA common name, e.g. 'Example Internal CA'")
@click.option("--out", "out_dir", default="certs", help="CA store directory")
def ca_init(cn: str, out_dir: str) -> None:
    """Create a new private certificate authority."""
    CertificateAuthority.create(cn, out_dir)
    click.echo(f"CA '{cn}' created in {out_dir}/")
    click.echo("Protect ca-key.pem like production credentials.")


@main.command(name="ca-issue")
@click.option("--ca", "ca_dir", default="certs", help="CA store directory")
@click.option("--domain", required=True, help="Domain to issue for")
@click.option("--valid-days", default=825, help="Certificate lifetime in days")
@click.option("--out", "out_dir", default="out", help="Output directory")
def ca_issue(ca_dir: str, domain: str, valid_days: int, out_dir: str) -> None:
    """Issue a server certificate from the private CA."""
    try:
        ca = CertificateAuthority(ca_dir)
    except OSError as exc:
        click.echo(f"CA ERROR: {exc}", err=True)
        sys.exit(1)
    cert_pem, key_pem = ca.issue(domain, valid_days)
    os.makedirs(out_dir, exist_ok=True)
    cert_path = os.path.join(out_dir, f"{domain}.crt")
    key_path = os.path.join(out_dir, f"{domain}.key")
    with open(cert_path, "wb") as f:
        f.write(cert_pem)
    with open(key_path, "wb") as f:
        os.chmod(f.fileno(), 0o600)
        f.write(key_pem)
    click.echo(f"wrote {cert_path} and {key_path}")
    ledger_record("ca-issue", domain, {"ca_dir": ca_dir, "valid_days": valid_days})


@main.command(name="ca-crl")
@click.option("--ca", "ca_dir", default="certs", help="CA store directory")
def ca_crl(ca_dir: str) -> None:
    """Print the certificate revocation list for the private CA."""
    try:
        ca = CertificateAuthority(ca_dir)
    except OSError as exc:
        click.echo(f"CA ERROR: {exc}", err=True)
        sys.exit(1)
    click.echo(ca.crl_pem().decode(), nl=False)


@main.command()
@click.option("--spec", "spec_name", default=None, help="Filter to one consumer")
@click.option("--limit", default=20, help="Max entries to show")
def history(spec_name: str | None, limit: int) -> None:
    """Show the audit ledger of onboarding actions."""
    entries = ledger_history(spec_name, limit=limit)
    if not entries:
        click.echo("ledger is empty")
        return
    for entry in entries:
        details = " ".join(f"{k}={v}" for k, v in entry["details"].items())
        click.echo(f"{entry['ts'][:19]}  {entry['action']:<8} {entry['consumer']}  {details}")


@main.command()
@click.argument("spec_path")
@click.option("--rps", required=True, type=int, help="Offered load in requests/second")
@click.option("--duration", default=60, help="Simulation length in seconds")
@click.option("--library", default=DEFAULT_LIBRARY)
def simulate_cmd(spec_path: str, rps: int, duration: int, library: str) -> None:
    """Simulate offered load against the rate-limit policy (token bucket model)."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    result = simulate(spec, lib, rps, duration)
    click.echo(f"policy:      {result['policy']}")
    click.echo(f"sustained:   {result['sustained_rps']} rps, burst capacity {result['burst_capacity']}")
    click.echo(f"offered:     {result['offered_rps']} rps for {result['duration_s']}s")
    click.echo(f"allowed:     {result['allowed_requests']:,}")
    click.echo(f"rejected:    {result['rejected_429']:,} ({result['rejection_pct']}%)")
    if result["rejection_pct"] > 0:
        click.echo("verdict:     this load will see 429s; raise the tier or shed load")


@main.command()
@click.argument("spec_path")
@click.option("--library", default=DEFAULT_LIBRARY)
@click.option("--out", "out_path", default="catalog-info.yaml")
def catalog(spec_path: str, library: str, out_path: str) -> None:
    """Generate a Backstage catalog-info.yaml for the consumer."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"SCHEMA ERROR: {exc}", err=True)
        sys.exit(1)
    lib = load_library(library)
    content = render_catalog(spec, library_version(lib))
    with open(out_path, "w") as f:
        f.write(content)
    click.echo(f"wrote {out_path}")


if __name__ == "__main__":
    main()
