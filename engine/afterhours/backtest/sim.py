"""Economics simulator: historical stock prices, simulated vault (SPEC 9).

One step per closed period, for all selected stocks at once:

1. Before the close each strategy picks supply x[s, t] per stock and tier. Money already
   lent out (`borrowed`) cannot move; only the unborrowed rest can.
2. The gap g happens. Borrowers in tier t hold LTVs spread uniformly over
   [low, high] x LLTV_t. A borrower with LTV l is left with bad debt when the open is below
   l x LIF_t (the collateral no longer covers debt plus the liquidation incentive); the
   lender loses 1 - (1 + g) / (l x LIF_t) of that debt (Morpho `liquidate` with the
   verified incentive factor).
3. Supply earns the tier's assumed APY for the closed hours plus the next session.
4. Loans roll: a share `loan_turnover_per_session` of each tier's loans is repaid and
   re-borrowed against current supply at the assumed utilisation.

Strategies: always weekday tier, always weekend tier, Afterhours (the LP with the shipped
calibrated forecast), and perfect foresight (the LP given the realised gap).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from afterhours.policy.lp import StockState, TierSpec, solve, tier_spec

STRATEGIES = ("always_weekday", "always_weekend", "afterhours", "perfect_foresight")
HOURS_PER_YEAR = 24 * 365


@dataclass(frozen=True)
class SimParams:
    """Everything the simulator needs besides the data."""

    weekday: TierSpec
    weekend: TierSpec
    apy: dict[str, float]
    vault_usdg: float
    utilization: float
    turnover: float
    ltv_low: float
    ltv_high: float
    grid: int
    session_hours: float
    safety_margin: float
    turnover_penalty: float
    min_rebalance_usd: float
    max_share_per_stock: float
    depth_multiplier: float
    depth_usd: dict[str, float]

    @property
    def tiers(self) -> tuple[TierSpec, TierSpec]:
        return (self.weekday, self.weekend)


def bad_debt_fraction(g: float, tier: TierSpec, low: float, high: float, grid: int) -> float:
    """Expected share of a tier's loans lost to bad debt after a gap g."""
    lif = 1 + tier.allowance / tier.lltv
    ltv = np.linspace(low * tier.lltv, high * tier.lltv, grid)
    loss = np.clip(1 - (1 + g) / (ltv * lif), 0, None)
    return float(loss.mean())


class Row(dict[Any, Any]):
    """A period row with attribute access (`row.ticker`), typed as Any for the checker."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


@dataclass
class Ledger:
    """Running totals for one strategy."""

    assets: float
    supply: dict[tuple[str, str], float] = field(default_factory=dict)
    borrowed: dict[tuple[str, str], float] = field(default_factory=dict)
    interest: float = 0.0
    bad_debt: float = 0.0
    worst_event: dict[str, Any] = field(default_factory=dict)
    tier_usd_hours: dict[str, float] = field(
        default_factory=lambda: {"weekday": 0.0, "weekend": 0.0, "idle": 0.0}
    )
    reallocations: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)


def _target(
    strategy: str,
    p: SimParams,
    stocks: Sequence[str],
    ledger: Ledger,
    q: Mapping[str, float],
    g: Mapping[str, float],
) -> dict[tuple[str, str], float]:
    """Supply per (stock, tier) the strategy wants before this close."""
    total = ledger.assets
    if strategy in ("always_weekday", "always_weekend"):
        tier = "weekday" if strategy == "always_weekday" else "weekend"
        per = min(p.max_share_per_stock, 1 / len(stocks)) * total
        out = {}
        for s in stocks:
            limit = min(per, p.depth_multiplier * p.depth_usd.get(s, float("inf")))
            for t in ("weekday", "weekend"):
                b = ledger.borrowed.get((s, t), 0.0)
                out[(s, t)] = max(b, limit if t == tier else 0.0)
        return out
    risk = q if strategy == "afterhours" else {s: max(0.0, -g[s]) for s in stocks}
    margin = p.safety_margin if strategy == "afterhours" else 0.0
    states = [
        StockState(
            symbol=s,
            bad_case_drop=risk[s],
            depth_usd=p.depth_usd.get(s, 1e18),
            rate=p.apy,
            borrowed={t: ledger.borrowed.get((s, t), 0.0) for t in ("weekday", "weekend")},
            cap={"weekday": total, "weekend": total},
            prev={t: ledger.supply.get((s, t), 0.0) for t in ("weekday", "weekend")},
        )
        for s in stocks
    ]
    plan = solve(
        states,
        p.tiers,
        total=total,
        safety_margin=margin,
        turnover_penalty=p.turnover_penalty,
        min_rebalance_usd=p.min_rebalance_usd,
        max_share_per_stock=p.max_share_per_stock,
        depth_multiplier=p.depth_multiplier,
    )
    if plan.status != "optimal" or not plan.execute:
        return {
            k: max(v, ledger.borrowed.get(k, 0.0)) for k, v in ledger.supply.items()
        } or plan.allocation
    return plan.allocation


def run_strategy(
    strategy: str,
    p: SimParams,
    periods: pd.DataFrame,
    forecast: Callable[[Any], float],
) -> Ledger:
    """Simulate one strategy over `periods` (one row per ticker and closed period)."""
    ledger = Ledger(assets=p.vault_usdg)
    for session_prev, rows in periods.groupby("session_prev", sort=True):
        records: list[dict[str, Any]] = rows.to_dict("records")  # type: ignore[assignment]
        stocks: list[str] = [r["ticker"] for r in records]
        g: dict[str, float] = {r["ticker"]: float(r["g"]) for r in records}
        q = {r["ticker"]: forecast(Row(r)) for r in records}
        target = _target(strategy, p, stocks, ledger, q, g)
        moved = sum(
            abs(target.get(k, 0.0) - ledger.supply.get(k, 0.0))
            for k in set(target) | set(ledger.supply)
        )
        if moved >= p.min_rebalance_usd and ledger.supply:
            ledger.reallocations += 1
        # Stocks absent from this period keep only what is lent out.
        for k in list(ledger.supply):
            if k[0] not in stocks:
                target[k] = ledger.borrowed.get(k, 0.0)
        ledger.supply = {k: v for k, v in target.items() if v > 0}
        for k, v in ledger.supply.items():
            ledger.borrowed.setdefault(k, p.utilization * v)
        hours = float(rows["hours_closed"].iloc[0])
        period_bad = 0.0
        for (s, t), b in list(ledger.borrowed.items()):
            if s not in g or b <= 0:
                continue
            tier = p.weekday if t == "weekday" else p.weekend
            loss = b * bad_debt_fraction(g[s], tier, p.ltv_low, p.ltv_high, p.grid)
            period_bad += loss
            ledger.borrowed[(s, t)] = b - loss
        ledger.bad_debt += period_bad
        ledger.assets -= period_bad
        if period_bad > ledger.worst_event.get("bad_debt_usdg", 0.0):
            worst = Row(min(records, key=lambda r: float(r["g"])))
            ledger.worst_event = {
                "session_prev": str(session_prev),
                "bad_debt_usdg": period_bad,
                "share_of_vault": period_bad / (ledger.assets + period_bad),
                "ticker": worst.ticker,
                "g": float(worst.g),
                "segment": worst.segment,
            }
        if period_bad > 0:
            ledger.events.append({"session_prev": str(session_prev), "bad_debt_usdg": period_bad})
        accrual_h = hours + p.session_hours
        earned = sum(
            v * p.apy[t] * accrual_h / HOURS_PER_YEAR for (s, t), v in ledger.supply.items()
        )
        ledger.interest += earned
        ledger.assets += earned
        placed = 0.0
        for (_s, t), v in ledger.supply.items():
            ledger.tier_usd_hours[t] += v * hours
            placed += v
        ledger.tier_usd_hours["idle"] += max(ledger.assets - placed, 0.0) * hours
        for k, v in ledger.supply.items():
            b = ledger.borrowed.get(k, 0.0)
            ledger.borrowed[k] = min(v, (1 - p.turnover) * b + p.turnover * p.utilization * v)
    return ledger


def summarise(ledger: Ledger, p: SimParams, years: float) -> dict[str, Any]:
    """Headline metrics for one strategy."""
    net = ledger.assets / p.vault_usdg - 1
    total_h = sum(ledger.tier_usd_hours.values()) or 1.0
    return {
        "net_lender_yield_annualised": (1 + net) ** (1 / years) - 1 if years > 0 else 0.0,
        "net_return_total": net,
        "interest_usdg": ledger.interest,
        "bad_debt_usdg": ledger.bad_debt,
        "bad_debt_events": len(ledger.events),
        "worst_event": ledger.worst_event,
        "share_of_time": {k: v / total_h for k, v in ledger.tier_usd_hours.items()},
        "reallocations": ledger.reallocations,
        "final_assets_usdg": ledger.assets,
    }


def params_from(
    cfg_backtest: Any,
    cfg_policy: Any,
    cfg_vault: Any,
    weekday: float,
    weekend: float,
    margin: float,
    depth: Mapping[str, float],
    spread_mult: float = 1.0,
) -> SimParams:
    """Build SimParams from config sections and a tier pair."""
    base_weekend = cfg_backtest.apy(weekend)
    apy = {
        "weekday": base_weekend + spread_mult * (cfg_backtest.apy(weekday) - base_weekend),
        "weekend": base_weekend,
    }
    return SimParams(
        weekday=tier_spec("weekday", weekday),
        weekend=tier_spec("weekend", weekend),
        apy=apy,
        vault_usdg=cfg_backtest.vault_usdg,
        utilization=cfg_backtest.utilization,
        turnover=cfg_backtest.loan_turnover_per_session,
        ltv_low=cfg_backtest.borrower_ltv_share_of_lltv.low,
        ltv_high=cfg_backtest.borrower_ltv_share_of_lltv.high,
        grid=cfg_backtest.ltv_grid_points,
        session_hours=cfg_backtest.session_hours,
        safety_margin=margin,
        turnover_penalty=cfg_policy.turnover_penalty,
        min_rebalance_usd=cfg_policy.min_rebalance_usd,
        max_share_per_stock=cfg_vault.max_share_per_stock,
        depth_multiplier=cfg_vault.depth_multiplier,
        depth_usd=dict(depth),
    )
