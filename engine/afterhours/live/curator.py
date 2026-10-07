"""The curator view: which LLTV survives tonight, per live Stock Token market on Morpho.

For each USDG Morpho market lending against a Stock Token on mainnet (read-only), it puts
tonight's calibrated bad case (the same forecast as the risk board, from `LiveRisk`) against the
market's cushion (1 minus LLTV minus Morpho's liquidation incentive allowance, `tier_spec`), and
adds what a curator needs to act on it: utilization and exit liquidity, the feed's state and
price regime, borrower concentration, the highest enabled LLTV whose cushion the bad case does
not reach, and one recommendation.

Recommendations (strongest first; thresholds in config `curator` and `policy`):

- "reduce_cap": tonight's bad case reaches the cushion. A loan at the limit could be left with
  bad debt if the stock opens that far down. Stop new supply and cut the cap.
- "do_not_increase": inside the cushion, but past the margin Afterhours' own vault keeps
  (`policy.pullback_fraction` of the cushion). Hold the cap.
- "watch": the modelled bad case fits, but lenders can barely exit (utilization at or above
  `curator.watch_utilization`) or one borrower holds most of the debt
  (`curator.concentration_watch_share`). Feed state and price quality are shown with each
  market but do not change the call: the weekend freeze is already in the weekend segment's
  calibrated bad case.
- "survives": the modelled bad case stays inside the cushion with the vault's margin.

"Survives" means survives the modelled bad case: the forecast targets a fall beyond it on 1% of
closed periods, and on held-out years it was beaten more often than that on weekends and
holidays (`held_out_miss_rate`). It is not a guarantee.
"""

from __future__ import annotations

from typing import Any

from afterhours.config import AfterhoursConfig
from afterhours.policy.lp import tier_spec

LABELS = {
    "reduce_cap": "Reduce cap",
    "do_not_increase": "Do not increase",
    "watch": "Watch",
    "survives": "Survives the modelled bad case",
    "no_forecast": "No forecast",
}


def cushion(lltv: float) -> float:
    """1 - LLTV - liquidation incentive allowance (the board's and the vault's definition)."""
    return tier_spec("m", lltv).cushion


def highest_surviving(lltvs: list[float], drop: float, keep: float = 0.0) -> float | None:
    """The highest enabled LLTV whose cushion, less `keep` of it, is beyond `drop`."""
    ok = [lv for lv in lltvs if lv > 0 and cushion(lv) * (1 - keep) > drop]
    return max(ok) if ok else None


def _pct(x: float) -> str:
    return f"{x:.1%}"


def market_row(
    cfg: AfterhoursConfig,
    market: dict[str, Any],
    stock: dict[str, Any] | None,
    enabled_lltvs: list[float],
    concentration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One market's curator row from its Morpho state and its stock's live board row."""
    lltv = float(market["lltv"])
    supplied, borrowed = float(market["supplied"]), float(market["borrowed"])
    util = borrowed / supplied if supplied > 0 else 0.0
    c = cushion(lltv)
    keep = cfg.policy.pullback_fraction
    t = (stock or {}).get("tonight")
    regime = (stock or {}).get("regime") or {}
    status = (stock or {}).get("status") or {}
    row: dict[str, Any] = {
        "market_id": market["id"],
        "symbol": market["symbol"],
        "lltv": lltv,
        "cushion": c,
        "margin_limit": c * (1 - keep),
        "supplied_usdg": supplied,
        "borrowed_usdg": borrowed,
        "utilization": util,
        "exit_liquidity_usdg": max(0.0, supplied - borrowed),
        "oracle": {
            "price": (stock or {}).get("price"),
            "updated_at": (stock or {}).get("updated_at"),
            "state": status.get("state"),
            "regime": regime.get("regime"),
            "regime_label": regime.get("label"),
            "quality": (regime.get("quality") or {}).get("score"),
            "quality_grade": (regime.get("quality") or {}).get("grade"),
        },
        "borrowers": concentration,
        "tonight": None,
        "bad_case_drop": None,
        "headroom": None,
        "breach": None,
        "highest_surviving_lltv": None,
        "highest_lltv_with_margin": None,
    }
    if not t:
        row |= {
            "recommendation": "no_forecast",
            "label": LABELS["no_forecast"],
            "reason": f"No forecast for {market['symbol']} right now, so no call on this market.",
        }
        return row
    drop = float(t["bad_case_drop"])
    row |= {
        "tonight": {
            "period": t["period"],
            "alpha": t["alpha"],
            "held_out_miss_rate": t.get("held_out_miss_rate"),
            "held_out_years": t.get("held_out_years"),
            "model_version": t.get("model_version"),
        },
        "bad_case_drop": drop,
        "headroom": c - drop,
        "breach": drop >= c,
        "highest_surviving_lltv": highest_surviving(enabled_lltvs, drop),
        "highest_lltv_with_margin": highest_surviving(enabled_lltvs, drop, keep),
    }
    seg = t["period"]["segment"]
    survive = row["highest_surviving_lltv"]
    survive_text = (
        f"the highest enabled LLTV that survives it is {_pct(survive)}"
        if survive
        else "no enabled LLTV survives it"
    )
    watch: list[str] = []
    if util >= cfg.curator.watch_utilization:
        watch.append(
            f"{_pct(util)} lent, so lenders can withdraw only "
            f"{row['exit_liquidity_usdg']:,.0f} USDG until borrowers repay"
        )
    top = (concentration or {}).get("top_share")
    if top is not None and top >= cfg.curator.concentration_watch_share:
        watch.append(f"one borrower holds {_pct(top)} of the debt")
    # Feed state and price quality are shown, not counted: a frozen weekend feed is already in
    # the weekend segment's calibrated bad case, and a quiet weekday feed is not a cap decision.
    if drop >= c:
        rec = "reduce_cap"
        reason = (
            f"Tonight's bad case for {market['symbol']} ({seg}) is a {_pct(drop)} fall, beyond "
            f"this market's {_pct(c)} cushion at {_pct(lltv)} LLTV: a loan at the limit could be "
            f"left with bad debt. Stop new supply and cut the cap; {survive_text}."
        )
    elif drop >= row["margin_limit"]:
        rec = "do_not_increase"
        reason = (
            f"Tonight's bad case ({_pct(drop)}, {seg}) is inside the {_pct(c)} cushion but past "
            f"the {_pct(row['margin_limit'])} margin Afterhours' own vault keeps. Hold the cap."
        )
    elif watch:
        rec = "watch"
        reason = (
            f"Tonight's bad case ({_pct(drop)}, {seg}) fits the {_pct(c)} cushion, but "
            + "; ".join(watch)
            + "."
        )
    else:
        rec = "survives"
        reason = (
            f"Tonight's bad case ({_pct(drop)}, {seg}) stays inside the {_pct(c)} cushion with "
            f"the vault's margin; {survive_text}."
        )
    row |= {"recommendation": rec, "label": LABELS[rec], "reason": reason, "watch": watch}
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts by recommendation and the money behind each."""
    out: dict[str, Any] = {}
    for r in rows:
        b = out.setdefault(
            r["recommendation"], {"markets": 0, "supplied_usdg": 0.0, "borrowed_usdg": 0.0}
        )
        b["markets"] += 1
        b["supplied_usdg"] += r["supplied_usdg"]
        b["borrowed_usdg"] += r["borrowed_usdg"]
    return out
