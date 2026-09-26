"""Dataset tests, including the lookahead guard required by SPEC 7.2."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from afterhours.features.dataset import (
    FEATURES,
    build_dataset,
    closed_periods,
    earnings_flags,
    sessions,
)

CAL = "XNYS"


def _prices(sess: pd.DataFrame, seed: int, start: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(sess)
    close = start * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    open_ = close * np.exp(rng.normal(0, 0.01, n))
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.01,
            "low": np.minimum(open_, close) * 0.99,
            "close": close,
            "volume": 1e6,
        },
        index=sess.index,
    )
    return frame


@pytest.fixture(scope="module")
def world() -> dict[str, object]:
    sess = sessions(CAL, date(2019, 1, 1), date(2020, 12, 31))
    prices = {
        "AAA": _prices(sess, 1),
        "BBB": _prices(sess, 2),
        "SPY": _prices(sess, 3),
        "^VIX": _prices(sess, 4, 20),
    }
    earnings = {
        "AAA": pd.DataFrame(
            {
                "date": [
                    date(2019, 4, 25),
                    date(2019, 7, 25),
                    date(2020, 1, 30),
                    date(2020, 7, 30),
                ],
                "timing": ["amc", "bmo", "unknown", "amc"],
            }
        ),
    }
    return {"sess": sess, "prices": prices, "earnings": earnings}


def _build(world: dict[str, object], prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return build_dataset(
        prices,
        world["earnings"],
        world["sess"],
        vix_ticker="^VIX",
        market_ticker="SPY",  # type: ignore[arg-type]
        sectors={"AAA": "Tech", "BBB": "Energy"},
    )


def test_no_lookahead(world: dict[str, object]) -> None:
    base = _build(world, world["prices"])  # type: ignore[arg-type]
    cutoff = date(2020, 3, 13)
    rng = np.random.default_rng(99)
    shocked = {}
    for t, original in world["prices"].items():  # type: ignore[attr-defined]
        px = original.copy()
        future = px.index > cutoff
        px.loc[future, ["open", "high", "low", "close"]] *= rng.uniform(0.5, 1.5, (future.sum(), 1))
        shocked[t] = px
    after = _build(world, shocked)
    key = ["ticker", "session_prev"]
    a = base[base["session_prev"] <= cutoff].set_index(key)[FEATURES]
    b = after[after["session_prev"] <= cutoff].set_index(key)[FEATURES]
    pd.testing.assert_frame_equal(a, b)
    # The target of the period that straddles the cutoff must change: we did perturb the future.
    straddle = base["session_prev"] == cutoff
    assert not np.allclose(base.loc[straddle, "g"], after.loc[after["session_prev"] == cutoff, "g"])


def test_target_is_open_over_previous_close(world: dict[str, object]) -> None:
    data = _build(world, world["prices"])  # type: ignore[arg-type]
    px = world["prices"]["AAA"]  # type: ignore[index]
    row = data[data["ticker"] == "AAA"].iloc[100]
    assert row["g"] == pytest.approx(
        px.at[row["session_next"], "open"] / px.at[row["session_prev"], "close"] - 1
    )


def test_segments(world: dict[str, object]) -> None:
    periods = closed_periods(world["sess"])  # type: ignore[arg-type]
    seg = dict(zip(periods["session_prev"], periods["calendar_segment"], strict=True))
    assert seg[date(2020, 3, 12)] == "overnight"  # Thu -> Fri
    assert seg[date(2020, 3, 13)] == "weekend"  # Fri -> Mon
    assert seg[date(2020, 7, 2)] == "holiday"  # Thu -> Mon, Fri 3 July observed holiday
    hours = dict(zip(periods["session_prev"], periods["hours_closed"], strict=True))
    assert hours[date(2020, 3, 12)] == pytest.approx(17.5)
    assert hours[date(2020, 3, 13)] == pytest.approx(65.5)


def test_earnings_timing_assignment(world: dict[str, object]) -> None:
    periods = closed_periods(world["sess"])  # type: ignore[arg-type]
    events = world["earnings"]["AAA"]  # type: ignore[index]
    flags = earnings_flags(periods, events)
    flagged = set(periods.loc[flags, "session_prev"])
    assert date(2019, 4, 25) in flagged  # amc: the night after
    assert date(2019, 7, 24) in flagged  # bmo: the night before
    assert {date(2020, 1, 29), date(2020, 1, 30)} <= flagged  # unknown: both
    data = _build(world, world["prices"])  # type: ignore[arg-type]
    assert set(data.loc[data["ticker"] == "BBB", "segment"]) <= {"holiday", "weekend", "overnight"}
