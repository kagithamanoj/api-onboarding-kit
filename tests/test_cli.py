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
    deployed = tmp_path / "deployed"
    deployed.mkdir()
    r = runner.invoke(main, ["render", EXAMPLE, "--gateway", "aws",
                             "--library", LIB, "--out-dir", str(deployed)])
    assert r.exit_code == 0, r.output
    result = runner.invoke(main, ["diff", EXAMPLE, "--gateway", "aws",
                                  "--library", LIB, "--deployed", str(deployed)])
    assert result.exit_code == 0, result.output
    assert "no drift" in result.output


def test_diff_catches_drift(tmp_path):
    deployed = tmp_path / "deployed"
    deployed.mkdir()
    r = runner.invoke(main, ["render", EXAMPLE, "--gateway", "apim",
                             "--library", LIB, "--out-dir", str(deployed)])
    assert r.exit_code == 0, r.output
    # tamper with the deployed file
    (deployed / "payments-team.policy.xml").write_text("<policies>tampered</policies>")
    result = runner.invoke(main, ["diff", EXAMPLE, "--gateway", "apim",
                                  "--library", LIB, "--deployed", str(deployed)])
    assert result.exit_code == 1
    assert "tampered" in result.output


def test_ci_init(tmp_path):
    out = str(tmp_path / ".github" / "workflows" / "onboarding-ci.yaml")
    result = runner.invoke(main, ["ci-init", "--out", out])
    assert result.exit_code == 0, result.output
    assert os.path.exists(out)
