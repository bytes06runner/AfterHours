"""M7 acceptance: `make demo` runs the closing-bell scenario end to end without manual steps."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from afterhours.config import REPO_ROOT, load_config

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_make_demo_derisks_and_anchors_a_reason(tmp_path: Path) -> None:
    if not shutil.which("anvil"):
        pytest.skip("anvil not installed")
    # Own chain port, deployments and state, so a running `make up` stack is never touched.
    port = _free_port()
    deploy_dir = REPO_ROOT / "contracts" / "cache" / f"it-demo-deployments-{port}"
    deploy_dir.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "deployments" / "fork.discovered.json", deploy_dir)
    state_dir = tmp_path / "state"
    env = {
        **os.environ,
        "AFTERHOURS_PATHS__DEPLOYMENTS_DIR": str(deploy_dir.relative_to(REPO_ROOT)),
        "AFTERHOURS_PATHS__STATE_DIR": str(state_dir),
        "DEMO_EXIT": "1",
        "DEMO_SKIP_WEB": "1",
        "ANVIL_PORT": str(port),
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
    profile = load_config(load_env_file=False).demo.profile
    result = json.loads((state_dir / f"{profile}.closing_bell.json").read_text())
    assert result["derisked"], result
    assert result["reasons"], result
    assert all(r["registry_tx"].startswith("0x") for r in result["reasons"])
