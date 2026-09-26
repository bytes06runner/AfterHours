"""Earnings events with timing: before the open (bmo), after the close (amc) or unknown."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import date, timedelta

import httpx
import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.data.cache import ParquetCache
from afterhours.data.providers import yahoo_symbol

log = logging.getLogger(__name__)
EARNINGS_COLUMNS = ["date", "timing"]  # timing in {"bmo", "amc", "dmh", "unknown"}


def timing_from_timestamp(ts: pd.Timestamp) -> str:
    """Classify a New York timestamp: before 09:30 bmo, from 16:00 amc, else during hours.

    Midnight means the provider did not know the time.
    """
    local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
    minutes = local.hour * 60 + local.minute
    if minutes == 0:
        return "unknown"
    if minutes < 9 * 60 + 30:
        return "bmo"
    if minutes >= 16 * 60:
        return "amc"
    return "dmh"


def yfinance_earnings(ticker: str, limit: int) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.Ticker(yahoo_symbol(ticker)).get_earnings_dates(limit=limit)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=EARNINGS_COLUMNS)
    stamps = pd.to_datetime(raw.index)
    return pd.DataFrame(
        {"date": [s.tz_convert("America/New_York").date() for s in stamps],
         "timing": [timing_from_timestamp(s) for s in stamps]}
    )


def finnhub_earnings(client: httpx.Client, url: str, key: str, ticker: str, start: date) -> pd.DataFrame:
    resp = client.get(
        f"{url}/calendar/earnings",
        params={"symbol": ticker, "from": start.isoformat(),
                "to": (date.today() + timedelta(days=120)).isoformat(), "token": key},
    )
    resp.raise_for_status()
    rows = resp.json().get("earningsCalendar", [])
    return pd.DataFrame(
        {"date": [date.fromisoformat(r["date"]) for r in rows],
         "timing": [r.get("hour") if r.get("hour") in ("bmo", "amc", "dmh") else "unknown" for r in rows]}
    )


def load_earnings(
    cfg: AfterhoursConfig,
    cache: ParquetCache,
    client: httpx.Client,
    tickers: Sequence[str],
    start: date,
) -> dict[str, pd.DataFrame]:
    """Earnings per ticker from the first provider that answers; cached."""
    d = cfg.data
    out: dict[str, pd.DataFrame] = {}
    finnhub_key = cfg.env(d.finnhub_key_env)
    for i, t in enumerate(tickers):
        key = f"earnings/{t}"
        hit = cache.get(key)
        if hit is not None:
            out[t] = hit
            continue
        frame: pd.DataFrame | None = None
        for provider in d.earnings_providers:
            try:
                if provider == "yfinance":
                    frame = yfinance_earnings(t, d.earnings_history_limit)
                elif provider == "finnhub" and finnhub_key:
                    frame = finnhub_earnings(client, d.sources.finnhub_url, finnhub_key, t, start)
                else:
                    continue
            except Exception as exc:
                log.warning("earnings %s via %s failed: %s", t, provider, exc)
                frame = None
                continue
            if frame is not None and not frame.empty:
                cache.put(key, frame.drop_duplicates().reset_index(drop=True), provider)
                break
        if frame is None or frame.empty:
            stale = cache.get(key, allow_stale=True)
            frame = stale if stale is not None else pd.DataFrame(columns=EARNINGS_COLUMNS)
        out[t] = frame
        time.sleep(d.request_pause_seconds)
        if i % 50 == 0:
            log.info("earnings %d/%d", i, len(tickers))
    return out
