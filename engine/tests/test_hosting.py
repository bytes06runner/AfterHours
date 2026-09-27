"""Hosting: persistent paths come from the environment, and the hosted bot needs one key only."""

from __future__ import annotations

from pathlib import Path

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
