"""Traffic simulator: will this rate limit survive the load?

Models the resolved rate-limit policy as a token bucket and replays an
offered load profile against it. Answers the question every team asks
before a launch or a sale: at X rps, how much gets a 429?

This is a model, not a measurement. It assumes the gateway enforces the
policy exactly as written and ignores network effects.
"""
from __future__ import annotations

from .policies import resolve
from .spec import ConsumerSpec


def simulate(
    spec: ConsumerSpec,
    library: dict,
    offered_rps: int,
    duration_s: int = 60,
) -> dict:
    policies = resolve(spec.policies, library)
    rl = next((p for p in policies if p.get("type") == "rate-limit"), None)
    calls = rl["calls"] if rl else 1000
    period = rl["periodSeconds"] if rl else 60

    capacity = float(calls)
    refill_per_s = calls / period
    tokens = capacity
    allowed = 0
    rejected = 0
    for _ in range(duration_s):
        tokens = min(capacity, tokens + refill_per_s)
        take = min(offered_rps, tokens)
        tokens -= take
        allowed += take
        rejected += offered_rps - take

    total = allowed + rejected
    return {
        "consumer": spec.name,
        "policy": rl["ref"] if rl else "default (1000/60s)",
        "offered_rps": offered_rps,
        "duration_s": duration_s,
        "allowed_requests": int(allowed),
        "rejected_429": int(rejected),
        "rejection_pct": round(100 * rejected / total, 2) if total else 0.0,
        "sustained_rps": round(refill_per_s, 1),
        "burst_capacity": int(capacity),
    }
