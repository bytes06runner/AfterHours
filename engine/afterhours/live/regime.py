"""Price regime monitor: which pricing regime each Stock Token is in, and how good its price is.

Regimes (docs/REGIME.md):

- `regular`        the exchange is in its regular session;
- `extended`       outside the session but inside the hours the feeds keep posting (after hours,
                   overnight, pre-market: the Robinhood 24 Hour Market's Sunday 20:00 to Friday
                   20:00 New York);
- `weekend_venue`  the exchange and the 24/5 hours are both shut (the weekend window, holidays),
                   and the feed has posted since that stretch began: a weekend price source;
- `frozen`         shut, and the feed has posted nothing since the stretch began.

The calendar part reuses the oracle study's own segments, so the monitor and the study agree on
where a timestamp falls. The typical update interval of each feed comes from the study files
(`cadence`), never from a guess.

Price quality score, 0 to 100, a weighted mean of three marks in [0, 1] (weights in config):

- staleness: 1 up to the feed's typical interval for the regime, falling linearly to 0 at
  `stale_multiple` times it (at least `stale_floor_minutes`); 0 when frozen;
- divergence: 1 - |DEX mid / feed - 1| / `schedule.triggers.divergence_pct`, floored at 0;
- depth: log-scaled between `depth_floor_usd` (0) and `depth_full_usd` (1).

A mark that cannot be measured (no DEX pool read) is left out and the weights renormalised; the
score says which marks it used.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas_market_calendars as mcal

from afterhours.config import AfterhoursConfig
from afterhours.discovery.oracle_study import NEW_YORK, ClosedPeriod, segment

REGIMES = ("regular", "extended", "weekend_venue", "frozen")
EXTENDED_SEGMENTS = ("after_hours", "overnight", "pre_market")

LABELS = {
    "regular": "Regular session",
    "extended": "Extended hours",
    "weekend_venue": "Weekend price",
    "frozen": "Frozen",
}


# ------------------------------------------------------------------ the calendar
@lru_cache(maxsize=64)
def _sessions(calendar: str, day: str) -> tuple[tuple[datetime, datetime], ...]:
    """Regular sessions (open, close) in UTC from 10 days before `day` to 10 days after."""
    cal = mcal.get_calendar(calendar)
    d = datetime.fromisoformat(day)
    sched = cal.schedule(
        start_date=(d - timedelta(days=10)).date(), end_date=(d + timedelta(days=10)).date()
    )
    return tuple(
        (o.to_pydatetime().astimezone(UTC), c.to_pydatetime().astimezone(UTC))
        for o, c in zip(sched["market_open"], sched["market_close"], strict=True)
    )


def calendar_state(calendar: str, now: datetime) -> dict[str, Any]:
    """Session, or the closed period and the study segment `now` falls in."""
    sessions = _sessions(calendar, now.date().isoformat())
    for o, c in sessions:
        if o <= now < c:
            return {"state": "regular", "segment": "session", "open": o, "close": c}
    before = [c for _, c in sessions if c <= now]
    after = [o for o, _ in sessions if o > now]
    period = ClosedPeriod(before[-1], after[0])
    seg = segment(now, period)
    state = "extended" if seg in EXTENDED_SEGMENTS else "closed"
    return {"state": state, "segment": seg, "close": period.close, "open": period.open}


def closed_since(calendar: str, now: datetime, step_minutes: int) -> datetime:
    """When the current shut stretch (study segment `frozen`) began, to `step_minutes`."""
    step = timedelta(minutes=step_minutes)
    t = now
    for _ in range(int(timedelta(days=5) / step)):
        prev = t - step
        if calendar_state(calendar, prev)["state"] != "closed":
            break
        t = prev
    # The start lies within one step before t; segment edges are whole minutes.
    t = t.replace(second=0, microsecond=0)
    for _ in range(step_minutes):
        prev = t - timedelta(minutes=1)
        if calendar_state(calendar, prev)["state"] != "closed":
            break
        t = prev
    return t


# ------------------------------------------------------------------ cadence from the study
def _segment_hours(period: dict[str, Any], step_minutes: int) -> dict[str, float]:
    p = ClosedPeriod(
        datetime.fromisoformat(period["close"]), datetime.fromisoformat(period["open"])
    )
    step = timedelta(minutes=step_minutes)
    hours: dict[str, float] = {}
    t = p.close
    while t < p.open:
        seg = segment(t, p)
        hours[seg] = hours.get(seg, 0.0) + step_minutes / 60
        t += step
    return hours


def cadence(studies: Iterable[dict[str, Any]], step_minutes: int) -> dict[str, Any]:
    """Typical minutes between updates per feed, in the regular session and in extended hours.

    The study scans each closed period from 1 h before the close to 1 h after the open, so each
    period holds 2 h of regular session (`before_close`, `after_open`); extended hours are the
    `after_hours`, `overnight` and `pre_market` segments, measured on the same clock.
    """
    regular_hours = 0.0
    extended_hours = 0.0
    counts: dict[str, dict[str, int]] = {}
    periods_read = 0
    for study in studies:
        for period in study["periods"]:
            periods_read += 1
            regular_hours += 2.0
            h = _segment_hours(period, step_minutes)
            extended_hours += sum(h.get(s, 0.0) for s in EXTENDED_SEGMENTS)
        for f in study["feeds"]:
            c = counts.setdefault(f["symbol"], {"regular": 0, "extended": 0})
            for by in (f["weekend_updates_by_segment"], f["overnight_updates_by_segment"]):
                c["regular"] += by.get("before_close", 0) + by.get("after_open", 0)
                c["extended"] += sum(by.get(s, 0) for s in EXTENDED_SEGMENTS)

    def interval(n: int, hours: float) -> float | None:
        return round(hours * 60 / n, 1) if n else None

    return {
        "periods_read": periods_read,
        "regular_hours_read": round(regular_hours, 2),
        "extended_hours_read": round(extended_hours, 2),
        "feeds": {
            sym: {
                "regular_updates": c["regular"],
                "extended_updates": c["extended"],
                "typical_interval_minutes": {
                    "regular": interval(c["regular"], regular_hours),
                    "extended": interval(c["extended"], extended_hours),
                },
            }
            for sym, c in sorted(counts.items())
        },
    }


# ------------------------------------------------------------------ classification and score
def classify(state: str, updated_at: datetime | None, since: datetime | None, grace_s: int) -> str:
    """The regime for a calendar state and the feed's last post."""
    if state == "regular":
        return "regular"
    if state == "extended":
        return "extended"
    if updated_at and since and updated_at >= since + timedelta(seconds=grace_s):
        return "weekend_venue"
    return "frozen"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def staleness_mark(
    regime: str, age_s: float | None, typical_min: float | None, multiple: float, floor_min: float
) -> float | None:
    if regime == "frozen":
        return 0.0
    if age_s is None:
        return None
    if not typical_min:  # the study never saw this feed post in this regime
        typical_min = floor_min
    full = typical_min * 60
    zero = max(typical_min * multiple, floor_min) * 60
    if age_s <= full:
        return 1.0
    return _clamp(1 - (age_s - full) / max(zero - full, 1.0))


def divergence_mark(divergence: float | None, limit: float) -> float | None:
    return None if divergence is None else _clamp(1 - abs(divergence) / limit)


def depth_mark(depth_usd: float | None, floor: float, full: float) -> float | None:
    if depth_usd is None:
        return None
    if depth_usd <= floor:
        return 0.0
    return _clamp(math.log10(depth_usd / floor) / math.log10(full / floor))


def quality(cfg: AfterhoursConfig, marks: dict[str, float | None]) -> dict[str, Any]:
    """Weighted mean of the marks that could be measured, 0 to 100, with a grade."""
    w = cfg.regime.weights.model_dump()
    used = {k: v for k, v in marks.items() if v is not None and w.get(k, 0) > 0}
    total = sum(w[k] for k in used)
    score = round(100 * sum(w[k] * v for k, v in used.items()) / total) if total else None
    g = cfg.regime.grades
    grade = (
        None
        if score is None
        else "good"
        if score >= g.good
        else "fair"
        if score >= g.fair
        else "poor"
    )
    return {
        "score": score,
        "grade": grade,
        "marks": {k: None if v is None else round(v, 3) for k, v in marks.items()},
        "used": sorted(used),
    }


def _ago(seconds: float) -> str:
    if seconds < 90:
        return "under 2 minutes"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    if seconds < 172800:
        return f"{round(seconds / 3600)} hours"
    return f"{round(seconds / 86400)} days"


def _ny(t: datetime) -> str:
    local = t.astimezone(NEW_YORK)
    return f"{local:%A} {local:%H:%M} New York"


def line(
    symbol: str,
    regime: str,
    age_s: float | None,
    since: datetime | None,
    divergence: float | None,
    depth_usd: float | None,
    max_slippage: float,
) -> str:
    """One plain-English sentence about the token's price right now."""
    if age_s is None:
        return f"{symbol}: no reading from its price feed."
    dex = ""
    if divergence is not None:
        side = "above" if divergence > 0 else "below"
        dex = (
            " Its DEX price is within 0.1% of the feed."
            if abs(divergence) < 0.001
            else f" Its DEX price is {abs(divergence):.1%} {side} the feed."
        )
    depth = ""
    if depth_usd is not None:
        depth = f" About {depth_usd:,.0f} USDG of it can be sold within {max_slippage:.0%}."
    if regime == "regular":
        head = f"Regular session; the feed last posted {_ago(age_s)} ago."
    elif regime == "extended":
        head = f"Extended hours; the feed last posted {_ago(age_s)} ago."
    elif regime == "weekend_venue":
        head = (
            f"Weekend price: the exchange is shut but the feed posted {_ago(age_s)} ago, "
            "so it follows a weekend source, which can be thin."
        )
    else:
        when = f" since {_ny(since)}" if since else ""
        head = f"Frozen{when}: the feed has posted nothing for {_ago(age_s)}."
    return head + dex + depth


def regime_row(
    cfg: AfterhoursConfig,
    *,
    symbol: str,
    now: datetime,
    cal: dict[str, Any],
    since: datetime | None,
    updated_at: datetime | None,
    feed_price: float | None,
    dex_price: float | None,
    depth_usd: float | None,
    cadence_doc: dict[str, Any] | None,
) -> dict[str, Any]:
    """Regime, score and line for one token (all inputs already read)."""
    r = cfg.regime
    regime = classify(cal["state"], updated_at, since, r.window_grace_seconds)
    age = (now - updated_at).total_seconds() if updated_at else None
    divergence = (dex_price / feed_price - 1) if dex_price and feed_price else None
    typical = None
    if cadence_doc:
        feed = cadence_doc["feeds"].get(symbol)
        if feed:
            key = "regular" if regime == "regular" else "extended"
            typical = feed["typical_interval_minutes"][key]
    marks = {
        "staleness": staleness_mark(regime, age, typical, r.stale_multiple, r.stale_floor_minutes),
        "divergence": divergence_mark(divergence, cfg.schedule.triggers.divergence_pct),
        "depth": depth_mark(depth_usd, r.depth_floor_usd, r.depth_full_usd),
    }
    return {
        "regime": regime,
        "label": LABELS[regime],
        "since": since.isoformat() if since and regime in ("frozen", "weekend_venue") else None,
        "feed_age_seconds": None if age is None else round(age),
        "typical_interval_minutes": typical,
        "dex_price": dex_price,
        "divergence": None if divergence is None else round(divergence, 5),
        "depth_usd": None if depth_usd is None else round(depth_usd),
        "quality": quality(cfg, marks),
        "line": line(symbol, regime, age, since, divergence, depth_usd, cfg.vault.max_slippage),
    }
