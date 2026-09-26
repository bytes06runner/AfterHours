"""The gap dataset: one row per (ticker, closed period).

A closed period runs from one session's close to the next session's open. Its target is
`g = open_next / close_prev - 1`. Features use only information available at `close_prev`;
`tests/test_dataset.py` enforces that by perturbing the future and checking nothing moves.

Segments, first match wins:
- `earnings`  an earnings event falls in the period (after the close of `session_prev`, or
              before the open of `session_next`; unknown-time events mark both neighbours)
- `holiday`   a weekday inside the period is not a session
- `weekend`   the period contains a Saturday
- `overnight` everything else
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

SEGMENTS = ["earnings", "holiday", "weekend", "overnight"]
FEATURES = [
    "hours_closed",
    "seg_earnings",
    "seg_holiday",
    "seg_weekend",
    "seg_overnight",
    "rv5",
    "rv20",
    "rv60",
    "hist_q01",
    "hist_q05",
    "hist_seg_q05",
    "vix",
    "vix_chg5",
    "days_since_earnings",
    "market_ret1",
    "ret1",
    "sector_code",
    "ewma_sigma",
]


def sessions(calendar: str, start: date, end: date) -> pd.DataFrame:
    """Exchange sessions with UTC open and close times, indexed by session date."""
    sched = mcal.get_calendar(calendar).schedule(start_date=start, end_date=end)
    out = pd.DataFrame(
        {
            "open": sched["market_open"].dt.tz_convert("UTC"),
            "close": sched["market_close"].dt.tz_convert("UTC"),
        }
    )
    out.index = pd.Index([d.date() for d in sched.index], name="session")
    return out


def closed_periods(sess: pd.DataFrame) -> pd.DataFrame:
    """Periods between consecutive sessions with their calendar segment (before earnings)."""
    days = list(sess.index)
    rows = []
    session_set = set(days)
    for prev, nxt in pairwise(days):
        between = [prev + timedelta(days=k) for k in range(1, (nxt - prev).days)]
        weekday_gap = any(d.weekday() < 5 and d not in session_set for d in between)
        has_saturday = any(d.weekday() == 5 for d in between)
        rows.append(
            {
                "session_prev": prev,
                "session_next": nxt,
                "close_prev": sess.at[prev, "close"],
                "open_next": sess.at[nxt, "open"],
                "calendar_segment": "holiday"
                if weekday_gap
                else "weekend"
                if has_saturday
                else "overnight",
            }
        )
    out = pd.DataFrame(rows)
    out["hours_closed"] = (out["open_next"] - out["close_prev"]).dt.total_seconds() / 3600
    return out


def earnings_flags(periods: pd.DataFrame, events: pd.DataFrame) -> pd.Series:
    """Boolean per period: does an earnings event fall inside it?"""
    flags = pd.Series(False, index=periods.index)
    if events.empty:
        return flags
    by_prev = {d: i for i, d in zip(periods.index, periods["session_prev"], strict=True)}
    by_next = {d: i for i, d in zip(periods.index, periods["session_next"], strict=True)}
    starts = periods["session_prev"].to_numpy()
    for day, timing in zip(events["date"], events["timing"], strict=True):
        if day in by_prev and timing in ("amc", "unknown"):
            flags.at[by_prev[day]] = True
        if day in by_next and timing in ("bmo", "unknown"):
            flags.at[by_next[day]] = True
        if day not in by_prev and day not in by_next:
            # Reported on a non-session day: the period that contains it.
            pos = int(np.searchsorted(starts, day)) - 1
            if 0 <= pos < len(periods) and periods.at[periods.index[pos], "session_next"] > day:
                flags.at[periods.index[pos]] = True
    return flags


def _expanding_quantile_shifted(values: pd.Series, q: float, min_periods: int) -> pd.Series:
    """Quantile of all *earlier* values (the current row is excluded)."""
    return values.shift(1).expanding(min_periods=min_periods).quantile(q)


def build_ticker_rows(
    ticker: str,
    prices: pd.DataFrame,
    periods: pd.DataFrame,
    events: pd.DataFrame,
    *,
    vix: pd.Series,
    market_close: pd.Series,
    sector_code: int,
    min_history: int = 20,
    ewma_lambda: float = 0.94,
) -> pd.DataFrame:
    """Dataset rows for one ticker. `prices` is indexed by session date."""
    px = prices.sort_index()
    p = periods[
        periods["session_prev"].isin(px.index) & periods["session_next"].isin(px.index)
    ].copy()
    if p.empty:
        return p
    p["ticker"] = ticker
    close_prev = px["close"].reindex(p["session_prev"]).to_numpy()
    open_next = px["open"].reindex(p["session_next"]).to_numpy()
    p["g"] = open_next / close_prev - 1
    earn = earnings_flags(p, events)
    p["segment"] = np.where(earn, "earnings", p["calendar_segment"])
    for seg in SEGMENTS:
        p[f"seg_{seg}"] = (p["segment"] == seg).astype(float)

    # Realised volatility of close-to-close log returns up to and including session_prev.
    logret = np.log(px["close"]).diff()
    for n in (5, 20, 60):
        rv = logret.rolling(n, min_periods=max(3, n // 2)).std() * np.sqrt(252)
        p[f"rv{n}"] = rv.reindex(p["session_prev"]).to_numpy()
    p["ret1"] = px["close"].pct_change().reindex(p["session_prev"]).to_numpy()
    # RiskMetrics-style EWMA daily volatility (not a model feature; baseline (c) uses it).
    ewma_var = (logret**2).ewm(alpha=1 - ewma_lambda, min_periods=20).mean()
    p["ewma_sigma"] = np.sqrt(ewma_var).reindex(p["session_prev"]).to_numpy()

    # The ticker's own earlier gaps. Row k's gap ended at open(session_next_k) which is after
    # close_prev_k, so only gaps of rows before k are allowed: shift(1).
    p = p.sort_values("session_prev")
    p["hist_q01"] = _expanding_quantile_shifted(p["g"], 0.01, min_history).to_numpy()
    p["hist_q05"] = _expanding_quantile_shifted(p["g"], 0.05, min_history).to_numpy()
    p["hist_seg_q05"] = (
        p.groupby("segment")["g"]
        .transform(lambda s: _expanding_quantile_shifted(s, 0.05, max(8, min_history // 2)))
        .to_numpy()
    )

    p["vix"] = vix.reindex(p["session_prev"]).to_numpy()
    p["vix_chg5"] = (vix / vix.shift(5) - 1).reindex(p["session_prev"]).to_numpy()
    p["market_ret1"] = market_close.pct_change().reindex(p["session_prev"]).to_numpy()

    past = sorted(d for d in events["date"]) if not events.empty else []
    idx = (
        np.searchsorted(np.array(past, dtype="object"), p["session_prev"].to_numpy(), side="right")
        if past
        else None
    )
    if idx is not None:
        last = [past[i - 1] if i > 0 else None for i in idx]
        p["days_since_earnings"] = [
            float((sp - d).days) if d is not None else np.nan
            for sp, d in zip(p["session_prev"], last, strict=True)
        ]
    else:
        p["days_since_earnings"] = np.nan
    p["sector_code"] = float(sector_code)
    return p


def build_dataset(
    prices: Mapping[str, pd.DataFrame],
    earnings: Mapping[str, pd.DataFrame],
    sess: pd.DataFrame,
    *,
    vix_ticker: str,
    market_ticker: str,
    sectors: Mapping[str, str],
    ewma_lambda: float = 0.94,
) -> pd.DataFrame:
    """Rows for every ticker with prices, excluding the VIX series itself."""
    periods = closed_periods(sess)
    vix = prices[vix_ticker]["close"].sort_index()
    market = prices[market_ticker]["close"].sort_index()
    sector_names = sorted({s for s in sectors.values() if s})
    codes = {name: i for i, name in enumerate(sector_names)}
    frames = []
    for ticker, px in prices.items():
        if ticker == vix_ticker:
            continue
        events = earnings.get(ticker, pd.DataFrame(columns=["date", "timing"]))
        rows = build_ticker_rows(
            ticker,
            px,
            periods,
            events,
            vix=vix,
            market_close=market,
            sector_code=codes.get(sectors.get(ticker, ""), -1),
            ewma_lambda=ewma_lambda,
        )
        if not rows.empty:
            frames.append(rows)
    data = pd.concat(frames, ignore_index=True)
    data = data[np.isfinite(data["g"])]
    out: pd.DataFrame = data.sort_values(["session_prev", "ticker"]).reset_index(drop=True)
    return out
