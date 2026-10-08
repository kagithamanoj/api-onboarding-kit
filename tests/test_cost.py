"""Tests for cost estimation."""
import pytest

from onboarding.cost import compare, estimate, monthly_requests
from onboarding.spec import parse_spec

SPEC = {
    "apiVersion": "onboarding/v1",
    "consumer": {"name": "demo", "contact": "a@b.c", "environments": ["dev"]},
    "traffic": {"expectedRps": 100, "burstRps": 200},
    "auth": {"method": "oauth2"},
    "policies": ["rate-limit:standard"],
}


def test_monthly_requests():
    spec = parse_spec(dict(SPEC))
    assert monthly_requests(spec) == 100 * 86400 * 30  # 259.2M


def test_aws_rest_math():
    spec = parse_spec(dict(SPEC))
    row = estimate(spec, "aws", "rest")
    assert row["monthly_requests"] == 259_200_000
    assert row["total_usd"] == round(259.2 * 3.50, 2)


def test_azure_consumption_vs_standard():
    # At low traffic, consumption (pay per call) beats a fixed-price tier;
    # at high traffic the math flips. The estimator should show both honestly.
    low = dict(SPEC, traffic={"expectedRps": 10, "burstRps": 30})
    spec = parse_spec(low)
    consumption = estimate(spec, "apim", "consumption")
    standard = estimate(spec, "apim", "standard")
    assert consumption["total_usd"] < standard["total_usd"]
    assert consumption["total_usd"] == round(25.92 * 4.00, 2)


def test_compare_sorted_and_covers_gateways():
    spec = parse_spec(dict(SPEC))
    rows = compare(spec)
    gateways = {r["gateway"] for r in rows}
    assert gateways == {"apim", "aws", "gcp", "apigee"}
    totals = [r["total_usd"] for r in rows]
    assert totals == sorted(totals)


def test_unknown_gateway():
    spec = parse_spec(dict(SPEC))
    with pytest.raises(ValueError):
        estimate(spec, "kong")
