"""Clock-aware scheduler: hourly, pre-close, post-open and pre-earnings jobs plus event triggers.

APScheduler fires a tick every `schedule.tick_seconds`. Each tick asks which marks passed since
the previous tick on the profile's clock (chain time on fork and local, so demo time jumps fire
the right jobs) and which triggers are active, then runs one allocator cycle naming them all.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from afterhours.chain.rpc import Call, call_many
from afterhours.config import AfterhoursConfig, ScheduleConfig
from afterhours.features.dataset import sessions

log = logging.getLogger(__name__)
LATEST_ROUND = "latestRoundData()(uint80,int256,uint256,uint256,uint80)"


def schedule_marks(
    sched: ScheduleConfig,
    calendar: str,
    start: datetime,
    end: datetime,
    earnings: dict[str, list[tuple[datetime, str]]],
) -> list[tuple[datetime, str]]:
    """Every job mark in (start, end], sorted: hourly, pre_close, post_open, pre_earnings:<sym>."""
    marks: list[tuple[datetime, str]] = []
    if sched.hourly:
        t = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        while t <= end:
            marks.append((t, "hourly"))
            t += timedelta(hours=1)
    sess = sessions(calendar, (start - timedelta(days=5)).date(), (end + timedelta(days=5)).date())
    for o, c in zip(sess["open"], sess["close"], strict=True):
        marks.append((c.to_pydatetime() - timedelta(minutes=sched.pre_close_minutes), "pre_close"))
        marks.append((o.to_pydatetime() + timedelta(minutes=sched.post_open_minutes), "post_open"))
    for sym, events in earnings.items():
        for when, _timing in events:
            marks.append((when - timedelta(hours=sched.pre_earnings_hours), f"pre_earnings:{sym}"))
    return sorted(m for m in marks if start < m[0] <= end)


def pre_close_window(cfg: AfterhoursConfig, now: datetime) -> datetime | None:
    """The close whose pre-close window (`schedule.pre_close_minutes`) contains `now`, if any."""
    sess = sessions(cfg.data.exchange_calendar, (now - timedelta(days=1)).date(), now.date())
    lead = timedelta(minutes=cfg.schedule.pre_close_minutes)
    for c in sess["close"]:
        close: datetime = c.to_pydatetime()
        if close - lead <= now < close:
            return close
    return None


def earnings_times(calendar: str, events: Iterable[tuple[Any, str]]) -> list[tuple[datetime, str]]:
    """Map (date, timing) to the bell it is tied to: bmo -> that day's open, else its close."""
    rows = list(events)
    if not rows:
        return []
    days = [d for d, _ in rows]
    sess = sessions(calendar, min(days) - timedelta(days=5), max(days) + timedelta(days=5))
    out = []
    for d, timing in rows:
        if d in sess.index:
            bell = pd.Timestamp(sess.at[d, "open"] if timing == "bmo" else sess.at[d, "close"])  # type: ignore[arg-type]
            out.append((bell.to_pydatetime(), timing))
    return out


@dataclass
class TriggerState:
    """Oracle samples for the shock and staleness triggers."""

    samples: dict[str, deque[tuple[datetime, float]]] = field(default_factory=dict)
    last_fired: dict[str, datetime] = field(default_factory=dict)


def shock_triggers(
    state: TriggerState, now: datetime, prices: dict[str, float], move: float, window: timedelta
) -> list[str]:
    """Stocks whose oracle price moved more than `move` within `window`."""
    fired = []
    for sym, price in prices.items():
        q = state.samples.setdefault(sym, deque())
        q.append((now, price))
        while q and q[0][0] < now - window:
            q.popleft()
        lo, hi = min(p for _, p in q), max(p for _, p in q)
        if lo > 0 and (hi / lo - 1) > move:
            fired.append(f"shock:{sym}")
    return fired


def stale_triggers(
    updated: dict[str, datetime], now: datetime, is_open: bool, stale: timedelta
) -> list[str]:
    """Feeds older than `stale` while the market is open."""
    if not is_open:
        return []
    return [f"stale:{s}" for s, t in updated.items() if now - t > stale]


def v3_pool_price(
    sqrt_price_x96: int, stock_is_token0: bool, stock_decimals: int, usd_decimals: int
) -> float:
    """Stock price in USDG from a Uniswap v3 pool's sqrtPriceX96 (token1 per token0)."""
    raw = float((sqrt_price_x96 / 2**96) ** 2)
    if stock_is_token0:
        return raw * 10.0 ** (stock_decimals - usd_decimals)
    return 1.0 / (raw * 10.0 ** (usd_decimals - stock_decimals)) if raw else 0.0


def divergence_triggers(pool: dict[str, float], oracle: dict[str, float], pct: float) -> list[str]:
    """Stocks whose pool price is more than `pct` away from the oracle."""
    return [
        f"divergence:{s}" for s, p in pool.items() if oracle.get(s) and abs(p / oracle[s] - 1) > pct
    ]


class BotScheduler:
    """Runs the allocator on schedule and on triggers."""

    def __init__(self, cfg: AfterhoursConfig) -> None:
        from afterhours.bot.allocator import Allocator
        from afterhours.data.pipeline import make_cache

        self.cfg = cfg
        self.allocator = Allocator(cfg)
        self.cache = make_cache(cfg)
        self.state = TriggerState()
        self.last_tick: datetime | None = None
        self.oracles = {m["symbol"]: m["oracle"] for m in self.allocator.deployment["markets"]}
        self.pools = self._pools()

    def _pools(self) -> dict[str, dict[str, Any]]:
        """Deepest USDG v3 pool per stock on native collateral (for the divergence trigger)."""
        from afterhours.deployments import load_discovered

        if self.allocator.deployment["simulation"]["collateral"]:
            return {}
        stocks = load_discovered(self.cfg, "fork").get("stock_tokens", {})
        out = {}
        for sym in self.oracles:
            pools = [
                p
                for p in stocks.get(sym, {}).get("pools", [])
                if p["version"] == "v3" and p["quote_symbol"] == "USDG"
            ]
            if pools:
                out[sym] = pools[0]
        return out

    def _earnings(self) -> dict[str, list[tuple[datetime, str]]]:
        out = {}
        for sym in self.allocator.symbols():
            ev = self.cache.get(f"earnings/{sym}", allow_stale=True)
            rows = [] if ev is None else list(zip(ev["date"], ev["timing"], strict=True))
            out[sym] = earnings_times(self.cfg.data.exchange_calendar, rows)
        return out

    def tick(self) -> list[str]:
        """One tick: find due jobs and triggers, run a cycle if any. Returns what fired."""
        from afterhours.risk.live import session_state

        now = self.allocator.now()
        start = self.last_tick or now - timedelta(seconds=self.cfg.schedule.tick_seconds)
        self.last_tick = now
        fired = [
            name
            for _, name in schedule_marks(
                self.cfg.schedule, self.cfg.data.exchange_calendar, start, now, self._earnings()
            )
        ]
        t = self.cfg.schedule.triggers
        rounds = call_many(
            self.allocator.w3, [Call(o, LATEST_ROUND) for o in self.oracles.values()]
        )
        prices = {s: float(r[1]) for s, r in zip(self.oracles, rounds, strict=True) if r}
        updated = {
            s: datetime.fromtimestamp(int(r[3]), UTC)
            for s, r in zip(self.oracles, rounds, strict=True)
            if r
        }
        fired += shock_triggers(
            self.state, now, prices, t.shock_move_pct, timedelta(minutes=t.shock_window_min)
        )
        is_open = session_state(self.cfg.data.exchange_calendar, now).state == "open"
        fired += stale_triggers(updated, now, is_open, timedelta(minutes=t.stale_minutes))
        if self.pools:
            slots = call_many(
                self.allocator.w3,
                [
                    Call(
                        p["address_or_id"], "slot0()(uint160,int24,uint16,uint16,uint16,uint8,bool)"
                    )
                    for p in self.pools.values()
                ],
            )
            pool_prices = {
                s: v3_pool_price(int(sl[0]), p["token"].lower() < p["quote"].lower(), 18, 6)
                for (s, p), sl in zip(self.pools.items(), slots, strict=True)
                if sl
            }
            fired += divergence_triggers(
                pool_prices, {k: v / 1e8 for k, v in prices.items()}, t.divergence_pct
            )
        # Each trigger fires at most once per shock window.
        fresh = []
        for name in dict.fromkeys(fired):
            last = self.state.last_fired.get(name)
            if (
                name.startswith(("shock:", "stale:", "divergence:"))
                and last
                and now - last < timedelta(minutes=t.shock_window_min)
            ):
                continue
            self.state.last_fired[name] = now
            fresh.append(name)
        if fresh:
            log.info("cycle for %s", ", ".join(fresh))
            self.allocator.run_cycle(",".join(fresh))
        return fresh

    def run(self) -> None:
        """Block forever, ticking on an interval."""
        from apscheduler.schedulers.blocking import BlockingScheduler

        sched = BlockingScheduler(timezone=UTC)
        sched.add_job(
            self.tick,
            "interval",
            seconds=self.cfg.schedule.tick_seconds,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(UTC),
        )
        log.info("scheduler started for %s", self.cfg.active_profile)
        sched.start()
