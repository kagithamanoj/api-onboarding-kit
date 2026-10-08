"""Backstage catalog generation: register the API in the developer portal."""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader

from .spec import ConsumerSpec

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def render_catalog(spec: ConsumerSpec, library_version: str = "") -> str:
    env = Environment(
        loader=FileSystemLoader(os.path.abspath(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("backstage/catalog.yaml.j2")
    owner = spec.contact.split("@")[0] if "@" in spec.contact else "platform-team"
    lifecycle = "production" if "prod" in spec.environments else "experimental"
    return template.render(spec=spec, owner=owner, lifecycle=lifecycle,
                           library_version=library_version)
