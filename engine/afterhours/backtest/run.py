"""Backtest runner: strategies, tuning sweep, sensitivity and replay scenarios.

Writes `artifacts/backtest/`:
- `results.json`   all four strategies at the chosen settings, plus tuning and sensitivity
- `scenarios.json` replay scenarios picked from the data (largest gaps per segment)
- `replay/<id>.json` the price path and both vaults for each scenario
All labelled "historical stock prices, simulated vault".
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from afterhours.backtest.sim import (
    STRATEGIES,
    Row,
    SimParams,
    params_from,
    run_strategy,
    summarise,
)
from afterhours.config import AfterhoursConfig
from afterhours.deployments import load_discovered
from afterhours.features.dataset import SEGMENTS
from afterhours.features.gaps import code_version

log = logging.getLogger(__name__)
LABEL = "historical stock prices, simulated vault"


def forecasts(card: dict[str, Any], heldout: pd.DataFrame, alpha: float) -> tuple[str, pd.Series]:
    """The shipped calibrated forecast at `alpha` for each (ticker, session_prev)."""
    shipped = str(card["acceptance"]["shipped"])
    col = f"{shipped}_q{alpha:g}"
    series = heldout.set_index(["ticker", "session_prev"])[col]
    return shipped, series


def depth_by_symbol(cfg: AfterhoursConfig) -> dict[str, float]:
    """Per-stock depth from the discovered file (a present-day proxy used for all history)."""
    if cfg.backtest.depth_source == "none":
        return {}
    doc = load_discovered(cfg)
    return {
        s: float(v.get("depth_usd_at_max_slippage", 0.0))
        for s, v in doc.get("stock_tokens", {}).items()
    }


def simulate_all(p: SimParams, periods: pd.DataFrame, fc: Callable[[Any], float]) -> dict[str, Any]:
    """Every strategy under one parameter set."""
    years = (
        pd.to_datetime(periods["session_next"].max())
        - pd.to_datetime(periods["session_prev"].min())
    ).days / 365.25
    return {s: summarise(run_strategy(s, p, periods, fc), p, years) for s in STRATEGIES}


def select_scenarios(periods: pd.DataFrame, per_segment: int) -> list[dict[str, Any]]:
    """Largest absolute gaps per segment among the selected tokens (from data, not typed in)."""
    out = []
    for seg in SEGMENTS:
        part = periods[periods["segment"] == seg].copy()
        part["abs_g"] = part["g"].abs()
        for rec in part.nlargest(per_segment, "abs_g").to_dict("records"):
            r = Row(rec)
            out.append(
                {
                    "id": f"{r.ticker}-{r.session_prev}-{seg}",
                    "ticker": r.ticker,
                    "session_prev": str(r.session_prev),
                    "session_next": str(r.session_next),
                    "segment": seg,
                    "g": float(r.g),
                    "hours_closed": float(r.hours_closed),
                }
            )
    return out


def replay_series(
    scenario: dict[str, Any],
    periods: pd.DataFrame,
    prices: pd.DataFrame,
    p: SimParams,
    fc: Callable[[Any], float],
    window: int,
) -> dict[str, Any]:
    """Price path and both vaults (ordinary = always weekday, Afterhours) around one event."""
    tick = (
        periods[periods["ticker"] == scenario["ticker"]]
        .sort_values("session_prev")
        .reset_index(drop=True)
    )
    idx = int(tick.index[tick["session_prev"].astype(str) == scenario["session_prev"]][0])
    lo, hi = max(0, idx - window), min(len(tick), idx + window + 1)
    local = tick.iloc[lo:hi]
    vaults = {}
    for strategy in ("always_weekday", "afterhours"):
        single = SimParams(**{**p.__dict__, "max_share_per_stock": 1.0})
        ledger = run_strategy(strategy, single, local, fc)
        vaults[strategy] = {
            "bad_debt_usdg": ledger.bad_debt,
            "interest_usdg": ledger.interest,
            "final_assets_usdg": ledger.assets,
            "events": ledger.events,
        }
    px = prices.loc[
        (prices.index >= local["session_prev"].min())
        & (prices.index <= local["session_next"].max())
    ]
    path = [
        {"date": str(d), "open": float(r.open), "close": float(r.close)} for d, r in px.iterrows()
    ]
    steps = [  # one entry per closed period in the window
        {
            "session_prev": str(r.session_prev),
            "session_next": str(r.session_next),
            "g": float(r.g),
            "segment": r.segment,
            "bad_case_drop": fc(r),
        }
        for r in (Row(rec) for rec in local.to_dict("records"))
    ]
    return {
        **scenario,
        "label": LABEL,
        "price_path": path,
        "periods": steps,
        "vaults": vaults,
        "vault_usdg": p.vault_usdg,
    }


def run(
    cfg: AfterhoursConfig,
    data: pd.DataFrame,
    heldout: pd.DataFrame,
    card: dict[str, Any],
    prices: dict[str, pd.DataFrame],
    selected: list[str],
) -> dict[str, Any]:
    """Run the backtest and write artifacts."""
    b = cfg.backtest
    alpha = cfg.model.target_alpha
    shipped, fseries = forecasts(card, heldout, alpha)
    fmap = fseries.to_dict()
    periods = data[data["ticker"].isin(selected)]
    keys = set(fmap)
    periods = periods[
        [(t, sp) in keys for t, sp in zip(periods["ticker"], periods["session_prev"], strict=True)]
    ]
    periods = periods.sort_values(["session_prev", "ticker"]).reset_index(drop=True)

    def fc(row: Any) -> float:
        return max(0.0, -float(fmap[(row.ticker, row.session_prev)]))

    depth = depth_by_symbol(cfg)
    tuning: list[dict[str, Any]] = []
    for wd, we in b.tier_pairs_to_tune:
        for m in b.safety_margins_to_tune:
            p = params_from(b, cfg.policy, cfg.vault, wd, we, m, depth)
            res = simulate_all(p, periods, fc)
            tuning.append(
                {"weekday_lltv": wd, "weekend_lltv": we, "safety_margin": m, "results": res}
            )
            log.info(
                "tuned %s/%s m=%s afterhours=%.4f weekday=%.4f",
                wd,
                we,
                m,
                res["afterhours"]["net_lender_yield_annualised"],
                res["always_weekday"]["net_lender_yield_annualised"],
            )
    best = max(tuning, key=lambda r: r["results"]["afterhours"]["net_lender_yield_annualised"])
    chosen: tuple[float, float, float] = (
        float(best["weekday_lltv"]),
        float(best["weekend_lltv"]),
        float(best["safety_margin"]),
    )
    sensitivity = []
    for mult in b.rate_spread_multipliers:
        p = params_from(b, cfg.policy, cfg.vault, chosen[0], chosen[1], chosen[2], depth, mult)
        sensitivity.append(
            {"rate_spread_multiplier": mult, "apy": p.apy, "results": simulate_all(p, periods, fc)}
        )
    p = params_from(b, cfg.policy, cfg.vault, *chosen, depth)
    main = simulate_all(p, periods, fc)
    scenarios = select_scenarios(periods, b.replay.per_segment)
    out_dir = cfg.path(cfg.paths.artifacts_dir) / "backtest"
    (out_dir / "replay").mkdir(parents=True, exist_ok=True)
    for sc in scenarios:
        doc = replay_series(sc, periods, prices[sc["ticker"]], p, fc, b.replay.window_sessions)
        (out_dir / "replay" / f"{sc['id']}.json").write_text(
            json.dumps(doc, indent=2, default=str) + "\n"
        )
    results = {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_version": code_version(),
        "label": LABEL,
        "forecast": {
            "shipped": shipped,
            "alpha": alpha,
            "model_version": card["production"]["model_version"],
        },
        "selected": selected,
        "period": {
            "first": str(periods["session_prev"].min()),
            "last": str(periods["session_next"].max()),
            "closed_periods": int(periods["session_prev"].nunique()),
            "rows": len(periods),
        },
        "assumptions": {
            **b.model_dump(exclude={"tier_pairs_to_tune", "safety_margins_to_tune", "replay"}),
            "depth_usd_by_stock": {s: depth.get(s) for s in selected},
            "note": "rates, utilisation and borrower behaviour are assumptions; see config",
        },
        "chosen": {
            "weekday_lltv": chosen[0],
            "weekend_lltv": chosen[1],
            "safety_margin": chosen[2],
            "rule": "highest Afterhours net lender yield across the tuning grid",
        },
        "strategies": main,
        "tuning": tuning,
        "sensitivity": sensitivity,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    (out_dir / "scenarios.json").write_text(
        json.dumps({"label": LABEL, "scenarios": scenarios}, indent=2) + "\n"
    )
    return results


def load_inputs(cfg: AfterhoursConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Held-out predictions and the report card written by `afterhours model`."""
    card_path: Path = cfg.path(cfg.paths.artifacts_dir) / "model" / "report_card.json"
    heldout = pd.read_parquet(cfg.path(cfg.data.cache_dir) / "heldout_predictions.parquet")
    return heldout, json.loads(card_path.read_text())
