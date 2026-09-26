"""Deciding fact 1: how Stock Token Chainlink feeds behave while the exchange is closed.

For each feed we collect `AnswerUpdated` events from every aggregator the proxy has used
(all phases), over recent weekend closed periods and, as a control, weekday overnights.
Each update is placed in a segment of the New York clock:

- `after_hours`   close -> 20:00 ET the same day
- `overnight`     20:00 -> 04:00 ET on nights that are followed by a session
- `pre_market`    04:00 -> the open
- `frozen`        Friday 20:00 -> Sunday 20:00 ET (weekends), and any other time inside a
                  closed period that none of the above cover (holidays)

A feed "freezes over the weekend" if no update lands in `frozen` across the study.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal
from web3 import Web3

from afterhours.chain.abi import get_logs
from afterhours.chain.rpc import Call, block_at_or_after, call_many

NEW_YORK = ZoneInfo("America/New_York")
ANSWER_UPDATED = "AnswerUpdated(int256 indexed current,uint256 indexed roundId,uint256 updatedAt)"
# Robinhood's 24/5 session: Sunday 20:00 ET to Friday 20:00 ET (docs.robinhood.com, Stock Tokens).
SESSION_EDGE_HOUR = 20
PRE_MARKET_HOUR = 4


@dataclass(frozen=True)
class ClosedPeriod:
    """One gap between an exchange close and the next open."""

    close: datetime
    open: datetime

    @property
    def is_weekend(self) -> bool:
        return (self.open - self.close) > timedelta(hours=24)

    @property
    def hours(self) -> float:
        return (self.open - self.close).total_seconds() / 3600


def recent_closed_periods(
    calendar: str, now: datetime, count: int
) -> tuple[list[ClosedPeriod], list[ClosedPeriod]]:
    """The last `count` completed weekend-type and overnight closed periods before `now`."""
    cal = mcal.get_calendar(calendar)
    sched = cal.schedule(
        start_date=(now - timedelta(days=7 * (count + 3))).date(), end_date=now.date()
    )
    opens = [t.to_pydatetime() for t in sched["market_open"]]
    closes = [t.to_pydatetime() for t in sched["market_close"]]
    periods = [ClosedPeriod(c, o) for c, o in zip(closes[:-1], opens[1:], strict=True) if o <= now]
    weekends = [p for p in periods if p.is_weekend][-count:]
    overnights = [p for p in periods if not p.is_weekend][-count:]
    return weekends, overnights


def segment(ts: datetime, period: ClosedPeriod) -> str:
    """Name the part of a closed period that a timestamp falls in (see module doc)."""
    if ts < period.close:
        return "before_close"
    if ts >= period.open:
        return "after_open"
    local = ts.astimezone(NEW_YORK)
    close_local = period.close.astimezone(NEW_YORK)
    open_local = period.open.astimezone(NEW_YORK)
    evening_edge = close_local.replace(hour=SESSION_EDGE_HOUR, minute=0, second=0)
    if local < evening_edge:
        return "after_hours"
    pre_market_start = open_local.replace(hour=PRE_MARKET_HOUR, minute=0, second=0)
    if local >= pre_market_start:
        return "pre_market"
    overnight_start = (open_local - timedelta(days=1)).replace(
        hour=SESSION_EDGE_HOUR, minute=0, second=0
    )
    if local >= overnight_start and overnight_start.weekday() != 5:  # not a Saturday evening
        return "overnight"
    return "frozen"


@dataclass
class FeedStudy:
    """Results for one feed."""

    symbol: str
    proxy: str
    aggregators: list[str]
    weekend_counts: Counter[str] = field(default_factory=Counter)
    overnight_counts: Counter[str] = field(default_factory=Counter)
    weekends: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """JSON-friendly result."""
        moves = [
            w["oracle_move_across_frozen"]
            for w in self.weekends
            if w["oracle_move_across_frozen"] is not None
        ]
        return {
            "symbol": self.symbol,
            "proxy": self.proxy,
            "aggregators": self.aggregators,
            "weekend_updates_by_segment": dict(self.weekend_counts),
            "overnight_updates_by_segment": dict(self.overnight_counts),
            "frozen_updates": self.weekend_counts.get("frozen", 0),
            "weekends": self.weekends,
            "max_abs_oracle_move_across_frozen": max((abs(m) for m in moves), default=None),
        }


def feed_aggregators(w3: Web3, proxies: dict[str, str], block: int) -> dict[str, list[str]]:
    """Every phase aggregator behind each proxy (Chainlink `phaseAggregators`)."""
    phase_ids = call_many(w3, [Call(p, "phaseId()(uint16)") for p in proxies.values()], block=block)
    calls: list[Call] = []
    owners: list[str] = []
    for (symbol, proxy), phase in zip(proxies.items(), phase_ids, strict=True):
        for i in range(1, int(phase or 0) + 1):
            calls.append(Call(proxy, "phaseAggregators(uint16)(address)", (i,)))
            owners.append(symbol)
    out: dict[str, list[str]] = {s: [] for s in proxies}
    for symbol, agg in zip(owners, call_many(w3, calls, block=block), strict=True):
        if agg and int(str(agg), 16) != 0:
            out[symbol].append(Web3.to_checksum_address(str(agg)))
    return out


def study(
    w3: Web3,
    proxies: dict[str, str],
    *,
    calendar: str,
    weekends: int,
    head_block: int,
    max_range: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the weekend and overnight study for `proxies` ({symbol: proxy})."""
    now = now or datetime.fromtimestamp(int(w3.eth.get_block(head_block)["timestamp"]), UTC)
    aggs = feed_aggregators(w3, proxies, head_block)
    by_agg = {a.lower(): s for s, lst in aggs.items() for a in lst}
    results = {s: FeedStudy(s, p, aggs[s]) for s, p in proxies.items()}
    wk, ov = recent_closed_periods(calendar, now, weekends)
    all_aggs = sorted({a for lst in aggs.values() for a in lst})
    periods_out: list[dict[str, Any]] = []
    for kind, periods in (("weekend", wk), ("overnight", ov)):
        for period in periods:
            start = block_at_or_after(
                w3, int((period.close - timedelta(hours=1)).timestamp()), hi=head_block
            )
            end = block_at_or_after(
                w3, int((period.open + timedelta(hours=1)).timestamp()), hi=head_block
            )
            logs = get_logs(w3, ANSWER_UPDATED, all_aggs, start, end, max_range=max_range)
            periods_out.append(
                {
                    "kind": kind,
                    "close": period.close.isoformat(),
                    "open": period.open.isoformat(),
                    "hours": round(period.hours, 2),
                    "from_block": start,
                    "to_block": end,
                    "updates": len(logs),
                }
            )
            per_symbol: dict[str, list[tuple[datetime, int]]] = {s: [] for s in proxies}
            for log in logs:
                sym = by_agg.get(str(log["_address"]).lower())
                if sym:
                    per_symbol[sym].append(
                        (datetime.fromtimestamp(int(log["updatedAt"]), UTC), int(log["current"]))
                    )
            for sym, updates in per_symbol.items():
                updates.sort()
                counts = Counter(segment(t, period) for t, _ in updates)
                if kind == "weekend":
                    results[sym].weekend_counts.update(counts)
                    results[sym].weekends.append(_weekend_detail(period, updates))
                else:
                    results[sym].overnight_counts.update(counts)
    return {
        "calendar": calendar,
        "now": now.isoformat(),
        "periods": periods_out,
        "feeds": [r.summary() for r in results.values()],
    }


def _weekend_detail(
    period: ClosedPeriod, updates: Sequence[tuple[datetime, int]]
) -> dict[str, Any]:
    """Last update before the frozen window, first after, and the move the oracle showed."""
    local_close = period.close.astimezone(NEW_YORK)
    frozen_start = local_close.replace(hour=SESSION_EDGE_HOUR, minute=0, second=0)
    local_open = period.open.astimezone(NEW_YORK)
    frozen_end = (local_open - timedelta(days=1)).replace(
        hour=SESSION_EDGE_HOUR, minute=0, second=0
    )
    before = [u for u in updates if u[0] < frozen_start]
    inside_detail = []
    prev_price = before[-1][1] if before else None
    for ts, price in (u for u in updates if frozen_start <= u[0] < frozen_end):
        change = (price / prev_price - 1) if prev_price else None
        inside_detail.append({"at": ts.isoformat(), "change_vs_previous": change})
        prev_price = price
    inside = [u for u in updates if frozen_start <= u[0] < frozen_end]
    after = [u for u in updates if u[0] >= frozen_end]
    last_before = before[-1] if before else None
    first_after = after[0] if after else None
    move = (first_after[1] / last_before[1] - 1) if last_before and first_after else None
    return {
        "close": period.close.isoformat(),
        "open": period.open.isoformat(),
        "last_update_before_frozen": last_before[0].isoformat() if last_before else None,
        "updates_inside_frozen": len(inside),
        "inside_frozen_detail": inside_detail,
        "first_update_after_frozen": first_after[0].isoformat() if first_after else None,
        "oracle_move_across_frozen": round(move, 6) if move is not None else None,
    }


def latest_updates(w3: Web3, proxies: dict[str, str], block: int) -> dict[str, str | None]:
    """ISO time of each feed's latest round at `block`."""
    rounds = call_many(
        w3,
        [
            Call(p, "latestRoundData()(uint80,int256,uint256,uint256,uint80)")
            for p in proxies.values()
        ],
        block=block,
    )
    return {
        s: (datetime.fromtimestamp(int(r[3]), UTC).isoformat() if r else None)
        for s, r in zip(proxies, rounds, strict=True)
    }


def to_frame(result: dict[str, Any]) -> pd.DataFrame:
    """One row per feed, for printing."""
    rows = [
        {
            "symbol": f["symbol"],
            "frozen_updates": f["frozen_updates"],
            "weekend_after_hours": f["weekend_updates_by_segment"].get("after_hours", 0),
            "weekend_overnight": f["weekend_updates_by_segment"].get("overnight", 0),
            "weekday_overnight": f["overnight_updates_by_segment"].get("overnight", 0),
            "max_abs_move_across_frozen": f["max_abs_oracle_move_across_frozen"],
        }
        for f in result["feeds"]
    ]
    return pd.DataFrame(rows)
