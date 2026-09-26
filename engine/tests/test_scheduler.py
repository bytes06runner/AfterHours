"""Tests for the clock-aware scheduler's pure parts."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from afterhours.bot.scheduler import (
    TriggerState,
    divergence_triggers,
    earnings_times,
    schedule_marks,
    shock_triggers,
    stale_triggers,
    v3_pool_price,
)
from afterhours.config import load_config


def test_marks_on_a_friday() -> None:
    sched = load_config(load_env_file=False).schedule
    start = datetime(2026, 9, 25, 16, 30, tzinfo=UTC)  # Friday 12:30 New York
    end = datetime(2026, 9, 25, 21, 30, tzinfo=UTC)
    names = [n for _, n in schedule_marks(sched, "XNYS", start, end, {})]
    assert names.count("hourly") == 5
    assert names.count("pre_close") == 1  # 18:00 UTC = 16:00 close - 120 min
    when = dict(
        (n, t) for t, n in schedule_marks(sched, "XNYS", start, end, {}) if n == "pre_close"
    )
    assert when["pre_close"] == datetime(2026, 9, 25, 18, 0, tzinfo=UTC)


def test_pre_earnings_mark() -> None:
    sched = load_config(load_env_file=False).schedule
    events = {"META": earnings_times("XNYS", [(date(2026, 10, 28), "amc")])}
    start = datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
    marks = schedule_marks(sched, "XNYS", start, start + timedelta(days=2), events)
    pre = [t for t, n in marks if n == "pre_earnings:META"]
    assert pre == [datetime(2026, 10, 27, 20, 0, tzinfo=UTC)]  # 24 h before the 16:00 close


def test_shock_trigger_fires_once_move_exceeds_threshold() -> None:
    state = TriggerState()
    t0 = datetime(2026, 9, 28, 14, 0, tzinfo=UTC)
    assert shock_triggers(state, t0, {"NVDA": 100.0}, 0.03, timedelta(minutes=15)) == []
    fired = shock_triggers(
        state, t0 + timedelta(minutes=5), {"NVDA": 96.0}, 0.03, timedelta(minutes=15)
    )
    assert fired == ["shock:NVDA"]
    later = shock_triggers(
        state, t0 + timedelta(minutes=30), {"NVDA": 96.1}, 0.03, timedelta(minutes=15)
    )
    assert later == []  # the old sample left the window


def test_stale_only_while_open() -> None:
    now = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
    updated = {"SPY": now - timedelta(hours=30)}
    assert stale_triggers(updated, now, True, timedelta(minutes=1470)) == ["stale:SPY"]
    assert stale_triggers(updated, now, False, timedelta(minutes=1470)) == []


def test_pool_price_and_divergence() -> None:
    # 225 USDG per token, stock is token0 (18 decimals), USDG token1 (6 decimals).
    raw = 225 * 10 ** (6 - 18)
    sqrt = int((raw**0.5) * 2**96)
    assert v3_pool_price(sqrt, True, 18, 6) == pytest.approx(225, rel=1e-9)
    assert divergence_triggers({"NVDA": 230.0}, {"NVDA": 225.0}, 0.02) == ["divergence:NVDA"]
    assert divergence_triggers({"NVDA": 226.0}, {"NVDA": 225.0}, 0.02) == []
