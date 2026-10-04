"""Read-only weekend risk for AI agents (docs/AGENTS.md).

The four documents behind `/v1/agent/*` and the MCP tools of the same names:

- `market_status`    session state, next open and close, the weekend window, regime counts;
- `weekend_risk`     one Stock Token: regime, price quality, next closed period, bad case, and a
                     one-paragraph plain-English summary;
- `position_check`   every Stock Token Morpho loan of an address with LTV, liquidation price and
                     whether tonight's bad case reaches it;
- `explain_move`     a reason card and its onchain verification.

Everything is built from data the API already serves (the live board, the position checker, the
reason store), so agents see exactly what people see. Nothing here signs or sends anything. The
rate limiter is a per-client token bucket.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

NEW_YORK = ZoneInfo("America/New_York")
DISCLAIMER = "Read-only risk information from Afterhours, not financial advice."


def _ny(iso: str) -> str:
    t = datetime.fromisoformat(iso).astimezone(NEW_YORK)
    return f"{t:%a %b} {t.day}, {t:%H:%M} New York"


def _pct(x: float) -> str:
    return f"{x:.1%}"


# ------------------------------------------------------------------ response models (OpenAPI)
class _Doc(BaseModel):
    model_config = ConfigDict(extra="allow")


class MarketStatus(_Doc):
    as_of: str = Field(description="When this was read (UTC).")
    session: str = Field(description="open, closed or holiday (XNYS calendar).")
    next_open: str
    next_close: str
    seconds_to_open: int
    seconds_to_close: int
    feeds_window: str = Field(description="regular, extended or closed: where feeds post now.")
    closed_since: str | None = Field(description="Start of the current shut stretch, if shut.")
    regime_counts: dict[str, int] | None = Field(description="Stock Tokens per price regime.")
    summary: str


class WeekendRisk(_Doc):
    symbol: str
    network: str
    block: int
    as_of: str
    feed_price: float | None
    regime: dict[str, Any] = Field(description="Regime, price quality and line (docs/REGIME.md).")
    next_closed_period: dict[str, Any] | None
    bad_case_drop: float | None = Field(description="Fall beaten only about 1 night in 1/alpha.")
    alpha: float | None
    markets: list[dict[str, Any]] = Field(description="USDG Morpho markets: LLTV and cushion.")
    beyond_cushion_of: list[float] = Field(description="LLTVs whose cushion the bad case passes.")
    summary: str


class PositionCheck(_Doc):
    address: str
    network: str
    block: int
    as_of: str
    loans: list[dict[str, Any]]
    summary: str


class MoveExplanation(_Doc):
    reason_id: str
    card: dict[str, Any]
    canonical_json: str = Field(description="RFC 8785 JSON whose keccak256 is the reason hash.")
    verification: dict[str, Any]
    summary: str


# ------------------------------------------------------------------ builders
def market_status(status: dict[str, Any], regimes: dict[str, Any] | None) -> dict[str, Any]:
    """From `/v1/status` and the board's regime summary (if a board has been read)."""
    when = {"open": "open", "closed": "closed", "holiday": "closed for a holiday"}
    state = when.get(status["state"], status["state"])
    parts = [f"The US stock exchange is {state}."]
    if status["state"] == "open":
        parts.append(f"It closes at {_ny(status['next_close'])}.")
    else:
        parts.append(f"It opens at {_ny(status['next_open'])}.")
    window = regimes["calendar"] if regimes else None
    since = regimes.get("closed_since") if regimes else None
    if window == "closed" and since:
        parts.append(
            "Stock Token price feeds are inside a shut stretch that began at "
            f"{_ny(since)}; they normally post nothing until it ends."
        )
    elif window == "extended":
        parts.append("Feeds are in extended hours: they post, but the exchange is not trading.")
    counts = regimes.get("counts") if regimes else None
    if counts:
        named = {
            "regular": "regular session",
            "extended": "extended hours",
            "weekend_venue": "on a weekend price",
            "frozen": "frozen",
        }
        parts.append(
            "Stock Tokens by price regime: "
            + ", ".join(f"{n} {named[k]}" for k, n in counts.items() if n)
            + "."
        )
    return {
        "as_of": status["now"],
        "session": status["state"],
        "next_open": status["next_open"],
        "next_close": status["next_close"],
        "seconds_to_open": status["seconds_to_open"],
        "seconds_to_close": status["seconds_to_close"],
        "feeds_window": window,
        "closed_since": since,
        "regime_counts": counts,
        "summary": " ".join(parts),
    }


def weekend_risk(board: dict[str, Any], symbol: str) -> dict[str, Any]:
    """One Stock Token from the live board. Raises KeyError for an unknown ticker."""
    sym = symbol.strip().upper()
    row = next((r for r in board["stocks"] if r["symbol"] == sym), None)
    if row is None:
        raise KeyError(sym)
    regime = row.get("regime") or {}
    t = row.get("tonight")
    parts = [regime.get("line") or f"{sym}: no price regime reading yet."]
    q = (regime.get("quality") or {}).get("score")
    if q is not None:
        parts.append(f"Price quality {q} of 100 ({regime['quality']['grade']}).")
    if t:
        p = t["period"]
        one_in = round(1 / t["alpha"]) if t["alpha"] else None
        parts.append(
            f"The next closed period is a {p['segment']} from {_ny(p['starts'])} to "
            f"{_ny(p['ends'])} ({float(p['hours']):.1f} hours closed). Its bad case, the fall "
            f"beaten only about 1 night in {one_in}, is {_pct(t['bad_case_drop'])}."
        )
        markets = row["markets"]
        if not markets:
            parts.append(f"No USDG Morpho market lends against {sym}.")
        elif row["breached"]:
            parts.append(
                f"That is beyond the cushion of {len(row['breached'])} of {len(markets)} USDG "
                f"Morpho markets lending against {sym} (LLTV "
                + ", ".join(_pct(x) for x in row["breached"])
                + "), so a loan at those markets' limits could be left with bad debt."
            )
        else:
            parts.append(
                f"That stays inside the cushion of every USDG Morpho market lending against "
                f"{sym} ({len(markets)})."
            )
    else:
        parts.append("There is no bad-case forecast for this stock right now.")
    parts.append(DISCLAIMER)
    return {
        "symbol": sym,
        "network": board["network"],
        "block": board["block"],
        "as_of": board["as_of"],
        "feed_price": row["price"],
        "regime": regime,
        "next_closed_period": t["period"] if t else None,
        "bad_case_drop": t["bad_case_drop"] if t else None,
        "alpha": t["alpha"] if t else None,
        "markets": row["markets"],
        "beyond_cushion_of": row["breached"],
        "summary": " ".join(parts),
    }


def position_check(doc: dict[str, Any]) -> dict[str, Any]:
    """From the live position checker."""
    loans = []
    lines = []
    for p in doc["positions"]:
        if p.get("borrowed", 0) <= 0:
            continue
        unit = p.get("loan_symbol") or "units of the loan token"
        loan = {
            "symbol": p["symbol"],
            "market_id": p["market_id"],
            "lltv": p["lltv"],
            "borrowed": p["borrowed"],
            "loan_symbol": p.get("loan_symbol"),
            "collateral_tokens": p["collateral_tokens"],
            "ltv": p.get("ltv"),
            "liquidation_price": p.get("liquidation_price"),
            "drop_to_liquidation": p.get("drop_to_liquidation"),
            "bad_case_tonight": (p.get("tonight") or {}).get("bad_case_drop"),
            "tonight_reaches_liquidation": p.get("breach_tonight"),
        }
        loans.append(loan)
        line = f"{p['symbol']}: {p['borrowed']:,.2f} {unit} borrowed at {_pct(p['lltv'])} LLTV"
        if p.get("ltv") is not None and p.get("drop_to_liquidation") is not None:
            line += (
                f", LTV {_pct(p['ltv'])}, liquidated after a {_pct(p['drop_to_liquidation'])} "
                f"fall (at {p['liquidation_price']:,.2f})"
            )
        if loan["bad_case_tonight"] is not None:
            reach = "reaches" if p.get("breach_tonight") else "does not reach"
            line += f"; tonight's bad case ({_pct(loan['bad_case_tonight'])}) {reach} it"
        lines.append(line + ".")
    head = (
        f"{len(loans)} open Stock Token loan(s) for {doc['address']} on {doc['network']}."
        if loans
        else f"No open Stock Token loans for {doc['address']} on {doc['network']}."
    )
    return {
        "address": doc["address"],
        "network": doc["network"],
        "block": doc["block"],
        "as_of": doc["as_of"],
        "loans": loans,
        "summary": " ".join([head, *lines, DISCLAIMER]),
    }


def explain_move(
    card: dict[str, Any], canonical_json: str, verification: dict[str, Any]
) -> dict[str, Any]:
    """A reason card, its canonical JSON and the onchain check, with a plain summary."""
    status = verification.get("status")
    checked = (
        "Its hash matches the ReasonLogged event onchain."
        if status == "matched"
        else f"Onchain check: {status or 'not available'}."
    )
    created = card.get("created_at")
    summary = " ".join(
        x
        for x in (
            f"On {_ny(created)}" if created else None,
            f"the Afterhours bot ({card.get('profile')}) wrote: {card.get('rule_fired')}",
            checked,
        )
        if x
    )
    return {
        "reason_id": card["id"],
        "card": card,
        "canonical_json": canonical_json,
        "verification": verification,
        "summary": summary,
    }


# ------------------------------------------------------------------ rate limit
class RateLimiter:
    """Token bucket per client: `per_minute` refill, up to `burst` at once."""

    def __init__(self, per_minute: int, burst: int, max_clients: int) -> None:
        self.rate = per_minute / 60.0
        self.burst = float(burst)
        self.max_clients = max_clients
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, client: str, now: float | None = None) -> float:
        """0 if allowed, else seconds until the next request would be."""
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._buckets.get(client, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if tokens >= 1:
                self._buckets[client] = (tokens - 1, now)
                wait = 0.0
            else:
                self._buckets[client] = (tokens, now)
                wait = (1 - tokens) / self.rate
            if len(self._buckets) > self.max_clients:  # forget the least recently seen
                for k, _ in sorted(self._buckets.items(), key=lambda kv: kv[1][1])[
                    : len(self._buckets) - self.max_clients
                ]:
                    del self._buckets[k]
            return wait


def client_address(forwarded_for: str | None, peer: str | None, hops: int) -> str:
    """The caller's address: X-Forwarded-For's entry `hops` from the right, else the peer."""
    if forwarded_for:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if parts:
            return parts[max(0, len(parts) - hops)]
    return peer or "unknown"
