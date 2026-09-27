"""Tests for the Telegram alert bot, with a fake chat and a fake mainnet source."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from afterhours.config import AfterhoursConfig, load_config
from afterhours.live.alerts import AlertBot, Store, check_window, handle, run_checks

ADDR = "0x498752D5fa0600CBd613074C151Abe15B3FeC7CB"
PRE_CLOSE = datetime(2026, 9, 25, 18, 30, tzinfo=UTC)  # Friday 14:30 New York, inside the window
MIDDAY = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)  # 11:00 New York, before it


def forecast(drop: float) -> dict[str, Any]:
    return {"bad_case_drop": drop, "period": {"hours": 65.5}}


class FakeSource:
    def __init__(self, drop: float) -> None:
        self.feeds = {"NVDA": "0x1", "TSLA": "0x2"}
        self.drop = drop
        self.calls = 0

    def board(self, now: datetime | None = None) -> dict[str, Any]:
        self.calls += 1
        cushion = 0.05
        return {
            "stocks": [
                {
                    "symbol": s,
                    "tonight": forecast(self.drop),
                    "markets": [{"lltv": 0.915, "cushion": cushion}],
                    "breached": [0.915] if self.drop >= cushion else [],
                }
                for s in self.feeds
            ]
        }

    def positions(self, address: str, now: datetime | None = None) -> dict[str, Any]:
        self.calls += 1
        drop_to_liq = 0.12
        return {
            "positions": [
                {
                    "symbol": "NVDA",
                    "liquidation_price": 121.85,
                    "drop_to_liquidation": drop_to_liq,
                    "tonight": forecast(self.drop),
                    "breach_tonight": self.drop >= drop_to_liq,
                }
            ]
        }


class FakeChat:
    def __init__(self, inbox: list[tuple[int, str]]) -> None:
        self.inbox = inbox
        self.sent: list[tuple[int, str]] = []

    def updates(self, offset: int | None) -> list[dict[str, Any]]:
        out = [
            {"update_id": i, "message": {"chat": {"id": c}, "text": t}}
            for i, (c, t) in enumerate(self.inbox)
            if offset is None or i >= offset
        ]
        return out

    def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.fixture
def cfg(tmp_path: Path) -> AfterhoursConfig:
    base = load_config(load_env_file=False)
    paths = base.paths.model_copy(update={"state_dir": str(tmp_path)})
    return base.model_copy(update={"paths": paths})


def test_commands(tmp_path: Path) -> None:
    store = Store(tmp_path / "a.json")
    syms = {"NVDA"}
    assert "/watch" in handle(store, 1, "/start", syms, "Robinhood Chain", 3)
    assert "Following NVDA" in handle(store, 1, "/watch nvda", syms, "x", 3)
    assert "already" in handle(store, 1, "/watch NVDA", syms, "x", 3)
    assert "not a Stock Token" in handle(store, 1, "/watch ZZZZ", syms, "x", 3)
    assert "Following" in handle(store, 1, f"/watch {ADDR.lower()}", syms, "x", 3)
    assert store.chats["1"]["addresses"] == [ADDR]  # stored checksummed
    assert "NVDA" in handle(store, 1, "/list", syms, "x", 3)
    assert "Stopped following" in handle(store, 1, "/unwatch NVDA", syms, "x", 3)
    assert "Stopped." in handle(store, 1, "/stop", syms, "x", 3)
    assert "1" not in store.chats


def test_watch_limit(tmp_path: Path) -> None:
    store = Store(tmp_path / "a.json")
    handle(store, 1, "/watch NVDA", {"NVDA", "TSLA"}, "x", 1)
    assert "up to 1" in handle(store, 1, "/watch TSLA", {"NVDA", "TSLA"}, "x", 1)


def test_window() -> None:
    cfg = load_config(load_env_file=False)
    close = check_window(cfg, PRE_CLOSE)
    assert close == datetime(2026, 9, 25, 20, 0, tzinfo=UTC)  # 16:00 New York
    assert check_window(cfg, MIDDAY) is None
    assert check_window(cfg, datetime(2026, 9, 26, 18, 30, tzinfo=UTC)) is None  # Saturday


def test_alerts_once_per_close(tmp_path: Path) -> None:
    store = Store(tmp_path / "a.json")
    handle(store, 7, "/watch NVDA", {"NVDA"}, "x", 5)
    handle(store, 7, f"/watch {ADDR}", {"NVDA"}, "x", 5)
    close = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    risky = FakeSource(0.15)  # beyond the 5% cushion and the 12% drop to liquidation
    msgs = run_checks(store, risky, close, PRE_CLOSE)
    assert len(msgs) == 2
    assert "NVDA: tonight's forecast bad case is a 15.0% drop" in msgs[0][1]
    assert "liquidated if the price falls to 121.85" in msgs[1][1]
    assert run_checks(store, risky, close, PRE_CLOSE) == []  # already checked for this close


def test_quiet_night_sends_nothing(tmp_path: Path) -> None:
    store = Store(tmp_path / "a.json")
    handle(store, 7, "/watch NVDA", {"NVDA"}, "x", 5)
    handle(store, 7, f"/watch {ADDR}", {"NVDA"}, "x", 5)
    close = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    assert run_checks(store, FakeSource(0.02), close, PRE_CLOSE) == []


def test_bot_loop(cfg: AfterhoursConfig) -> None:
    chat = FakeChat([(9, "/watch NVDA")])
    source = FakeSource(0.15)
    refreshed: list[int] = []
    bot = AlertBot(cfg, source, chat, clock=lambda: MIDDAY, refresh=lambda: refreshed.append(1))
    bot.poll()
    assert chat.sent[-1][1].startswith("Following NVDA")
    assert bot.check() == 0
    assert source.calls == 0  # outside the window: no chain reads
    bot.clock = lambda: PRE_CLOSE
    assert bot.check() == 1
    assert bot.check() == 0
    assert refreshed == [1]
    # Subscriptions and the update offset survive a restart.
    again = AlertBot(cfg, source, FakeChat([(9, "/watch NVDA")]), clock=lambda: PRE_CLOSE)
    assert again.store.offset == 1
    assert again.store.chats["9"]["symbols"] == ["NVDA"]
    again.poll()
    assert again.chat.sent == []  # type: ignore[attr-defined]
