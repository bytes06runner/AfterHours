"""The numbers the README, pitch and demo scripts quote, generated from artifacts (M12).

`afterhours numbers` writes `artifacts/report/numbers.json`: every entry has the raw value, the
text as written in prose, and the artifact it came from. `scripts/check-numbers.py` fails if a
document quotes a percentage or a thousands-separated number that is not in this file.
"""

from __future__ import annotations

import json
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from afterhours.config import AfterhoursConfig
from afterhours.policy.lp import TierSpec, tier_spec

# The pre-registered verdict, verbatim from PROGRESS.md (tests/test_numbers.py checks it is there).
VERDICT_RULE = (
    "The dynamic strategy wins only if, on 2022 to 2026, it has less bad debt than the "
    "no-hindsight fixed map at equal or higher interest."
)
VERDICT_RESULT = (
    "The dynamic strategy has less bad debt but less interest in both universes, so under the "
    "rule it does not win. Option B applies."
)


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def usd(x: float) -> str:
    return f"{x:,.0f}"


def count(x: int) -> str:
    return f"{x:,}"


def oracle_summary(study: dict[str, Any]) -> dict[str, Any]:
    """How the Stock Token feeds behaved inside the weekend window the study calls frozen."""
    ny = ZoneInfo("America/New_York")
    feeds = study["feeds"]
    weekends = [p for p in study["periods"] if p["kind"] == "weekend"]
    updates = []
    for f in feeds:
        for w in f["weekends"]:
            friday = datetime.fromisoformat(w["close"]).astimezone(ny).date()
            opened = datetime.combine(friday, time(20, 0), tzinfo=ny)
            for u in w["inside_frozen_detail"]:
                at = datetime.fromisoformat(u["at"])
                updates.append(
                    {
                        "symbol": f["symbol"],
                        "at": u["at"],
                        "seconds_after_open": (at - opened).total_seconds(),
                    }
                )
    offsets = [u["seconds_after_open"] for u in updates]
    return {
        "weekends": len(weekends),
        "first_weekend_close": weekends[0]["close"] if weekends else None,
        "last_weekend_close": weekends[-1]["close"] if weekends else None,
        "feeds": len(feeds),
        "feeds_without_update": sum(1 for f in feeds if f["frozen_updates"] == 0),
        "feeds_with_update": sorted({u["symbol"] for u in updates}),
        "updates_in_window": len(updates),
        "updates": updates,
        "max_seconds_after_window_opened": max(offsets) if offsets else None,
        "window": "Friday 20:00 to Sunday 20:00 New York",
    }


def _entry(value: Any, text: str, source: str) -> dict[str, Any]:
    return {"value": value, "text": text, "source": source}


def build(cfg: AfterhoursConfig) -> dict[str, Any]:
    art = cfg.path(cfg.paths.artifacts_dir)

    def read(*parts: str) -> Any:
        return json.loads(art.joinpath(*parts).read_text())

    gaps = read("gaps", "summary.json")
    card = read("model", "report_card.json")
    bt = read("backtest", "results.json")
    study = read("discovery", "oracle_study.json")
    scenarios = read("backtest", "scenarios.json")["scenarios"]
    worst = min(scenarios, key=lambda s: s["g"])
    replay = read("backtest", "replay", f"{worst['id']}.json")
    n: dict[str, Any] = {}
    src = "artifacts/gaps/summary.json"
    n["gaps.universe_tickers"] = _entry(
        gaps["tickers"]["universe"], count(gaps["tickers"]["universe"]), src
    )
    n["gaps.closed_periods"] = _entry(
        gaps["universe"]["all"]["n"], count(gaps["universe"]["all"]["n"]), src
    )
    earn = gaps["universe"]["earnings"]
    n["gaps.earnings_nights"] = _entry(earn["n"], count(earn["n"]), src)
    for k in ("0.05", "0.1", "0.2"):
        n[f"gaps.threshold_{k}"] = _entry(float(k), pct(float(k), 0), f"{src} (drop thresholds)")
        v = earn["share_drops_at_least"][k]
        n[f"gaps.earnings_share_drop_{k}"] = _entry(v, pct(v), src)
        a = gaps["universe"]["all"]["share_drops_at_least"][k]
        n[f"gaps.all_share_drop_{k}"] = _entry(a, pct(a, 2), src)
    n["gaps.first_year"] = _entry(
        gaps["period"]["first_close"][:4], gaps["period"]["first_close"][:4], src
    )

    src = "artifacts/discovery/oracle_study.json"
    o = oracle_summary(study)
    for k in ("weekends", "feeds", "feeds_without_update", "updates_in_window"):
        n[f"oracle.{k}"] = _entry(o[k], str(o[k]), src)
    n["oracle.feeds_with_update"] = _entry(
        o["feeds_with_update"], ", ".join(o["feeds_with_update"]), src
    )
    secs = o["max_seconds_after_window_opened"]
    n["oracle.max_seconds_after_window_opened"] = _entry(
        secs, f"{secs:.0f}" if secs is not None else "none", src
    )

    src = "artifacts/model/report_card.json"
    acc = card["acceptance"]
    perf = card["shipped_performance"]
    n["model.shipped"] = _entry(acc["shipped"], acc["shipped"], src)
    n["model.first_sentence"] = _entry(card["first_sentence"], card["first_sentence"], src)
    n["model.alpha"] = _entry(acc["alpha"], pct(acc["alpha"], 0), src)
    n["model.heldout_periods"] = _entry(perf["overall"]["n"], count(perf["overall"]["n"]), src)
    for seg in ("overall", "earnings", "weekend", "overnight", "holiday"):
        v = perf[seg]["miss_rate"]
        n[f"model.miss_rate_{seg}"] = _entry(v, pct(v, 2), src)
    n["model.folds"] = _entry(len(card["folds"]), str(len(card["folds"])), src)

    src = "artifacts/backtest/results.json"
    n["backtest.first"] = _entry(bt["period"]["first"], bt["period"]["first"], src)
    n["backtest.last"] = _entry(bt["period"]["last"], bt["period"]["last"], src)
    n["backtest.closed_periods"] = _entry(
        bt["period"]["closed_periods"], count(bt["period"]["closed_periods"]), src
    )
    n["backtest.vault_usdg"] = _entry(
        bt["assumptions"]["vault_usdg"], usd(bt["assumptions"]["vault_usdg"]), src
    )
    n["backtest.selected"] = _entry(bt["selected"], ", ".join(bt["selected"]), src)
    for k, s in bt["strategies"].items():
        n[f"backtest.{k}.yield"] = _entry(
            s["net_lender_yield_annualised"], pct(s["net_lender_yield_annualised"], 2), src
        )
        n[f"backtest.{k}.bad_debt"] = _entry(s["bad_debt_usdg"], usd(s["bad_debt_usdg"]), src)
        n[f"backtest.{k}.bad_debt_events"] = _entry(
            s["bad_debt_events"], str(s["bad_debt_events"]), src
        )
        w = s.get("worst_event") or {}
        if "share_of_vault" in w:
            n[f"backtest.{k}.worst_event_share"] = _entry(
                w["share_of_vault"], pct(w["share_of_vault"], 2), src
            )
    ch = bt["chosen"]
    n["backtest.max_worst_event_share"] = _entry(
        bt["assumptions"]["max_worst_event_share"],
        pct(bt["assumptions"]["max_worst_event_share"], 2),
        src,
    )
    ratio = (
        bt["strategies"]["always_weekday"]["bad_debt_usdg"]
        / bt["strategies"]["afterhours"]["bad_debt_usdg"]
    )
    n["backtest.bad_debt_ratio_weekday_vs_afterhours"] = _entry(ratio, f"{ratio:.0f}", src)

    src = "config/afterhours.yaml (backtest-chosen tiers)"
    tiers: dict[str, TierSpec] = {
        "weekday": tier_spec("weekday", float(ch["weekday_lltv"])),
        "weekend": tier_spec("weekend", float(ch["weekend_lltv"])),
    }
    for name, t in tiers.items():
        n[f"tiers.{name}.lltv"] = _entry(t.lltv, pct(t.lltv), src)
        n[f"tiers.{name}.cushion"] = _entry(t.cushion, pct(t.cushion), src)
    n["policy.safety_margin"] = _entry(ch["safety_margin"], pct(ch["safety_margin"], 0), src)

    src = f"artifacts/backtest/replay/{worst['id']}.json"
    n["replay.id"] = _entry(worst["id"], worst["id"], src)
    n["replay.ticker"] = _entry(worst["ticker"], worst["ticker"], src)
    n["replay.date"] = _entry(worst["session_prev"], worst["session_prev"], src)
    n["replay.gap"] = _entry(worst["g"], pct(abs(worst["g"])), src)
    for k in ("always_weekday", "afterhours"):
        v = replay["vaults"][k]["bad_debt_usdg"]
        n[f"replay.{k}.bad_debt"] = _entry(v, usd(v), src)
    n["replay.vault_usdg"] = _entry(replay["vault_usdg"], usd(replay["vault_usdg"]), src)
    a_path = art / "backtest" / "option_a.json"
    b_path = art / "backtest" / "option_b.json"
    if a_path.exists() and b_path.exists():
        a_doc = json.loads(a_path.read_text())
        b_doc = json.loads(b_path.read_text())
        n["verdict.rule"] = _entry(VERDICT_RULE, VERDICT_RULE, "PROGRESS.md (pre-registered)")
        n["verdict.result"] = _entry(VERDICT_RESULT, VERDICT_RESULT, "PROGRESS.md")
        src_a, src_b = "artifacts/backtest/option_a.json", "artifacts/backtest/option_b.json"
        for u, pre in (("vault", "b5"), ("stock_tokens", "b35")):
            bu, au = b_doc["universes"][u], a_doc["universes"][u]
            ev = au["periods"]["evaluation"]
            n[f"{pre}.eval_first"] = _entry(ev["first"], ev["first"], src_a)
            n[f"{pre}.eval_last"] = _entry(ev["last"], ev["last"], src_a)
            n[f"{pre}.eval_closed_periods"] = _entry(
                ev["closed_periods"], count(ev["closed_periods"]), src_a
            )
            n[f"{pre}.stocks"] = _entry(len(au["tickers"]), str(len(au["tickers"])), src_a)
            rows = {
                "b": (bu["evaluation"], src_b),
                "fixed_map": (au["evaluation"]["fixed_map"], src_a),
                "dynamic": (au["evaluation"]["afterhours"], src_a),
                "blend": (bu["compare_on_evaluation"]["nearest_blend"], src_a),
                "always_weekday": (bu["compare_on_evaluation"]["always_weekday"], src_a),
                "always_weekend": (bu["compare_on_evaluation"]["always_weekend"], src_a),
            }
            for k, (r, src_r) in rows.items():
                w = (r.get("worst_event") or {}).get("share_of_vault", 0.0)
                n[f"{pre}.{k}.yield"] = _entry(
                    r["net_lender_yield_annualised"],
                    pct(r["net_lender_yield_annualised"], 2),
                    src_r,
                )
                n[f"{pre}.{k}.bad_debt"] = _entry(
                    r["bad_debt_usdg"], usd(r["bad_debt_usdg"]), src_r
                )
                n[f"{pre}.{k}.interest"] = _entry(
                    r["interest_usdg"], usd(r["interest_usdg"]), src_r
                )
                n[f"{pre}.{k}.worst"] = _entry(w, pct(w, 3), src_r)
            blend_w = bu["compare_on_evaluation"]["nearest_blend"]["w"]
            n[f"{pre}.blend.weekday_share"] = _entry(blend_w, pct(blend_w, 0), src_a)
            c = bu["chosen"]
            n[f"{pre}.chosen.map_fraction"] = _entry(
                c["map_fraction"], pct(c["map_fraction"], 0), src_b
            )
            n[f"{pre}.chosen.pullback_fraction"] = _entry(
                c["pullback_fraction"], pct(c["pullback_fraction"], 0), src_b
            )
            n[f"{pre}.chosen.lookahead"] = _entry(c["lookahead"], str(c["lookahead"]), src_b)
            n[f"{pre}.tuning_worst"] = _entry(
                (bu["tuning_result"].get("worst_event") or {}).get("share_of_vault", 0.0),
                pct((bu["tuning_result"].get("worst_event") or {}).get("share_of_vault", 0.0), 3),
                src_b,
            )
            fm_tune = [x for x in au["grid"]["tuning"] if x["kind"] == "fixed_map"]
            smallest = min(x["worst_event_share"] for x in fm_tune)
            n[f"{pre}.fixed_map.tuning_smallest_worst"] = _entry(smallest, pct(smallest, 3), src_a)
            n[f"{pre}.settings_tuned"] = _entry(bu["settings"], str(bu["settings"]), src_b)
            n[f"{pre}.settings_meeting_cap"] = _entry(
                bu["settings_meeting_cap_on_tuning"],
                str(bu["settings_meeting_cap_on_tuning"]),
                src_b,
            )
            t = bu["evaluation"]["share_of_time"]
            for tier in ("weekday", "middle", "weekend", "idle"):
                n[f"{pre}.b.time_{tier}"] = _entry(
                    t.get(tier, 0.0), pct(t.get(tier, 0.0), 0), src_b
                )
        oa = cfg.backtest.option_a
        n["option_a.tuning_years"] = _entry(
            list(oa.tuning_years), f"{oa.tuning_years[0]} to {oa.tuning_years[1]}", "config"
        )
        n["option_a.evaluation_years"] = _entry(
            list(oa.evaluation_years),
            f"{oa.evaluation_years[0]} to {oa.evaluation_years[1]}",
            "config",
        )
        mid = tier_spec("middle", oa.tiers["middle"])
        n["tiers.middle.lltv"] = _entry(mid.lltv, pct(mid.lltv), "config (enabled onchain, M1)")
        n["tiers.middle.cushion"] = _entry(
            mid.cushion, pct(mid.cushion), "config (enabled onchain, M1)"
        )
        pol = cfg.policy
        for name, lltv in cfg.morpho.lltv_tiers.ordered():
            spec = tier_spec(name, lltv)
            n[f"tiers.{name}.lltv_short"] = _entry(
                lltv, f"{lltv * 100:g}%", "config morpho.lltv_tiers"
            )
            lim = spec.cushion * (1 - pol.map_fraction)
            n[f"policy.map_limit.{name}"] = _entry(lim, pct(lim), "config policy (option B)")
            apy = cfg.backtest.apy(lltv)
            n[f"assumed_apy.{name}"] = _entry(apy, pct(apy), "config backtest.supply_apy_by_lltv")
        pull = max(tier_spec(nm, v).cushion for nm, v in cfg.morpho.lltv_tiers.ordered()) * (
            1 - pol.pullback_fraction
        )
        n["policy.pull_limit"] = _entry(pull, pct(pull), "config policy (option B)")
        n["policy.lookahead"] = _entry(
            pol.lookahead_closed_periods, str(pol.lookahead_closed_periods), "config policy"
        )

    size_path = art / "discovery" / "market_size.json"
    if size_path.exists():
        src = "artifacts/discovery/market_size.json"
        ms = json.loads(size_path.read_text())
        u = ms["usdg_loan"]
        n["market.block"] = _entry(ms["block"], count(ms["block"]), src)
        n["market.date"] = _entry(ms["block_time"], ms["block_time"][:10], src)
        n["market.stock_token_markets"] = _entry(
            ms["stock_token_markets"], str(ms["stock_token_markets"]), src
        )
        n["market.usdg_supplied"] = _entry(u["supplied"], usd(u["supplied"]), src)
        n["market.usdg_borrowed"] = _entry(u["borrowed"], usd(u["borrowed"]), src)
    return {"generated_from": "afterhours numbers", "numbers": n, "oracle": o}


def write(cfg: AfterhoursConfig) -> str:
    out = cfg.path(cfg.paths.artifacts_dir) / "report" / "numbers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(cfg), indent=2, default=str) + "\n")
    return str(out)
