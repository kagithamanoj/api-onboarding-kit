"""Tests for the new CLI commands."""
import os

from click.testing import CliRunner

from onboarding.cli import main

LIB = os.path.join(os.path.dirname(__file__), "..", "policies", "library.yaml")
EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "consumer.yaml")
OPENAPI = os.path.join(os.path.dirname(__file__), "..", "examples", "openapi-sample.yaml")

runner = CliRunner()


def test_import_cli(tmp_path):
    out = str(tmp_path / "imported.yaml")
    result = runner.invoke(main, ["import", OPENAPI, "--out", out])
    assert result.exit_code == 0, result.output
    assert os.path.exists(out)


def test_cost_all_cli():
    result = runner.invoke(main, ["cost", EXAMPLE, "--all"])
    assert result.exit_code == 0, result.output
    assert "AWS API Gateway" in result.output


def test_diff_no_drift(tmp_path):
    with runner.isolated_filesystem():
        deployed = "deployed"
        os.makedirs(deployed)
        r = runner.invoke(main, ["render", EXAMPLE, "--gateway", "aws",
                                 "--library", LIB, "--out-dir", deployed])
        assert r.exit_code == 0, r.output
        result = runner.invoke(main, ["diff", EXAMPLE, "--gateway", "aws",
                                      "--library", LIB, "--deployed", deployed])
        assert result.exit_code == 0, result.output
        assert "no drift" in result.output


def test_diff_catches_drift(tmp_path):
    with runner.isolated_filesystem():
        deployed = "deployed"
        os.makedirs(deployed)
        r = runner.invoke(main, ["render", EXAMPLE, "--gateway", "apim",
                                 "--library", LIB, "--out-dir", deployed])
        assert r.exit_code == 0, r.output
        # tamper with the deployed file
        with open(os.path.join(deployed, "payments-team.policy.xml"), "w") as f:
            f.write("<policies>tampered</policies>")
        result = runner.invoke(main, ["diff", EXAMPLE, "--gateway", "apim",
                                      "--library", LIB, "--deployed", deployed])
        assert result.exit_code == 1
        assert "tampered" in result.output


def test_render_with_env_overlay():
    with runner.isolated_filesystem():
        r = runner.invoke(main, ["render", EXAMPLE, "--gateway", "gcp",
                                 "--env", "prod", "--library", LIB,
                                 "--out-dir", "out"])
        assert r.exit_code == 0, r.output
        with open("out/payments-team.openapi.yaml") as f:
            content = f.read()
        assert "https://payments.prod.internal" in content


def test_promote_cli():
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["promote", EXAMPLE, "--from", "staging",
                                      "--to", "prod", "--library", LIB, "--yes"])
        assert result.exit_code == 0, result.output
        assert "promoted payments-team to prod" in result.output


def test_promote_blocked_by_findings(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("""apiVersion: onboarding/v1
consumer:
  name: badsvc
  contact: a@b.c
  environments: [dev]
traffic: {expectedRps: 100, burstRps: 200}
auth: {method: apikey}
policies: [cors:default]
""")
    result = runner.invoke(main, ["promote", str(bad), "--from", "dev",
                                  "--to", "dev", "--library", LIB, "--yes"])
    assert result.exit_code == 1
    assert "cannot promote" in result.output


def test_simulate_cli():
    result = runner.invoke(main, ["simulate", EXAMPLE, "--rps", "500",
                                  "--duration", "10", "--library", LIB])
    assert result.exit_code == 0, result.output
    assert "rejected:" in result.output


def test_catalog_cli(tmp_path):
    out = str(tmp_path / "catalog-info.yaml")
    result = runner.invoke(main, ["catalog", EXAMPLE, "--library", LIB, "--out", out])
    assert result.exit_code == 0, result.output
    assert os.path.exists(out)


def test_ci_init(tmp_path):
    out = str(tmp_path / ".github" / "workflows" / "onboarding-ci.yaml")
    result = runner.invoke(main, ["ci-init", "--out", out])
    assert result.exit_code == 0, result.output
    assert os.path.exists(out)
