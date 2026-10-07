"""Hosting: persistent paths come from the environment, and the hosted bot needs one key only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from afterhours.config import REPO_ROOT, load_config
from afterhours.deploy import role_keys


def render_env() -> dict[str, str]:
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text())
    (svc,) = doc["services"]
    return {e["key"]: e.get("value", "") for e in svc["envVars"]}


def test_render_paths_are_on_the_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text())
    mount = Path(doc["services"][0]["disk"]["mountPath"])
    env = render_env()
    for key in ("AFTERHOURS_PATHS__STATE_DIR", "AFTERHOURS_DATA__CACHE_DIR"):
        monkeypatch.setenv(key, env[key])
    cfg = load_config(load_env_file=False)
    for path in (cfg.path(cfg.paths.state_dir), cfg.path(cfg.data.cache_dir)):
        assert path.is_relative_to(mount)


def test_render_asks_for_every_secret_it_needs() -> None:
    env = render_env()
    cfg = load_config(load_env_file=False)
    needed = {"ALLOCATOR_PK", cfg.alerts.token_env, cfg.api.cors_origins_env}
    assert needed <= set(env)
    # The deployer, curator and guardian keys stay on your machine.
    assert not {"DEPLOYER_PK", "CURATOR_PK", "GUARDIAN_PK"} & set(env)


def test_bot_needs_only_the_allocator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for role in ("DEPLOYER_PK", "CURATOR_PK", "GUARDIAN_PK"):
        monkeypatch.delenv(role, raising=False)
    monkeypatch.setenv("ALLOCATOR_PK", "0x" + "11" * 32)
    cfg = load_config(load_env_file=False)
    assert set(role_keys(cfg, "rh-testnet", ("ALLOCATOR_PK",))) == {"ALLOCATOR_PK"}
    with pytest.raises(KeyError, match="DEPLOYER_PK"):
        role_keys(cfg, "rh-testnet")


def test_live_views_find_stock_tokens_on_a_testnet_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hosted API runs on rh-testnet, which has no discovered file; the live views must still
    fetch prices for every mainnet Stock Token (this was empty before the fix)."""
    from afterhours.data.universe import stock_token_tickers

    monkeypatch.setenv("AFTERHOURS_ACTIVE_PROFILE", "rh-testnet")
    cfg = load_config(load_env_file=False)
    assert stock_token_tickers(cfg)[0] == []
    assert len(stock_token_tickers(cfg, cfg.live.discovery_profile)[0]) > 0


def test_curator_top_up_sends_only_what_is_missing() -> None:
    from afterhours.deploy import top_up

    balances = {"curator": 0}
    sent: list[int] = []

    def send(address: str, wei: int) -> None:
        sent.append(wei)
        balances[address] += wei

    target = int(load_config(load_env_file=False).funding.curator_eth * 10**18)
    assert top_up(balances.__getitem__, send, "curator", target) == target
    assert top_up(balances.__getitem__, send, "curator", target) == 0  # enough: no transfer
    balances["curator"] = target - 7
    assert top_up(balances.__getitem__, send, "curator", target) == 7
    assert sent == [target, 7]


def test_health_answers_head() -> None:
    from fastapi.testclient import TestClient

    from afterhours.api.app import create_app

    client = TestClient(create_app(load_config(load_env_file=False)))
    assert client.head("/v1/health").status_code == 200


def test_cors_allows_the_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from afterhours.api.app import create_app

    cfg = load_config(load_env_file=False)
    site = "https://site.example"
    monkeypatch.setenv(cfg.api.cors_origins_env, f" {site} ,https://other.example")
    client = TestClient(create_app(cfg))
    res = client.get("/v1/config/public", headers={"Origin": site})
    assert res.headers.get("access-control-allow-origin") == site


def test_timelock_plan_and_hardening_only_raise() -> None:
    from eth_utils import keccak

    from afterhours.chain.abi import encode_call
    from afterhours.deploy import INCREASE_TIMELOCK, harden_timelocks, timelock_plan

    cfg = load_config(load_env_file=False)
    fns = cfg.vault.harden_timelock_functions
    assert "setReceiveSharesGate(address)" in fns  # an exit gate
    assert not any(f.startswith(("removeAdapter", "decrease")) for f in fns)  # de-risking stays
    now = {fns[0]: 0, fns[1]: 86_400, fns[2]: 172_800}

    def read(calls: list[Any]) -> list[Any]:
        by_sel = {keccak(text=f)[:4]: f for f in fns}
        if calls[0].signature.startswith("timelock"):
            return [now.get(by_sel[c.args[0]], 0) for c in calls]
        return [by_sel[c.args[0]] == fns[3] for c in calls]  # fns[3] abdicated

    plan = timelock_plan(read, "0xVault", fns, 86_400)
    by = {p["function"]: p["action"] for p in plan}
    assert by[fns[0]] == "raise"
    assert by[fns[1]] == "keep"
    assert by[fns[2]] == "keep"  # never lowered
    assert by[fns[3]] == "abdicated"
    sent: list[tuple[str, str, tuple[Any, ...]]] = []

    class Tx:
        tx_hash = "0xabc"

    def send(to: str, sig: str, *args: Any) -> Tx:
        sent.append((to, sig, args))
        return Tx()

    txs = harden_timelocks(send, "0xVault", plan)
    raises = [p for p in plan if p["action"] == "raise"]
    assert len(txs) == 2 * len(raises)
    sel0 = keccak(text=fns[0])[:4]
    assert sent[0] == ("0xVault", "submit(bytes)", (encode_call(INCREASE_TIMELOCK, sel0, 86_400),))
    assert sent[1] == ("0xVault", INCREASE_TIMELOCK, (sel0, 86_400))


def test_hardening_refuses_mainnet_and_local_profiles() -> None:
    from typer.testing import CliRunner

    from afterhours.cli import app

    runner = CliRunner()
    for profile in ("rh-mainnet", "local", "fork"):
        res = runner.invoke(app, ["harden-timelocks", "--profile", profile])
        assert res.exit_code != 0
        assert "not a testnet profile" in res.output
