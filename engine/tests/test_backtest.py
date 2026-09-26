"""Tests for the economics simulator."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from afterhours.backtest.sim import SimParams, bad_debt_fraction, run_strategy, summarise
from afterhours.policy.lp import tier_spec

WEEKDAY = tier_spec("weekday", 0.86)
WEEKEND = tier_spec("weekend", 0.625)


def params(**over: object) -> SimParams:
    base = dict(
        weekday=WEEKDAY,
        weekend=WEEKEND,
        apy={"weekday": 0.085, "weekend": 0.055},
        vault_usdg=1_000_000.0,
        utilization=0.85,
        turnover=0.2,
        ltv_low=0.6,
        ltv_high=0.98,
        grid=200,
        session_hours=6.5,
        safety_margin=0.02,
        turnover_penalty=0.0005,
        min_rebalance_usd=1000.0,
        max_share_per_stock=1.0,
        depth_multiplier=0.5,
        depth_usd={"A": 1e12},
    )
    base.update(over)
    return SimParams(**base)  # type: ignore[arg-type]


def periods(gaps: list[float], segments: list[str] | None = None) -> pd.DataFrame:
    start = date(2020, 1, 6)
    rows = []
    for i, g in enumerate(gaps):
        d = start + timedelta(days=i)
        rows.append(
            {
                "ticker": "A",
                "session_prev": d,
                "session_next": d + timedelta(days=1),
                "g": g,
                "hours_closed": 17.5,
                "segment": (segments or ["overnight"] * len(gaps))[i],
            }
        )
    return pd.DataFrame(rows)


def test_no_bad_debt_on_small_moves() -> None:
    assert bad_debt_fraction(-0.02, WEEKDAY, 0.6, 0.98, 200) == 0.0
    assert bad_debt_fraction(0.05, WEEKEND, 0.6, 0.98, 200) == 0.0


def test_bad_debt_grows_with_gap_and_lltv() -> None:
    small = bad_debt_fraction(-0.15, WEEKDAY, 0.6, 0.98, 200)
    big = bad_debt_fraction(-0.30, WEEKDAY, 0.6, 0.98, 200)
    safer = bad_debt_fraction(-0.30, WEEKEND, 0.6, 0.98, 200)
    assert 0 < small < big
    assert safer < big


def test_bad_debt_matches_closed_form_for_one_borrower() -> None:
    # One borrower at LTV 0.86 x 0.98; loss = 1 - (1 + g) / (ltv x LIF)
    lif = 1 + WEEKDAY.allowance / WEEKDAY.lltv
    ltv = 0.86 * 0.98
    assert bad_debt_fraction(-0.2, WEEKDAY, 0.98, 0.98, 1) == pytest.approx(1 - 0.8 / (ltv * lif))


def test_afterhours_avoids_the_known_crash_better_than_weekday() -> None:
    gaps = [0.0] * 30 + [-0.25] + [0.0] * 5
    data = periods(gaps)
    risky = {data["session_prev"].iloc[30]}

    def fc(row: object) -> float:
        return 0.30 if row.session_prev in risky else 0.02  # type: ignore[attr-defined]

    p = params()
    wd = run_strategy("always_weekday", p, data, fc)
    ah = run_strategy("afterhours", p, data, fc)
    pf = run_strategy("perfect_foresight", p, data, fc)
    assert wd.bad_debt > 0
    assert ah.bad_debt < wd.bad_debt  # only the unborrowed part could move
    assert ah.bad_debt > 0  # loans already made stay exposed
    assert pf.bad_debt <= ah.bad_debt + 1e-9
    s = summarise(ah, p, years=36 / 365)
    assert s["share_of_time"]["weekday"] > s["share_of_time"]["weekend"]
