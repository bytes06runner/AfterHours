"""M7 acceptance: `make demo` runs the closing-bell scenario end to end without manual steps."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess

import pytest

from afterhours.config import REPO_ROOT, load_config

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_make_demo_derisks_and_anchors_a_reason() -> None:
    if not shutil.which("anvil"):
        pytest.skip("anvil not installed")
    env = {
        **os.environ,
        "DEMO_EXIT": "1",
        "ANVIL_PORT": str(_free_port()),
        "API_PORT": str(_free_port()),
        "WEB_PORT": str(_free_port()),
    }
    out = subprocess.run(
        ["./scripts/demo.sh"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
        check=False,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    cfg = load_config(load_env_file=False)
    profile = cfg.demo.profile
    result = json.loads(
        (cfg.path(cfg.paths.state_dir) / f"{profile}.closing_bell.json").read_text()
    )
    assert result["derisked"], result
    assert result["reasons"], result
    assert all(r["registry_tx"].startswith("0x") for r in result["reasons"])
