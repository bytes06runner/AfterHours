"""Allocation policy (SPEC 7.5): a linear program over (stock, tier) supply amounts.

For stock s and tier t, with q_s the calibrated bad-case drop for the next closed period,
m the safety margin and b_t the liquidation-incentive allowance, tier t is allowed only if

    q_s + m <= 1 - LLTV_t - b_t        (the tier's cushion)

Variables x[s,t] (USDG supplied), with
    borrowed[s,t] <= x[s,t] <= cap[s,t]       (borrowed money cannot be pulled)
    x[s,t] <= borrowed[s,t]                    if tier t is not allowed for s
    sum_t x[s,t] <= max(stock_limit_s, sum_t borrowed[s,t])
    stock_limit_s = min(max_share * total, depth_multiplier * depth_s)
    sum x + idle = total, idle >= 0
Objective: maximise sum r[s,t] x[s,t] - turnover_penalty * sum |x - x_prev|, linearised
with x - x_prev = up - down, up, down >= 0. Solved with HiGHS through scipy.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linprog

TIERS = ("weekday", "weekend")


@dataclass(frozen=True)
class TierSpec:
    """A tier: its LLTV and the liquidation-incentive allowance b = LLTV * (LIF - 1)."""

    name: str
    lltv: float
    allowance: float

    @property
    def cushion(self) -> float:
        """Largest price drop a position at the LLTV can take without bad debt."""
        return 1 - self.lltv - self.allowance


@dataclass(frozen=True)
class StockState:
    """Inputs for one stock."""

    symbol: str
    bad_case_drop: float  # q_s, positive, e.g. 0.12 for a 12% drop
    depth_usd: float
    rate: dict[str, float]  # supply APY per tier
    borrowed: dict[str, float]
    cap: dict[str, float]
    prev: dict[str, float]


@dataclass
class Plan:
    """Solver output."""

    allocation: dict[tuple[str, str], float]
    idle: float
    allowed: dict[tuple[str, str], bool]
    reasons: dict[tuple[str, str], str]
    turnover: float
    execute: bool
    objective: float
    status: str
    stock_limits: dict[str, float] = field(default_factory=dict)


def allowed_tier(q: float, margin: float, tier: TierSpec) -> tuple[bool, str]:
    """Whether a tier is allowed for a bad-case drop, with a plain-English reason."""
    need = q + margin
    ok = need <= tier.cushion
    verb = "fits inside" if ok else "exceeds"
    return ok, (
        f"bad-case drop {q:.1%} plus margin {margin:.1%} = {need:.1%} {verb} the "
        f"{tier.name} tier cushion of {tier.cushion:.1%} (LLTV {tier.lltv:.1%})"
    )


def solve(
    stocks: Sequence[StockState],
    tiers: Sequence[TierSpec],
    *,
    total: float,
    safety_margin: float,
    turnover_penalty: float,
    min_rebalance_usd: float,
    max_share_per_stock: float,
    depth_multiplier: float,
) -> Plan:
    """Solve the allocation LP. Units are USDG."""
    keys = [(s.symbol, t.name) for s in stocks for t in tiers]
    n = len(keys)
    idx = {k: i for i, k in enumerate(keys)}
    allowed: dict[tuple[str, str], bool] = {}
    reasons: dict[tuple[str, str], str] = {}
    lower = np.zeros(n)
    upper = np.zeros(n)
    rate = np.zeros(n)
    prev = np.zeros(n)
    for s in stocks:
        for t in tiers:
            k = (s.symbol, t.name)
            ok, why = allowed_tier(s.bad_case_drop, safety_margin, t)
            allowed[k], reasons[k] = ok, why
            b = s.borrowed.get(t.name, 0.0)
            lower[idx[k]] = b
            upper[idx[k]] = max(b, s.cap.get(t.name, 0.0)) if ok else b
            rate[idx[k]] = s.rate.get(t.name, 0.0)
            prev[idx[k]] = s.prev.get(t.name, 0.0)

    # Variables: [x (n), up (n), down (n)].
    c = np.concatenate([-rate, np.full(n, turnover_penalty), np.full(n, turnover_penalty)])
    a_eq = np.hstack([np.eye(n), -np.eye(n), np.eye(n)])  # x - up + down = prev
    b_eq = prev.copy()
    rows, rhs = [], []
    limits: dict[str, float] = {}
    for s in stocks:
        row = np.zeros(3 * n)
        for t in tiers:
            row[idx[(s.symbol, t.name)]] = 1.0
        borrowed_total = sum(s.borrowed.get(t.name, 0.0) for t in tiers)
        limit = min(max_share_per_stock * total, depth_multiplier * s.depth_usd)
        limits[s.symbol] = max(limit, borrowed_total)
        rows.append(row)
        rhs.append(limits[s.symbol])
    total_row = np.concatenate([np.ones(n), np.zeros(2 * n)])
    rows.append(total_row)
    rhs.append(total)
    bounds = [(lower[i], upper[i]) for i in range(n)] + [(0, None)] * (2 * n)
    res = linprog(
        c,
        A_ub=np.array(rows),
        b_ub=np.array(rhs),
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not res.success:
        return Plan(
            {}, total, allowed, reasons, 0.0, False, 0.0, f"infeasible: {res.message}", limits
        )
    x = res.x[:n]
    alloc = {k: float(x[idx[k]]) for k in keys}
    turnover = float(np.abs(x - prev).sum())
    # Risk-driven moves (money above the borrowed floor in a tier that is no longer allowed)
    # always execute; other moves must clear the minimum rebalance.
    forced = any(not allowed[k] and prev[idx[k]] - lower[idx[k]] > 1e-6 for k in keys)
    return Plan(
        allocation=alloc,
        idle=float(total - x.sum()),
        allowed=allowed,
        reasons=reasons,
        turnover=turnover,
        execute=forced or turnover >= min_rebalance_usd,
        objective=float(-res.fun),
        status="optimal",
        stock_limits=limits,
    )


def tier_spec(name: str, lltv: float) -> TierSpec:
    """Tier from its LLTV with Morpho's liquidation incentive (verified in M1)."""
    lif = min(1.15, 1 / (1 - 0.3 * (1 - lltv)))
    return TierSpec(name, lltv, lltv * (lif - 1))
