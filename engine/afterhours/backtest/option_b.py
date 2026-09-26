"""Option B: the no-hindsight fixed map over three tiers, plus a pullback on risky nights.

Pre-registered in PROGRESS.md (commit 8f31b8e) before this ran; this is the second evaluation on
the 2022 to 2026 held-out window. Historical stock prices, simulated vault. Writes
`artifacts/backtest/option_b.json`.
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
from typing import Any

import pandas as pd

from afterhours.backtest.option_a import fixed_map_ratings, params
from afterhours.backtest.run import LABEL, forecasts, load_inputs, lookahead_risk
from afterhours.backtest.sim import SimParams, run_strategy, summarise
from afterhours.config import AfterhoursConfig
from afterhours.features.gaps import code_version

log = logging.getLogger(__name__)
_W: dict[str, Any] = {}
PULLED = 1.0  # a bad case no tier admits: the stock's unborrowed money goes idle


def b_risk(
    p: SimParams,
    ratings: dict[tuple[str, int], float],
    table: dict[tuple[str, Any], float],
    map_fraction: float,
    pullback_fraction: float,
) -> Any:
    """The drop B hands the LP for one stock and night (the LP's margin is the map fraction)."""
    floor = min(t.cushion for t in p.tiers if t.name == "weekend") * (1 - map_fraction)
    pull_limit = max(t.cushion for t in p.tiers) * (1 - pullback_fraction)

    def risk(r: Any) -> float:
        if table[(r.ticker, r.session_prev)] > pull_limit:
            return PULLED
        rating = ratings.get((r.ticker, int(str(r.session_prev)[:4])), floor)
        return min(rating, floor)

    return risk


def _init(state: dict[str, Any]) -> None:
    _W.update(state)


def _run(job: dict[str, Any]) -> dict[str, Any]:
    cfg: AfterhoursConfig = _W["cfg"]
    per: pd.DataFrame = _W["periods"][job["universe"]][job["span"]]
    p = params(cfg, cfg.backtest.option_b.tier_set, job["map_fraction"])
    risk = b_risk(
        p,
        _W["ratings"][job["universe"]],
        _W["tables"][job["universe"]][job["lookahead"]],
        job["map_fraction"],
        job["pullback_fraction"],
    )
    led = run_strategy("afterhours", p, per, risk)
    days = (pd.Timestamp(per["session_prev"].max()) - pd.Timestamp(per["session_prev"].min())).days
    return {**job, "result": summarise(led, p, days / 365.25)}


def worst(result: dict[str, Any]) -> float:
    return float((result.get("worst_event") or {}).get("share_of_vault", 0.0))


def pick_by_yield(rows: list[dict[str, Any]], cap: float) -> dict[str, Any]:
    """The M4 rule: highest net lender yield with worst event <= cap; else the smallest worst."""
    ok = [r for r in rows if worst(r["result"]) <= cap]
    if ok:
        return max(ok, key=lambda r: r["result"]["net_lender_yield_annualised"])
    return min(rows, key=lambda r: worst(r["result"]))


def run(cfg: AfterhoursConfig, data: pd.DataFrame, n_jobs: int = 0) -> dict[str, Any]:
    oa, ob = cfg.backtest.option_a, cfg.backtest.option_b
    a_doc = json.loads(
        (cfg.path(cfg.paths.artifacts_dir) / "backtest" / "option_a.json").read_text()
    )
    heldout, card = load_inputs(cfg)
    _, fseries = forecasts(card, heldout, cfg.model.target_alpha)
    fmap = fseries.to_dict()
    periods: dict[str, dict[str, pd.DataFrame]] = {}
    tables: dict[str, dict[int, Any]] = {}
    ratings: dict[str, dict[tuple[str, int], float]] = {}
    for u in oa.universes:
        tick = a_doc["universes"][u]["tickers"]
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
        tables[u] = {
            look: lookahead_risk(per, "forecast_drop", look, ex_ante=True) for look in ob.lookaheads
        }
        ratings[u] = fixed_map_ratings(cfg, data, tick)
    jobs = [
        {
            "universe": u,
            "span": span,
            "map_fraction": fm,
            "pullback_fraction": fp,
            "lookahead": look,
        }
        for u in oa.universes
        for span in ("tuning", "evaluation")
        for fm in ob.map_fractions
        for fp in ob.pullback_fractions
        for look in ob.lookaheads
    ]
    state = {"cfg": cfg, "periods": periods, "tables": tables, "ratings": ratings}
    procs = n_jobs or max(1, mp.cpu_count() - 1)
    log.info("option B: %d runs on %d processes", len(jobs), procs)
    with mp.get_context("fork").Pool(procs, initializer=_init, initargs=(state,)) as pool:
        done = pool.map(_run, jobs, chunksize=1)

    cap = cfg.backtest.max_worst_event_share
    keys = ("map_fraction", "pullback_fraction", "lookahead")
    report: dict[str, Any] = {
        "label": LABEL,
        "code_version": code_version(),
        "note": "second evaluation on the 2022 to 2026 held-out window (the first was option A)",
        "selection": "highest net lender yield with worst single event <= "
        f"{cap:.2%} of the vault on 2017 to 2021; else the smallest worst event",
        "config": ob.model_dump(),
        "universes": {},
    }
    for u in oa.universes:
        rows = [r for r in done if r["universe"] == u]
        tune = [r for r in rows if r["span"] == "tuning"]
        chosen = pick_by_yield(tune, cap)
        ev = next(
            r for r in rows if r["span"] == "evaluation" and all(r[k] == chosen[k] for k in keys)
        )
        a_u = a_doc["universes"][u]
        blends = a_u["blends"]["evaluation"]
        b_res = ev["result"]
        nearest = min(
            blends,
            key=lambda x: abs(
                x["net_lender_yield_annualised"] - b_res["net_lender_yield_annualised"]
            ),
        )
        report["universes"][u] = {
            "chosen": {k: chosen[k] for k in keys},
            "tuning_result": chosen["result"],
            "met_cap_on_tuning": worst(chosen["result"]) <= cap,
            "settings_meeting_cap_on_tuning": sum(1 for r in tune if worst(r["result"]) <= cap),
            "settings": len(tune),
            "evaluation": b_res,
            "compare_on_evaluation": {
                "nearest_blend": nearest,
                "fixed_map": a_u["evaluation"]["fixed_map"],
                "dynamic": a_u["evaluation"]["afterhours"],
                "always_weekday": blends[-1],
                "always_weekend": blends[0],
            },
            "grid": {
                s: [
                    {k: r[k] for k in keys}
                    | {
                        "net_lender_yield_annualised": r["result"]["net_lender_yield_annualised"],
                        "interest_usdg": r["result"]["interest_usdg"],
                        "bad_debt_usdg": r["result"]["bad_debt_usdg"],
                        "worst_event_share": worst(r["result"]),
                    }
                    for r in rows
                    if r["span"] == s
                ]
                for s in ("tuning", "evaluation")
            },
        }
    return report


def write(cfg: AfterhoursConfig, data: pd.DataFrame, n_jobs: int = 0) -> str:
    report = run(cfg, data, n_jobs)
    out = cfg.path(cfg.paths.artifacts_dir) / "backtest" / "option_b.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return str(out)
