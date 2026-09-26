"""Option B, the shipped policy (PROGRESS.md, 2026-09-27): a yearly tier map plus a pullback.

- Tier map: each January every stock is rated by its worst `quantile` closed-period gap over the
  previous `window_days` (trailing data only). It may use the highest tier whose cushion x
  (1 - map fraction) covers that rating, and never less than the weekend tier.
- Pullback: on a night when the forecast bad case (the worst of the next `lookahead` closed
  periods) exceeds every tier's cushion x (1 - pullback fraction), the stock's unborrowed money
  goes idle. There are no per-night moves between tiers.

The backtest (`backtest/option_b.py`) and the bot both use these functions, so the policy that
was evaluated is the policy that runs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from afterhours.policy.lp import TierSpec, allowed_tier

PULLED = 1.0  # a drop no tier admits: the LP may keep only what is lent out


@dataclass(frozen=True)
class Decision:
    """B's view of one stock for one night."""

    symbol: str
    rating: float | None  # worst-quantile gap over the rating window; None if too little data
    rating_year: int
    mapped_tier: str  # the highest tier the map allows
    forecast_bad_case: float
    pull_limit: float
    pulled: bool
    lp_drop: float  # what the LP sees (with margin fraction = map fraction)


def rating_from_gaps(gaps: pd.Series, quantile: float, min_observations: int) -> float | None:
    """Worst `quantile` gap as a positive drop, or None with too few observations."""
    g = gaps.dropna()
    if len(g) < min_observations:
        return None
    return max(0.0, -float(np.quantile(g, quantile)))


def gaps_from_prices(prices: pd.DataFrame) -> pd.Series:
    """Closed-period gaps from daily prices: next open / previous close - 1, indexed by the
    session before the gap."""
    p = prices.sort_index()
    g = p["open"].shift(-1) / p["close"] - 1
    g.index = pd.to_datetime(p.index).date
    return g.iloc[:-1]


def rating_window(year: int, window_days: int) -> tuple[date, date]:
    """[start, end) of the trailing window used to rate a stock for `year`."""
    end = date(year, 1, 1)
    return end - timedelta(days=window_days), end


def floor_limit(tiers: Sequence[TierSpec], map_fraction: float) -> float:
    """The limit of the lowest-LLTV tier (the widest cushion): the map never places a stock
    below it."""
    return min(tiers, key=lambda t: t.lltv).cushion * (1 - map_fraction)


def pull_limit(tiers: Sequence[TierSpec], pullback_fraction: float) -> float:
    """The largest limit of any tier: a bad case above it fits nowhere."""
    return max(t.cushion for t in tiers) * (1 - pullback_fraction)


def mapped_tier(rating: float | None, tiers: Sequence[TierSpec], map_fraction: float) -> TierSpec:
    """Highest-LLTV tier whose cushion x (1 - map fraction) covers the rating; else the lowest."""
    lowest = min(tiers, key=lambda t: t.lltv)
    if rating is None:
        return lowest
    ok = [t for t in tiers if rating <= t.cushion * (1 - map_fraction)]
    return max(ok, key=lambda t: t.lltv) if ok else lowest


def decide(
    symbol: str,
    rating: float | None,
    rating_year: int,
    forecast_bad_case: float,
    tiers: Sequence[TierSpec],
    map_fraction: float,
    pullback_fraction: float,
) -> Decision:
    floor = floor_limit(tiers, map_fraction)
    limit = pull_limit(tiers, pullback_fraction)
    pulled = forecast_bad_case > limit
    lp_drop = PULLED if pulled else min(rating if rating is not None else floor, floor)
    return Decision(
        symbol=symbol,
        rating=rating,
        rating_year=rating_year,
        mapped_tier=mapped_tier(rating, tiers, map_fraction).name,
        forecast_bad_case=forecast_bad_case,
        pull_limit=limit,
        pulled=pulled,
        lp_drop=lp_drop,
    )


def reason(d: Decision, tiers: Sequence[TierSpec], map_fraction: float, lookahead: int) -> str:
    """Plain-English reason for B's decision on one stock."""
    tier = next(t for t in tiers if t.name == d.mapped_tier)
    if d.pulled:
        return (
            f"Pullback: the forecast bad case for {d.symbol} over the next {lookahead} closed "
            f"periods is {d.forecast_bad_case:.1%}, above every tier's limit (the largest is "
            f"{d.pull_limit:.1%}), so money not lent out goes idle. Money lent out stays until "
            "repaid."
        )
    if d.rating is None:
        return (
            f"Tier map for {d.rating_year}: too little history to rate {d.symbol}, so it may use "
            f"only the {tier.name} tier (LLTV {tier.lltv:.1%})."
        )
    return (
        f"Tier map for {d.rating_year}: {d.symbol}'s worst 1% closed-period gap over the previous "
        f"year was {d.rating:.1%}, which fits the {tier.name} tier "
        f"({1 - map_fraction:.0%} of its {tier.cushion:.1%} cushion, LLTV {tier.lltv:.1%}). "
        f"Tonight's forecast bad case, {d.forecast_bad_case:.1%}, is within the pullback limit of "
        f"{d.pull_limit:.1%}."
    )


def live_ratings(
    prices: dict[str, pd.DataFrame | None],
    year: int,
    window_days: int,
    quantile: float,
    min_observations: int,
) -> dict[str, float | None]:
    """Ratings for `year` from cached daily prices, trailing window only."""
    start, end = rating_window(year, window_days)
    out: dict[str, float | None] = {}
    for symbol, frame in prices.items():
        if frame is None or frame.empty:
            out[symbol] = None
            continue
        g = gaps_from_prices(frame)
        win = g[[start <= d < end for d in g.index]]
        out[symbol] = rating_from_gaps(win, quantile, min_observations)
    return out


def allowed_tiers(d: Decision, tiers: Sequence[TierSpec], map_fraction: float) -> dict[str, bool]:
    """Which tiers B lets the stock use tonight (what the LP enforces)."""
    return {t.name: allowed_tier(d.lp_drop, 0.0, t, map_fraction)[0] for t in tiers}
