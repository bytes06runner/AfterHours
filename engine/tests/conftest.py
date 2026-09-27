"""Tests never reach real services, even when `make` exports .env into the environment."""

from __future__ import annotations

import pytest

from afterhours.config import load_config

_cfg = load_config(load_env_file=False)
# Shared store and Telegram credentials: without them the code falls back to local files and
# refuses to send, and tests that need them use fakes (tests/fake_upstash.py, FakeTelegram).
LIVE_ENV = (
    _cfg.state.kv_url_env,
    _cfg.state.kv_token_env,
    _cfg.alerts.token_env,
    _cfg.alerts.webhook_secret_env,
)


@pytest.fixture(autouse=True)
def no_live_services(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LIVE_ENV:
        monkeypatch.delenv(name, raising=False)
    # load_config() without load_env_file=False would read .env again and refill them.
    monkeypatch.setattr("afterhours.config.load_dotenv", lambda *a, **k: False)
