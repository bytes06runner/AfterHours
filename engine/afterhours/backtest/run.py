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

import numpy as np
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


def lookahead_risk(
    periods: pd.DataFrame, drop_col: str, horizon: int, *, ex_ante: bool
) -> dict[Any, float]:
    """Worst drop over each ticker's next `horizon` closed periods, keyed by (ticker, session_prev).

    With `ex_ante`, a future period's calibrated drop is rescaled from its own EWMA volatility
    to the volatility known today (sigma_k / sigma_j), so only information available at the
    decision close is used. The segment (earnings dates are scheduled) and closed hours of
    future periods are known in advance.
    """
    out: dict[Any, float] = {}
    for ticker, unsorted in periods.groupby("ticker", sort=False):
        part = unsorted.sort_values("session_prev")
        drops = part[drop_col].to_numpy(dtype=float)
        sigma = part["ewma_sigma"].to_numpy(dtype=float)
        keys = list(zip([ticker] * len(part), part["session_prev"], strict=True))
        for k in range(len(part)):
            window = slice(k, min(k + horizon, len(part)))
            d = drops[window]
            if ex_ante:
                ratio = sigma[k] / sigma[window]
                d = d * np.where(np.isfinite(ratio) & (ratio > 0), ratio, 1.0)
            out[keys[k]] = float(np.nanmax(d)) if d.size else 0.0
    return out


def simulate_all(p: SimParams, periods: pd.DataFrame, horizon: int) -> dict[str, Any]:
    """Every strategy under one parameter set and lookahead."""
    ah = lookahead_risk(periods, "forecast_drop", horizon, ex_ante=True)
    pf = lookahead_risk(periods, "realised_drop", horizon, ex_ante=False)

    def risk_for(table: dict[Any, float]) -> Callable[[Any], float]:
        return lambda row: table[(row.ticker, row.session_prev)]

    years = (
        pd.to_datetime(periods["session_next"].max())
        - pd.to_datetime(periods["session_prev"].min())
    ).days / 365.25
    fns = {
        "always_weekday": risk_for(ah),
        "always_weekend": risk_for(ah),
        "afterhours": risk_for(ah),
        "perfect_foresight": risk_for(pf),
    }
    return {s: summarise(run_strategy(s, p, periods, fns[s]), p, years) for s in STRATEGIES}


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
    forecast: Callable[[Any], float] | None = None,
    describe: Callable[[Any], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Price path and both vaults (ordinary = always weekday, Afterhours) around one event.

    `fc` is what the strategy acts on; `forecast` (default `fc`) is the bad case shown for each
    night and `describe` adds the policy's view of each night."""
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
        series: list[dict[str, Any]] = []
        ledger = run_strategy(strategy, single, local, fc, record=series)
        vaults[strategy] = {
            "bad_debt_usdg": ledger.bad_debt,
            "interest_usdg": ledger.interest,
            "final_assets_usdg": ledger.assets,
            "events": ledger.events,
            "series": series,
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
            "bad_case_drop": (forecast or fc)(r),
            **(describe(r) if describe else {}),
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

    periods = periods.assign(
        forecast_drop=[
            max(0.0, -float(fmap[(t, sp)]))
            for t, sp in zip(periods["ticker"], periods["session_prev"], strict=True)
        ],
        realised_drop=np.maximum(0.0, -periods["g"].to_numpy(dtype=float)),
    )

    depth = depth_by_symbol(cfg)
    tuning: list[dict[str, Any]] = []
    for wd, we in b.tier_pairs_to_tune:
        for m in b.safety_margins_to_tune:
            for h in b.lookaheads_to_tune:
                p = params_from(b, cfg.policy, cfg.vault, wd, we, m, depth)
                res = simulate_all(p, periods, h)
                tuning.append(
                    {
                        "weekday_lltv": wd,
                        "weekend_lltv": we,
                        "safety_margin": m,
                        "lookahead": h,
                        "results": res,
                    }
                )
                log.info(
                    "tuned %s/%s m=%s h=%s afterhours=%.4f weekday=%.4f bad=%.0f",
                    wd,
                    we,
                    m,
                    h,
                    res["afterhours"]["net_lender_yield_annualised"],
                    res["always_weekday"]["net_lender_yield_annualised"],
                    res["afterhours"]["bad_debt_usdg"],
                )

    def worst_share(r: dict[str, Any]) -> float:
        return float(r["results"]["afterhours"]["worst_event"].get("share_of_vault", 0.0))

    eligible = [r for r in tuning if worst_share(r) <= b.max_worst_event_share]
    best = (
        max(eligible, key=lambda r: r["results"]["afterhours"]["net_lender_yield_annualised"])
        if eligible
        else min(tuning, key=worst_share)
    )
    chosen: tuple[float, float, float] = (
        float(best["weekday_lltv"]),
        float(best["weekend_lltv"]),
        float(best["safety_margin"]),
    )
    horizon = int(best["lookahead"])
    sensitivity: list[dict[str, Any]] = []
    for mult in b.rate_spread_multipliers:
        p = params_from(b, cfg.policy, cfg.vault, *chosen, depth, mult)
        sensitivity.append(
            {
                "kind": "rate_spread",
                "value": mult,
                "apy": p.apy,
                "results": simulate_all(p, periods, horizon),
            }
        )
    for turnover in b.turnover_sensitivity:
        p = params_from(b, cfg.policy, cfg.vault, *chosen, depth)
        p = SimParams(**{**p.__dict__, "turnover": turnover})
        sensitivity.append(
            {
                "kind": "loan_turnover",
                "value": turnover,
                "results": simulate_all(p, periods, horizon),
            }
        )
    p = params_from(b, cfg.policy, cfg.vault, *chosen, depth)
    main = simulate_all(p, periods, horizon)
    risk_table = lookahead_risk(periods, "forecast_drop", horizon, ex_ante=True)

    def fc(row: Any) -> float:
        return risk_table[(row.ticker, row.session_prev)]

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
            "lookahead_closed_periods": horizon,
            "rule": (
                "highest Afterhours net lender yield among settings whose worst single event "
                f"loses at most {b.max_worst_event_share:.2%} of the vault"
            ),
            "eligible_settings": len(eligible),
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


def write_replays(
    cfg: AfterhoursConfig,
    data: pd.DataFrame,
    heldout: pd.DataFrame,
    card: dict[str, Any],
    prices: dict[str, pd.DataFrame],
    selected: list[str],
) -> list[str]:
    """Regenerate scenarios and replays for the shipped policy (option B, config `policy`)."""
    from afterhours.backtest.option_a import fixed_map_ratings, params
    from afterhours.backtest.option_b import b_risk
    from afterhours.policy.option_b import decide

    b = cfg.backtest
    pol = cfg.policy
    out_dir = cfg.path(cfg.paths.artifacts_dir) / "backtest"
    _, fseries = forecasts(card, heldout, cfg.model.target_alpha)
    fmap = fseries.to_dict()
    periods = data[data["ticker"].isin(selected)]
    periods = periods[
        [(t, sp) in fmap for t, sp in zip(periods["ticker"], periods["session_prev"], strict=True)]
    ]
    periods = periods.sort_values(["session_prev", "ticker"]).reset_index(drop=True)
    periods = periods.assign(
        forecast_drop=[
            max(0.0, -float(fmap[(t, sp)]))
            for t, sp in zip(periods["ticker"], periods["session_prev"], strict=True)
        ],
        realised_drop=np.maximum(0.0, -periods["g"].to_numpy(dtype=float)),
    )
    p = params(cfg, b.option_b.tier_set, pol.map_fraction)
    table = lookahead_risk(periods, "forecast_drop", pol.lookahead_closed_periods, ex_ante=True)
    ratings = fixed_map_ratings(cfg, data, selected)
    fc = b_risk(p, ratings, table, pol.map_fraction, pol.pullback_fraction)

    def forecast(row: Any) -> float:
        return table[(row.ticker, row.session_prev)]

    def describe(row: Any) -> dict[str, Any]:
        year = int(str(row.session_prev)[:4])
        d = decide(
            row.ticker,
            ratings.get((row.ticker, year)),
            year,
            forecast(row),
            p.tiers,
            pol.map_fraction,
            pol.pullback_fraction,
        )
        return {
            "rating": d.rating,
            "mapped_tier": d.mapped_tier,
            "pulled": d.pulled,
            "pull_limit": d.pull_limit,
        }

    scenarios = select_scenarios(periods, b.replay.per_segment)
    (out_dir / "replay").mkdir(parents=True, exist_ok=True)
    written = []
    for sc in scenarios:
        doc = replay_series(
            sc,
            periods,
            prices[sc["ticker"]],
            p,
            fc,
            b.replay.window_sessions,
            forecast=forecast,
            describe=describe,
        )
        doc["settings"] = {
            "policy": "option_b",
            "map_fraction": pol.map_fraction,
            "pullback_fraction": pol.pullback_fraction,
            "lookahead_closed_periods": pol.lookahead_closed_periods,
        }
        doc["tiers"] = {t.name: {"lltv": t.lltv, "cushion": t.cushion} for t in p.tiers}
        path = out_dir / "replay" / f"{sc['id']}.json"
        path.write_text(json.dumps(doc, indent=2, default=str) + "\n")
        written.append(str(path))
    (out_dir / "scenarios.json").write_text(
        json.dumps({"label": LABEL, "scenarios": scenarios}, indent=2) + "\n"
    )
    return written


def load_inputs(cfg: AfterhoursConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Held-out predictions and the report card written by `afterhours model`."""
    card_path: Path = cfg.path(cfg.paths.artifacts_dir) / "model" / "report_card.json"
    heldout = pd.read_parquet(cfg.path(cfg.data.cache_dir) / "heldout_predictions.parquet")
    return heldout, json.loads(card_path.read_text())
