"""Cost estimation: what does this consumer cost to run per gateway?

Estimates from public list pricing. They are directional, for comparing
options and right-sizing tiers, not for budgeting. Verify against current
pricing before spending money.
"""
from __future__ import annotations

from .spec import ConsumerSpec

SECONDS_PER_MONTH = 86400 * 30

# base_usd: fixed monthly cost. per_million_usd: cost per million requests.
PRICING: dict[str, dict] = {
    "apim": {
        "label": "Azure API Management",
        "tiers": {
            "consumption": {"base_usd": 0.0, "per_million_usd": 4.00,
                            "note": "Serverless; best for spiky or low traffic"},
            "developer": {"base_usd": 48.0, "per_million_usd": 0.0,
                          "note": "Non-production use"},
            "standard": {"base_usd": 700.0, "per_million_usd": 0.0,
                         "note": "Production SLA, VNet support"},
        },
    },
    "aws": {
        "label": "AWS API Gateway",
        "tiers": {
            "rest": {"base_usd": 0.0, "per_million_usd": 3.50,
                     "note": "REST API, first 333M req/mo tier"},
            "http": {"base_usd": 0.0, "per_million_usd": 1.00,
                     "note": "HTTP API; cheaper, fewer features"},
        },
    },
    "gcp": {
        "label": "Google Cloud API Gateway",
        "tiers": {
            "standard": {"base_usd": 0.0, "per_million_usd": 3.00,
                         "note": "Pay per million calls"},
        },
    },
    "apigee": {
        "label": "Apigee X",
        "tiers": {
            "payg": {"base_usd": 0.0, "per_million_usd": 40.00,
                     "note": "Pay-as-you-go; evaluate for high governance needs"},
        },
    },
}


def monthly_requests(spec: ConsumerSpec) -> float:
    return spec.expected_rps * SECONDS_PER_MONTH


def estimate(spec: ConsumerSpec, gateway: str, tier: str | None = None) -> dict:
    """Estimate monthly cost for one gateway/tier. Returns a breakdown dict."""
    if gateway not in PRICING:
        raise ValueError(f"unknown gateway {gateway!r}")
    tiers = PRICING[gateway]["tiers"]
    tier = tier or next(iter(tiers))
    if tier not in tiers:
        raise ValueError(f"unknown tier {tier!r} for {gateway}; want {sorted(tiers)}")
    price = tiers[tier]
    millions = monthly_requests(spec) / 1_000_000
    variable = millions * price["per_million_usd"]
    return {
        "gateway": gateway,
        "label": PRICING[gateway]["label"],
        "tier": tier,
        "monthly_requests": monthly_requests(spec),
        "base_usd": price["base_usd"],
        "variable_usd": round(variable, 2),
        "total_usd": round(price["base_usd"] + variable, 2),
        "note": price["note"],
    }


def compare(spec: ConsumerSpec) -> list[dict]:
    """Cheapest tier per gateway, sorted by total monthly cost."""
    results = []
    for gateway, info in PRICING.items():
        best = min(
            (estimate(spec, gateway, tier) for tier in info["tiers"]),
            key=lambda e: e["total_usd"],
        )
        results.append(best)
    return sorted(results, key=lambda e: e["total_usd"])
