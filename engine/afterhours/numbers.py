"""The numbers the README, pitch and demo scripts quote, generated from artifacts (M12).

`afterhours numbers` writes `artifacts/report/numbers.json`: every entry has the raw value, the
text as written in prose, and the artifact it came from. `scripts/check-numbers.py` fails if a
document quotes a percentage or a thousands-separated number that is not in this file.
"""

from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
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

    # Dated readings of the same study since M1 (artifacts/discovery/oracle_readings/).
    idx_path = art / "discovery" / "oracle_readings" / "index.json"
    if idx_path.exists():
        src = "artifacts/discovery/oracle_readings/index.json"
        idx = json.loads(idx_path.read_text())
        latest = idx["latest"]
        n["oracle_readings.weekends_read"] = _entry(
            idx["weekends_read"], str(idx["weekends_read"]), src
        )
        n["oracle_readings.latest.weekends"] = _entry(
            latest["weekends"], str(latest["weekends"]), src
        )
        n["oracle_readings.latest.first_weekend_close"] = _entry(
            latest["first_weekend_close"], latest["first_weekend_close"][:10], src
        )
        n["oracle_readings.latest.feeds_without_update"] = _entry(
            latest["feeds_without_update"], str(latest["feeds_without_update"]), src
        )
        n["oracle_readings.latest.feeds_with_update"] = _entry(
            latest["feeds_with_update"], ", ".join(latest["feeds_with_update"]) or "none", src
        )

    # The latest price regime snapshot (artifacts/regime/snapshot-*.json, make regime-snapshot).
    snaps = sorted((art / "regime").glob("snapshot-*.json"))
    if snaps:
        src = f"artifacts/regime/{snaps[-1].name}"
        snap = json.loads(snaps[-1].read_text())
        sm = snap["summary"]
        n["regime.as_of"] = _entry(snap["as_of"], snap["as_of"][:10], src)
        n["regime.block"] = _entry(snap["block"], count(snap["block"]), src)
        n["regime.tokens"] = _entry(sm["tokens"], str(sm["tokens"]), src)
        for k in ("frozen", "weekend_venue", "extended", "regular"):
            n[f"regime.counts.{k}"] = _entry(snap["counts"][k], str(snap["counts"][k]), src)
        n["regime.with_dex_price"] = _entry(sm["with_dex_price"], str(sm["with_dex_price"]), src)
        med = sm["median_abs_divergence"]
        n["regime.median_abs_divergence"] = _entry(med, f"{med:.2%}", src)
        n["regime.beyond_divergence_trigger"] = _entry(
            sm["beyond_divergence_trigger"], ", ".join(sm["beyond_divergence_trigger"]), src
        )
        by = {t["symbol"]: t for t in snap["tokens"]}
        for sym in sm["beyond_divergence_trigger"]:
            d = by[sym]["divergence"]
            n[f"regime.divergence.{sym}"] = _entry(d, f"{abs(d):.1%}", src)
            n[f"regime.divergence_signed.{sym}"] = _entry(d, f"{d:+.1%}", src)
            depth = by[sym].get("depth_usd")
            if depth is not None:  # thin pools: a move there is not price discovery
                n[f"regime.depth.{sym}"] = _entry(depth, f"${depth:,.0f}", src)

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

    if "b5.b.bad_debt" in n:
        src = "derived from option_a.json and option_b.json (5 vault stocks)"

        def less(a: float, b: float) -> float:
            return 1 - a / b

        b5 = {
            k: n[f"b5.{k}"]["value"]
            for k in (
                "b.bad_debt",
                "b.worst",
                "blend.bad_debt",
                "blend.worst",
                "fixed_map.bad_debt",
                "fixed_map.worst",
            )
        }
        for other in ("blend", "fixed_map"):
            v = less(b5["b.bad_debt"], b5[f"{other}.bad_debt"])
            n[f"rel.b_vs_{other}.bad_debt_less"] = _entry(v, pct(v, 0), src)
            v = less(b5["b.worst"], b5[f"{other}.worst"])
            n[f"rel.b_vs_{other}.worst_less"] = _entry(v, pct(v, 0), src)
        v = less(
            n["replay.afterhours.bad_debt"]["value"], n["replay.always_weekday.bad_debt"]["value"]
        )
        n["rel.replay.b_less"] = _entry(v, pct(v, 0), n["replay.id"]["source"])

    act_path = art / "backtest" / "option_b_activity.json"
    if act_path.exists():
        act = json.loads(act_path.read_text())
        src = "artifacts/backtest/option_b_activity.json"
        for u, pre in (("vault", "b5"), ("stock_tokens", "b35")):
            a = act["universes"][u]
            tot = a["total"]
            n[f"{pre}.pulls.nights"] = _entry(tot["nights"], count(tot["nights"]), src)
            n[f"{pre}.pulls.stock_nights"] = _entry(
                tot["stock_nights"], count(tot["stock_nights"]), src
            )
            n[f"{pre}.pulls.usdg"] = _entry(tot["usdg_moved"], usd(tot["usdg_moved"]), src)
            for y, v in a["per_year"].items():
                n[f"{pre}.pulls.{y}.nights"] = _entry(v["nights"], str(v["nights"]), src)
                n[f"{pre}.pulls.{y}.usdg"] = _entry(v["usdg_moved"], usd(v["usdg_moved"]), src)

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
        if "rates" in ms:
            r = ms["rates"]
            n["market.supply_apy"] = _entry(
                r["usdg_supply_apy_supply_weighted"],
                pct(r["usdg_supply_apy_supply_weighted"], 4),
                src,
            )
            n["market.borrow_apy"] = _entry(
                r["usdg_borrow_apy_borrow_weighted"],
                pct(r["usdg_borrow_apy_borrow_weighted"], 2),
                src,
            )
            n["market.utilization"] = _entry(
                r["usdg_utilization"], pct(r["usdg_utilization"], 2), src
            )
            n["market.markets_with_borrowing"] = _entry(
                r["markets_with_borrowing"], str(r["markets_with_borrowing"]), src
            )
            n["market.usdg_markets"] = _entry(u["markets"], str(u["markets"]), src)
    n |= market_now(art)
    return {"generated_from": "afterhours numbers", "numbers": n, "oracle": o}


def market_now(art: Path) -> dict[str, dict[str, Any]]:
    """`market_now.*`: the latest dated snapshot (`afterhours market-size --snapshot`)."""
    snaps = sorted(
        (art / "report").glob("market_snapshot_*.json"),
        key=lambda p: int(p.stem.rsplit("_", 1)[1]),
    )
    if not snaps:
        return {}
    ms = json.loads(snaps[-1].read_text())
    src = f"artifacts/report/{snaps[-1].name}"
    u, r = ms["usdg_loan"], ms["rates"]
    usdg = [m for m in ms["markets"] if m["loan_token"] == ms["usdg"]]
    by_borrow = sorted(usdg, key=lambda m: -m["borrowed"])
    top4 = sum(m["borrowed"] for m in by_borrow[:4])
    full = [m for m in usdg if m["supplied"] > 0 and m["borrowed"] >= m["supplied"] * 0.9999]
    dominant = max(r["by_lltv"], key=lambda k: r["by_lltv"][k]["supplied"])
    lv = r["by_lltv"][dominant]
    n = {
        "market_now.block": _entry(ms["block"], count(ms["block"]), src),
        "market_now.date": _entry(ms["block_time"], ms["block_time"][:10], src),
        "market_now.usdg_markets": _entry(u["markets"], str(u["markets"]), src),
        "market_now.usdg_supplied": _entry(u["supplied"], usd(u["supplied"]), src),
        "market_now.usdg_borrowed": _entry(u["borrowed"], usd(u["borrowed"]), src),
        "market_now.utilization": _entry(r["usdg_utilization"], pct(r["usdg_utilization"]), src),
        "market_now.borrow_apy": _entry(
            r["usdg_borrow_apy_borrow_weighted"], pct(r["usdg_borrow_apy_borrow_weighted"]), src
        ),
        "market_now.supply_apy": _entry(
            r["usdg_supply_apy_supply_weighted"], pct(r["usdg_supply_apy_supply_weighted"]), src
        ),
        "market_now.markets_with_borrowing": _entry(
            r["markets_with_borrowing"], str(r["markets_with_borrowing"]), src
        ),
        "market_now.dominant_lltv": _entry(float(dominant), pct(float(dominant)), src),
        "market_now.dominant_lltv_supply_share": _entry(
            lv["supplied"] / u["supplied"], pct(lv["supplied"] / u["supplied"], 2), src
        ),
        "market_now.dominant_lltv_borrowed": _entry(lv["borrowed"], usd(lv["borrowed"]), src),
        "market_now.top4_borrow_share": _entry(
            top4 / u["borrowed"], pct(top4 / u["borrowed"]), src
        ),
        "market_now.top4_symbols": _entry(
            [m["symbol"] for m in by_borrow[:4]],
            ", ".join(m["symbol"] for m in by_borrow[:4]),
            src,
        ),
        "market_now.fully_lent_markets": _entry(len(full), str(len(full)), src),
    }
    return n


def write(cfg: AfterhoursConfig) -> str:
    out = cfg.path(cfg.paths.artifacts_dir) / "report" / "numbers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(cfg), indent=2, default=str) + "\n")
    return str(out)
