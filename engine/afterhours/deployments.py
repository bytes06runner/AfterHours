"""Readers for `deployments/<profile>.json` and `deployments/<profile>.discovered.json`.

Bot, API and web read addresses only from these files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from afterhours.config import AfterhoursConfig


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def deployment_path(cfg: AfterhoursConfig, profile: str | None = None) -> Path:
    """Path of our own deployment file for a profile (default: active)."""
    name = profile or cfg.active_profile
    return cfg.path(cfg.paths.deployments_dir) / f"{name}.json"


def discovered_path(cfg: AfterhoursConfig, profile: str | None = None) -> Path:
    """Path of the discovered-addresses file for a profile (default: active)."""
    name = profile or cfg.active_profile
    return cfg.path(cfg.paths.deployments_dir) / f"{name}.discovered.json"


def load_deployment(cfg: AfterhoursConfig, profile: str | None = None) -> dict[str, Any]:
    """Our deployed addresses, or an empty dict before the first deploy."""
    return _read(deployment_path(cfg, profile))


def load_discovered(cfg: AfterhoursConfig, profile: str | None = None) -> dict[str, Any]:
    """Discovered protocol addresses with evidence, or an empty dict before M1."""
    return _read(discovered_path(cfg, profile))
