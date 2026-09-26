"""The shipped policy (option B): yearly tier map plus pullback, shared by bot and backtest."""

from __future__ import annotations

import pandas as pd
import pytest

from afterhours.policy.lp import tier_spec
from afterhours.policy.option_b import (
    PULLED,
    decide,
    floor_limit,
    gaps_from_prices,
    mapped_tier,
    pull_limit,
    rating_from_gaps,
)

TIERS = [tier_spec("weekday", 0.915), tier_spec("middle", 0.86), tier_spec("weekend", 0.77)]


def test_limits_use_the_right_tiers() -> None:
    # The floor is the lowest-LLTV tier (widest cushion), not the smallest cushion.
    weekend = TIERS[2].cushion
    assert floor_limit(TIERS, 0.4) == pytest.approx(weekend * 0.6)
    assert pull_limit(TIERS, 0.4) == pytest.approx(weekend * 0.6)
    assert weekend > TIERS[1].cushion > TIERS[0].cushion


def test_mapped_tier_is_the_highest_that_covers_the_rating() -> None:
    assert mapped_tier(0.01, TIERS, 0.4).name == "weekday"  # 6.1% x 0.6 = 3.7%
    assert mapped_tier(0.05, TIERS, 0.4).name == "middle"  # 10.2% x 0.6 = 6.1%
    assert mapped_tier(0.09, TIERS, 0.4).name == "weekend"
    assert mapped_tier(0.50, TIERS, 0.4).name == "weekend"  # never below the lowest tier
    assert mapped_tier(None, TIERS, 0.4).name == "weekend"


def test_pullback_only_when_the_bad_case_fits_nowhere() -> None:
    stay = decide("NVDA", 0.05, 2026, 0.09, TIERS, 0.4, 0.4)
    assert not stay.pulled
    assert stay.lp_drop == pytest.approx(0.05)
    pull = decide("NVDA", 0.05, 2026, 0.20, TIERS, 0.4, 0.4)
    assert pull.pulled
    assert pull.lp_drop == PULLED
    # No downgrades between tiers: a bad case above the weekday limit but below the pullback
    # limit leaves the mapped tier unchanged.
    d = decide("SPY", 0.01, 2026, 0.08, TIERS, 0.4, 0.4)
    assert not d.pulled
    assert d.mapped_tier == "weekday"


def test_rating_from_prices() -> None:
    idx = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    prices = pd.DataFrame({"open": [100.0, 90.0, 99.0], "close": [100.0, 100.0, 100.0]}, idx)
    g = gaps_from_prices(prices)
    assert list(g.round(3)) == [-0.1, -0.01]
    assert rating_from_gaps(g, 0.01, 2) == pytest.approx(0.1, rel=0.02)
    assert rating_from_gaps(g, 0.01, 3) is None
