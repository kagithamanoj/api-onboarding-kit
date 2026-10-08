"""Audit ledger: every onboarding action, recorded.

Renders, promotions, and certificate issuance append one JSON line each:
who did what to which consumer, when, with which policy library version.
Boring, append-only, and exactly what auditors ask for.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

DEFAULT_LEDGER = ".onboarding/ledger.jsonl"


def record(
    action: str,
    spec_name: str,
    details: dict | None = None,
    ledger_path: str = DEFAULT_LEDGER,
) -> dict:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "consumer": spec_name,
        "details": details or {},
    }
    os.makedirs(os.path.dirname(ledger_path) or ".", exist_ok=True)
    with open(ledger_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def history(
    spec_name: str | None = None,
    ledger_path: str = DEFAULT_LEDGER,
    limit: int = 50,
) -> list[dict]:
    if not os.path.exists(ledger_path):
        return []
    entries = []
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    if spec_name:
        entries = [e for e in entries if e.get("consumer") == spec_name]
    return entries[-limit:]
