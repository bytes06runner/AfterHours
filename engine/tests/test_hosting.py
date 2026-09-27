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
