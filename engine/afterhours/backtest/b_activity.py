"""How often option B actually pulled money on the held-out years (a measurement, not a change).

Replays B's evaluated run (`artifacts/backtest/option_b.json`, same settings, same simulator)
and records, for every closed period, which stocks the pullback fired for while they held
unborrowed vault money, and how much USDG left them.
Writes `artifacts/backtest/option_b_activity.json`.
Historical stock prices, simulated vault.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import pandas as pd

from afterhours.backtest import sim
from afterhours.backtest.option_a import fixed_map_ratings, params
from afterhours.backtest.option_b import b_risk
from afterhours.backtest.run import LABEL, forecasts, load_inputs, lookahead_risk
from afterhours.config import AfterhoursConfig
from afterhours.policy.option_b import PULLED

DUST_USDG = 1.0  # below this a "pull" moves nothing worth counting


def measure(cfg: AfterhoursConfig, data: pd.DataFrame, universe: str) -> dict[str, Any]:
    art = cfg.path(cfg.paths.artifacts_dir) / "backtest"
    a_doc = json.loads((art / "option_a.json").read_text())
    b_doc = json.loads((art / "option_b.json").read_text())
    oa = cfg.backtest.option_a
    tick = a_doc["universes"][universe]["tickers"]
    chosen = b_doc["universes"][universe]["chosen"]
    heldout, card = load_inputs(cfg)
    _, fseries = forecasts(card, heldout, cfg.model.target_alpha)
    fmap = fseries.to_dict()
    per = data[data["ticker"].isin(tick)]
    per = per[[(t, s) in fmap for t, s in zip(per["ticker"], per["session_prev"], strict=True)]]
    per = per.sort_values(["session_prev", "ticker"]).reset_index(drop=True)
    per = per.assign(
        forecast_drop=[
            max(0.0, -float(fmap[(t, s)]))
            for t, s in zip(per["ticker"], per["session_prev"], strict=True)
        ]
    )
    table = lookahead_risk(per, "forecast_drop", chosen["lookahead"], ex_ante=True)
    year = pd.to_datetime(per["session_prev"]).dt.year
    ev = per[(year >= oa.evaluation_years[0]) & (year <= oa.evaluation_years[1])].reset_index(
        drop=True
    )
    p = params(cfg, cfg.backtest.option_b.tier_set, chosen["map_fraction"])
    risk = b_risk(
        p,
        fixed_map_ratings(cfg, data, tick),
        table,
        chosen["map_fraction"],
        chosen["pullback_fraction"],
    )

    events: list[dict[str, Any]] = []
    sessions = iter(sorted(ev["session_prev"].unique()))
    original = sim._target

    def spy(strategy: str, p_: Any, stocks: Any, ledger: Any, q: Any) -> Any:
        out = original(strategy, p_, stocks, ledger, q)
        session = str(next(sessions))
        for s in stocks:
            if q[s] != PULLED:
                continue
            before = sum(v for (x, _t), v in ledger.supply.items() if x == s)
            lent = sum(v for (x, _t), v in ledger.borrowed.items() if x == s)
            after = sum(v for (x, _t), v in out[0].items() if x == s)
            moved = max(0.0, before - after)
            if before - lent > DUST_USDG and moved > DUST_USDG:
                events.append({"session_prev": session, "symbol": s, "usdg_moved": moved})
        return out

    sim._target = spy  # type: ignore[assignment]  # instrumentation only; restored below
    try:
        led = sim.run_strategy("afterhours", p, ev, risk)
    finally:
        sim._target = original
    expected = b_doc["universes"][universe]["evaluation"]["bad_debt_usdg"]
    if abs(led.bad_debt - expected) > 1e-6 * max(1.0, expected):
        raise RuntimeError("replay does not reproduce option_b.json; refusing to report")

    nights: dict[int, set[str]] = defaultdict(set)
    usd: dict[int, float] = defaultdict(float)
    by_symbol: dict[str, int] = defaultdict(int)
    for e in events:
        y = int(e["session_prev"][:4])
        nights[y].add(e["session_prev"])
        usd[y] += e["usdg_moved"]
        by_symbol[e["symbol"]] += 1
    years = list(range(oa.evaluation_years[0], oa.evaluation_years[1] + 1))
    all_nights = {e["session_prev"] for e in events}
    return {
        "universe": universe,
        "stocks": len(tick),
        "settings": chosen,
        "period": {"first": str(ev["session_prev"].min()), "last": str(ev["session_prev"].max())},
        "reproduces_bad_debt_usdg": led.bad_debt,
        "per_year": {y: {"nights": len(nights[y]), "usdg_moved": usd[y]} for y in years},
        "total": {
            "nights": len(all_nights),
            "stock_nights": len(events),
            "usdg_moved": sum(e["usdg_moved"] for e in events),
        },
        "by_symbol": dict(sorted(by_symbol.items())),
        "note": (
            "a night counts when the pullback fired for a stock that held unborrowed vault money "
            "and at least 1 USDG left it; the partial 2026 year runs to the period's last night"
        ),
        "events": events,
    }


def write(cfg: AfterhoursConfig, data: pd.DataFrame) -> str:
    doc = {
        "label": LABEL,
        "universes": {u: measure(cfg, data, u) for u in cfg.backtest.option_a.universes},
    }
    out = cfg.path(cfg.paths.artifacts_dir) / "backtest" / "option_b_activity.json"
    out.write_text(json.dumps(doc, indent=2, default=str) + "\n")
    return str(out)
