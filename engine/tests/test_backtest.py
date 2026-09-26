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


def _risk_before_crash(data: pd.DataFrame, crash: int, notice: int):  # type: ignore[no-untyped-def]
    risky = set(data["session_prev"].iloc[max(0, crash - notice + 1) : crash + 1])

    def fc(row: object) -> float:
        return 0.30 if row.session_prev in risky else 0.02  # type: ignore[attr-defined]

    return fc


def test_one_close_of_notice_cannot_shrink_open_loans() -> None:
    data = periods([0.0] * 30 + [-0.25] + [0.0] * 5)
    p = params()
    wd = run_strategy("always_weekday", p, data, _risk_before_crash(data, 30, 1))
    ah = run_strategy("afterhours", p, data, _risk_before_crash(data, 30, 1))
    assert wd.bad_debt > 0
    assert ah.bad_debt == pytest.approx(wd.bad_debt)  # loans already made stay exposed


def test_earlier_notice_lets_loans_roll_off() -> None:
    data = periods([0.0] * 30 + [-0.25] + [0.0] * 5)
    p = params()
    wd = run_strategy("always_weekday", p, data, _risk_before_crash(data, 30, 1))
    ah = run_strategy("afterhours", p, data, _risk_before_crash(data, 30, 10))
    # Flagged 10 closes ahead, the vault pulls at the first; 9 sessions of 20% roll-off follow
    # before the crash, leaving 0.8^9 (about 13%) of the loans.
    assert ah.bad_debt == pytest.approx(wd.bad_debt * 0.8**9, rel=0.02)
    s = summarise(ah, p, years=36 / 365)
    assert s["share_of_time"]["weekday"] > s["share_of_time"]["weekend"]
