"""Option A: dynamic Afterhours against a no-hindsight fixed map, tuned and tested out of sample.

The decision rule and the grid were written to PROGRESS.md before this ran. Everything here is
historical stock prices, simulated vault. Writes `artifacts/backtest/option_a.json`.
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from afterhours.backtest.run import (
    LABEL,
    depth_by_symbol,
    forecasts,
    load_inputs,
    lookahead_risk,
)
from afterhours.backtest.sim import SimParams, params_from, run_strategy, summarise
from afterhours.config import AfterhoursConfig
from afterhours.deployments import load_discovered
from afterhours.features.gaps import code_version
from afterhours.policy.lp import tier_spec

log = logging.getLogger(__name__)

# Worker state (filled once per process by _init; fork start method shares it cheaply).
_W: dict[str, Any] = {}


def params(cfg: AfterhoursConfig, tier_set: list[str], fraction: float | None) -> SimParams:
    oa = cfg.backtest.option_a
    base = params_from(
        cfg.backtest,
        cfg.policy,
        cfg.vault,
        oa.tiers["weekday"],
        oa.tiers["weekend"],
        0.0,
        depth_by_symbol(cfg),
    )
    apy = dict(base.apy)
    middle = None
    if "middle" in tier_set:
        middle = tier_spec("middle", oa.tiers["middle"])
        apy["middle"] = cfg.backtest.apy(oa.tiers["middle"])
    return replace(base, middle=middle, margin_fraction=fraction, apy=apy)


def fixed_map_ratings(
    cfg: AfterhoursConfig, data: pd.DataFrame, tickers: list[str]
) -> dict[tuple[str, int], float]:
    """Each stock's worst `quantile` closed-period drop over the window before each January."""
    fm = cfg.backtest.option_a.fixed_map
    d = data[data["ticker"].isin(tickers)][["ticker", "session_prev", "g"]].copy()
    d["day"] = pd.to_datetime(d["session_prev"]).dt.date
    out: dict[tuple[str, int], float] = {}
    first, last = cfg.backtest.option_a.tuning_years[0], cfg.backtest.option_a.evaluation_years[1]
    for year in range(first, last + 1):
        end = date(year, 1, 1)
        start = end - timedelta(days=fm.window_days)
        win = d[(d["day"] >= start) & (d["day"] < end)]
        for t, grp in win.groupby("ticker"):
            if len(grp) >= fm.min_observations:
                out[(str(t), year)] = max(0.0, -float(np.quantile(grp["g"], fm.quantile)))
    return out


def _init(state: dict[str, Any]) -> None:
    _W.update(state)


def _run(job: dict[str, Any]) -> dict[str, Any]:
    cfg: AfterhoursConfig = _W["cfg"]
    per: pd.DataFrame = _W["periods"][job["universe"]][job["span"]]
    p = params(cfg, job["tier_set"], job.get("fraction"))
    kind = job["kind"]
    if kind == "afterhours":
        table = _W["tables"][job["universe"]][job["lookahead"]]
        led = run_strategy("afterhours", p, per, lambda r: table[(r.ticker, r.session_prev)])
    elif kind == "fixed_map":
        ratings = _W["ratings"][job["universe"]]
        # Missing history rates as "only the weekend tier": a drop just inside its limit.
        floor = p.weekend.cushion * (1 - (job["fraction"] or 0.0))
        led = run_strategy(
            "afterhours",
            p,
            per,
            lambda r: min(ratings.get((r.ticker, int(str(r.session_prev)[:4])), floor), floor),
        )
    else:
        led = run_strategy(f"blend:{job['w']}", p, per, lambda r: 0.0)
    days = (pd.Timestamp(per["session_prev"].max()) - pd.Timestamp(per["session_prev"].min())).days
    out = summarise(led, p, days / 365.25)
    return {**job, "result": out}


def _pick(rows: list[dict[str, Any]], cap: float) -> dict[str, Any]:
    """Highest interest with worst event <= cap; else the smallest worst event."""

    def worst(r: dict[str, Any]) -> float:
        return float((r["result"]["worst_event"] or {}).get("share_of_vault", 0.0))

    ok = [r for r in rows if worst(r) <= cap]
    if ok:
        return max(ok, key=lambda r: r["result"]["interest_usdg"])
    return min(rows, key=worst)


def run(cfg: AfterhoursConfig, data: pd.DataFrame, n_jobs: int = 0) -> dict[str, Any]:
    oa = cfg.backtest.option_a
    heldout, card = load_inputs(cfg)
    _, fseries = forecasts(card, heldout, cfg.model.target_alpha)
    fmap = fseries.to_dict()
    results = json.loads(
        (cfg.path(cfg.paths.artifacts_dir) / "backtest" / "results.json").read_text()
    )
    universes = {
        "vault": list(results["selected"]),
        "stock_tokens": sorted(load_discovered(cfg, "fork")["stock_tokens"]),
    }
    periods: dict[str, dict[str, pd.DataFrame]] = {}
    tables: dict[str, dict[int, dict[tuple[str, Any], float]]] = {}
    ratings: dict[str, dict[tuple[str, int], float]] = {}
    for u in oa.universes:
        tick = universes[u]
        per = data[data["ticker"].isin(tick)]
        per = per[[(t, s) in fmap for t, s in zip(per["ticker"], per["session_prev"], strict=True)]]
        per = per.sort_values(["session_prev", "ticker"]).reset_index(drop=True)
        per = per.assign(
            forecast_drop=[
                max(0.0, -float(fmap[(t, s)]))
                for t, s in zip(per["ticker"], per["session_prev"], strict=True)
            ]
        )
        year = pd.to_datetime(per["session_prev"]).dt.year
        periods[u] = {
            "tuning": per[(year >= oa.tuning_years[0]) & (year <= oa.tuning_years[1])].reset_index(
                drop=True
            ),
            "evaluation": per[
                (year >= oa.evaluation_years[0]) & (year <= oa.evaluation_years[1])
            ].reset_index(drop=True),
        }
        # Lookahead tables use ex-ante forecasts only, computed once over the whole span.
        tables[u] = {
            L: lookahead_risk(per, "forecast_drop", L, ex_ante=True) for L in oa.lookaheads
        }
        ratings[u] = fixed_map_ratings(cfg, data, tick)
    blends = [round(x, 4) for x in np.arange(0, 1 + 1e-9, oa.blend_step)]
    jobs: list[dict[str, Any]] = []
    for u in oa.universes:
        for span in ("tuning", "evaluation"):
            for ts in oa.tier_sets:
                for f in oa.margin_fractions:
                    jobs.append(
                        {
                            "universe": u,
                            "span": span,
                            "kind": "fixed_map",
                            "tier_set": ts,
                            "fraction": f,
                        }
                    )
                    for look in oa.lookaheads:
                        jobs.append(
                            {
                                "universe": u,
                                "span": span,
                                "kind": "afterhours",
                                "tier_set": ts,
                                "fraction": f,
                                "lookahead": look,
                            }
                        )
            for w in blends:
                jobs.append(
                    {
                        "universe": u,
                        "span": span,
                        "kind": "blend",
                        "tier_set": ["weekday", "weekend"],
                        "w": w,
                    }
                )
    state = {"cfg": cfg, "periods": periods, "tables": tables, "ratings": ratings}
    ctx = mp.get_context("fork")
    procs = n_jobs or max(1, mp.cpu_count() - 1)
    log.info("option A: %d runs on %d processes", len(jobs), procs)
    with ctx.Pool(procs, initializer=_init, initargs=(state,)) as pool:
        done = pool.map(_run, jobs, chunksize=1)

    cap = cfg.backtest.max_worst_event_share
    report: dict[str, Any] = {
        "label": LABEL,
        "code_version": code_version(),
        "rule": "tune on tuning_years, evaluate once on evaluation_years; dynamic wins only if it "
        "has less bad debt than the fixed map at equal or higher interest (PROGRESS.md)",
        "config": oa.model_dump(),
        "universes": {},
    }
    for u in oa.universes:
        rows = [r for r in done if r["universe"] == u]
        tune = [r for r in rows if r["span"] == "tuning"]
        chosen = {
            k: _pick([r for r in tune if r["kind"] == k], cap) for k in ("afterhours", "fixed_map")
        }

        def same(a: dict[str, Any], b: dict[str, Any]) -> bool:
            keys = ("kind", "tier_set", "fraction", "lookahead", "w")
            return all(a.get(k) == b.get(k) for k in keys)

        evaluation = {
            k: next(r for r in rows if r["span"] == "evaluation" and same(r, c))
            for k, c in chosen.items()
        }
        dyn, fix = evaluation["afterhours"]["result"], evaluation["fixed_map"]["result"]
        wins = (
            dyn["bad_debt_usdg"] < fix["bad_debt_usdg"]
            and dyn["interest_usdg"] >= fix["interest_usdg"]
        )
        report["universes"][u] = {
            "tickers": universes[u],
            "periods": {
                s: {
                    "first": str(periods[u][s]["session_prev"].min()),
                    "last": str(periods[u][s]["session_prev"].max()),
                    "closed_periods": int(periods[u][s]["session_prev"].nunique()),
                }
                for s in ("tuning", "evaluation")
            },
            "chosen_on_tuning": {
                k: {x: v for x, v in c.items() if x != "result"} | {"tuning_result": c["result"]}
                for k, c in chosen.items()
            },
            "evaluation": {k: v["result"] for k, v in evaluation.items()},
            "blends": {
                s: [
                    {"w": r["w"], **r["result"]}
                    for r in sorted(
                        (r for r in rows if r["kind"] == "blend" and r["span"] == s),
                        key=lambda r: r["w"],
                    )
                ]
                for s in ("tuning", "evaluation")
            },
            "grid": {
                s: [
                    {x: v for x, v in r.items() if x not in ("result", "universe", "span")}
                    | {
                        "interest_usdg": r["result"]["interest_usdg"],
                        "bad_debt_usdg": r["result"]["bad_debt_usdg"],
                        "worst_event_share": (r["result"]["worst_event"] or {}).get(
                            "share_of_vault", 0.0
                        ),
                        "net_lender_yield_annualised": r["result"]["net_lender_yield_annualised"],
                    }
                    for r in rows
                    if r["span"] == s and r["kind"] != "blend"
                ]
                for s in ("tuning", "evaluation")
            },
            "decision": {"dynamic_wins": wins, "dynamic": dyn, "fixed_map": fix},
        }
    return report


def write(cfg: AfterhoursConfig, data: pd.DataFrame, n_jobs: int = 0) -> str:
    report = run(cfg, data, n_jobs)
    out = cfg.path(cfg.paths.artifacts_dir) / "backtest" / "option_a.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return str(out)
