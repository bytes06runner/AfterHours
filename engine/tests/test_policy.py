"""Tests for the allocation LP."""

from __future__ import annotations

import pytest

from afterhours.policy.lp import StockState, allowed_tier, solve, tier_spec

WEEKDAY = tier_spec("weekday", 0.86)
WEEKEND = tier_spec("weekend", 0.625)
TIERS = [WEEKDAY, WEEKEND]
KW = dict(
    safety_margin=0.02,
    turnover_penalty=0.0005,
    min_rebalance_usd=1000,
    max_share_per_stock=0.5,
    depth_multiplier=0.5,
)
ONE = {**KW, "max_share_per_stock": 1.0}  # single-stock cases


def stock(
    sym: str,
    q: float,
    *,
    borrowed_weekday: float = 0.0,
    prev: dict[str, float] | None = None,
    depth: float = 10e6,
) -> StockState:
    return StockState(
        symbol=sym,
        bad_case_drop=q,
        depth_usd=depth,
        rate={"weekday": 0.08, "weekend": 0.04},
        borrowed={"weekday": borrowed_weekday, "weekend": 0.0},
        cap={"weekday": 1e9, "weekend": 1e9},
        prev=prev or {"weekday": 0.0, "weekend": 0.0},
    )


def test_tier_cushions_match_morpho_incentive() -> None:
    assert WEEKDAY.cushion == pytest.approx(1 - 0.86 * (1 / (1 - 0.3 * 0.14)))
    assert WEEKEND.cushion == pytest.approx(1 - 0.625 / 0.8875)


def test_allowed_rule_and_reason() -> None:
    ok, why = allowed_tier(0.05, 0.02, WEEKDAY)
    assert ok
    assert "fits inside" in why
    ok, why = allowed_tier(0.12, 0.02, WEEKDAY)
    assert not ok
    assert "exceeds" in why


def test_calm_stock_goes_to_higher_rate_tier() -> None:
    plan = solve([stock("A", 0.03), stock("B", 0.03)], TIERS, total=1_000_000, **KW)
    assert plan.status == "optimal"
    assert plan.allocation[("A", "weekday")] == pytest.approx(500_000)
    assert plan.idle == pytest.approx(0, abs=1e-6)


def test_risky_stock_leaves_weekday_but_borrowed_stays() -> None:
    prev = {"weekday": 400_000.0, "weekend": 0.0}
    plan = solve(
        [stock("A", 0.15, borrowed_weekday=250_000, prev=prev)], TIERS, total=400_000, **ONE
    )
    assert not plan.allowed[("A", "weekday")]
    assert plan.allocation[("A", "weekday")] == pytest.approx(250_000)  # cannot pull borrowed
    assert plan.allocation[("A", "weekend")] == pytest.approx(150_000)
    assert plan.execute


def test_extreme_risk_goes_idle() -> None:
    plan = solve([stock("A", 0.40)], TIERS, total=100_000, **ONE)
    assert not plan.allowed[("A", "weekend")]
    assert plan.idle == pytest.approx(100_000)


def test_depth_limits_exposure() -> None:
    plan = solve([stock("A", 0.03, depth=100_000)], TIERS, total=1_000_000, **ONE)
    assert sum(v for k, v in plan.allocation.items() if k[0] == "A") == pytest.approx(50_000)


def test_small_changes_do_not_execute() -> None:
    prev = {"weekday": 500_000.0, "weekend": 0.0}
    plan = solve([stock("A", 0.03, prev=prev)], TIERS, total=500_400, **ONE)
    assert not plan.execute
