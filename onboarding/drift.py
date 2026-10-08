"""Drift detection: compare rendered output against what is deployed.

Pass a directory holding the currently deployed files. Anything missing or
different is reported as a unified diff. File-based on purpose: it works in
CI without cloud credentials, and it makes drift reviewable as text.
"""
from __future__ import annotations

import difflib
import os

from .policies import load_library
from .renderer import render
from .spec import load_spec


def diff_deployed(
    spec_path: str,
    gateway: str,
    deployed_dir: str,
    library_path: str,
    format: str = "native",
) -> dict[str, str]:
    """Return {filename: diff_text} for every file that is missing or differs."""
    spec = load_spec(spec_path)
    library = load_library(library_path)
    rendered = render(spec, library, gateway, format)
    diffs: dict[str, str] = {}
    for name, content in rendered.items():
        deployed_path = os.path.join(deployed_dir, name)
        if not os.path.exists(deployed_path):
            diffs[name] = f"NOT DEPLOYED: {name} is rendered but missing in {deployed_dir}"
            continue
        with open(deployed_path) as f:
            deployed = f.read()
        if deployed != content:
            diff = difflib.unified_diff(
                deployed.splitlines(),
                content.splitlines(),
                fromfile=f"deployed/{name}",
                tofile=f"rendered/{name}",
                lineterm="",
            )
            diffs[name] = "\n".join(diff)
    return diffs
