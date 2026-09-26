"""M6 acceptance on a throwaway Anvil chain (the local profile; the fork run needs an archive RPC).

Deploys, seeds, starts the API, listens to the event stream, forces a close-out, then checks:
funds moved exactly as planned, every registry event matches the recomputed card hash, and the
stream delivered every event type.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from afterhours.config import REPO_ROOT

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    if not shutil.which("anvil"):
        pytest.skip("anvil not installed")
    port = _free_port()
    anvil = subprocess.Popen(["anvil", "--port", str(port), "--silent"])
    deploy_dir = REPO_ROOT / "contracts" / "cache" / f"it-deployments-{port}"
    deploy_dir.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "deployments" / "fork.discovered.json", deploy_dir)
    state_dir = tmp_path_factory.mktemp("state")
    env = {
        **os.environ,
        "ANVIL_PORT": str(port),
        "AFTERHOURS_ACTIVE_PROFILE": "local",
        "AFTERHOURS_PATHS__DEPLOYMENTS_DIR": str(deploy_dir.relative_to(REPO_ROOT)),
        "AFTERHOURS_PATHS__STATE_DIR": str(state_dir),
        "ADMIN_TOKEN": "integration-token",
        "API_HOST": "127.0.0.1",
        "API_PORT": str(_free_port()),
    }
    time.sleep(1)

    def run(*args: str) -> None:
        subprocess.run(
            ["uv", "run", "--quiet", "afterhours", *args],
            env=env,
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    try:
        run("deploy")
        run("sim", "seed")
        api = subprocess.Popen(
            ["uv", "run", "--quiet", "afterhours", "api"], env=env, cwd=REPO_ROOT
        )
        base = f"http://127.0.0.1:{env['API_PORT']}"  # hardcode-ok: test server
        for _ in range(60):
            try:
                if httpx.get(f"{base}/v1/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(1)
        yield {
            "base": base,
            "deploy_dir": str(deploy_dir),
            "state_dir": str(state_dir),
            "token": env["ADMIN_TOKEN"],
        }
        api.terminate()
    finally:
        anvil.terminate()
        shutil.rmtree(deploy_dir, ignore_errors=True)


def test_close_out_moves_funds_as_planned_and_everything_verifies(stack: dict[str, str]) -> None:
    base = stack["base"]
    seen: list[str] = []
    stop = threading.Event()

    def listen() -> None:
        with httpx.stream("GET", f"{base}/v1/stream?replay=true", timeout=None) as r:
            for line in r.iter_lines():
                if line.startswith("event:"):
                    seen.append(line.split(":", 1)[1].strip())
                if stop.is_set():
                    return

    threading.Thread(target=listen, daemon=True).start()
    time.sleep(2)
    shock = httpx.post(
        f"{base}/v1/sim/shock",
        json={"symbol": "SPY", "pct": 0.0},
        headers={"authorization": f"Bearer {stack['token']}"},
        timeout=60,
    )
    assert shock.status_code == 200
    res = httpx.post(
        f"{base}/v1/sim/close-out",
        headers={"authorization": f"Bearer {stack['token']}"},
        timeout=300,
    )
    assert res.status_code == 200, res.text
    body = res.json()

    # Funds moved exactly as planned (to the unit, less dust).
    vault = httpx.get(f"{base}/v1/vault", timeout=60).json()
    placed = {f"{m['symbol']}:{m['tier']}": m["vault_supply"] for m in vault["markets"]}
    for key, target in body["plan"]["allocation"].items():
        assert placed[key] == pytest.approx(target, abs=0.01), key

    # Every reason card matches its registry event.
    cards = httpx.get(f"{base}/v1/reasons", timeout=60).json()["items"]
    assert cards
    for c in cards:
        detail = httpx.get(f"{base}/v1/reasons/{c['id']}", timeout=60).json()
        assert detail["verification"]["status"] == "matched", detail["verification"]

    # The stream carried every event type.
    deadline = time.time() + 30
    wanted = {"status", "plan_changed", "tx_sent", "tx_confirmed", "reason_logged", "vault_updated"}
    while time.time() < deadline and not wanted <= set(seen):
        time.sleep(0.5)
    stop.set()
    assert wanted <= set(seen), f"missing {wanted - set(seen)}"
    Path(stack["state_dir"], "acceptance.json").write_text(
        json.dumps({"events": sorted(set(seen))})
    )
