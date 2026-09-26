"""Daily OHLC and earnings providers, tried in `data.providers` order and cached.

Prices are split- and dividend-adjusted. Stock Tokens reinvest dividends through their
multiplier, so a total-return series is the right basis for token gap risk; it also stops
ex-dividend drops from showing up as gaps.
"""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Sequence
from datetime import date
from typing import Protocol

import httpx
import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.data.cache import ParquetCache

log = logging.getLogger(__name__)
COLUMNS = ["open", "high", "low", "close", "volume"]


class PriceProvider(Protocol):
    """Returns {ticker: frame indexed by session date with COLUMNS}."""

    name: str

    def daily(self, tickers: Sequence[str], start: date) -> dict[str, pd.DataFrame]: ...


def yahoo_symbol(ticker: str) -> str:
    """Exchange ticker to Yahoo's form (BRK.B -> BRK-B)."""
    return ticker.replace(".", "-")


class YFinanceProvider:
    name = "yfinance"

    def __init__(self, batch: int, pause: float) -> None:
        self.batch = batch
        self.pause = pause

    def daily(self, tickers: Sequence[str], start: date) -> dict[str, pd.DataFrame]:
        import yfinance as yf

        out: dict[str, pd.DataFrame] = {}
        for i in range(0, len(tickers), self.batch):
            part = list(tickers[i : i + self.batch])
            raw = yf.download(
                [yahoo_symbol(t) for t in part], start=start.isoformat(), auto_adjust=True,
                progress=False, group_by="ticker", threads=True,
            )
            for t in part:
                sym = yahoo_symbol(t)
                if raw is None or raw.empty:
                    continue
                frame = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
                frame = frame.rename(columns=str.lower)[COLUMNS].dropna(subset=["open", "close"])
                if not frame.empty:
                    frame.index = pd.to_datetime(frame.index).date
                    frame.index.name = "date"
                    out[t] = frame.astype("float64")
            time.sleep(self.pause)
        return out


class StooqProvider:
    name = "stooq"

    def __init__(self, url_template: str, client: httpx.Client, pause: float) -> None:
        self.url = url_template
        self.client = client
        self.pause = pause

    def daily(self, tickers: Sequence[str], start: date) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for t in tickers:
            symbol = f"{t.lower().replace('.', '-')}.us"
            resp = self.client.get(self.url.format(symbol=symbol))
            if resp.status_code != 200 or not resp.text.startswith("Date"):
                continue
            frame = pd.read_csv(io.StringIO(resp.text)).rename(columns=str.lower)
            frame["date"] = pd.to_datetime(frame["date"]).dt.date
            frame = frame.set_index("date")
            frame = frame[frame.index >= start]
            if set(COLUMNS) <= set(frame.columns) and not frame.empty:
                # Stooq adjusts for splits and dividends by default.
                out[t] = frame[COLUMNS].astype("float64")
            time.sleep(self.pause)
        return out


class AlphaVantageProvider:
    name = "alphavantage"

    def __init__(self, url: str, key: str | None, client: httpx.Client, pause: float) -> None:
        self.url = url
        self.key = key
        self.client = client
        self.pause = pause

    def daily(self, tickers: Sequence[str], start: date) -> dict[str, pd.DataFrame]:
        if not self.key:
            return {}
        out: dict[str, pd.DataFrame] = {}
        for t in tickers:
            resp = self.client.get(
                self.url,
                params={"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": t,
                        "outputsize": "full", "datatype": "csv", "apikey": self.key},
            )
            if resp.status_code != 200 or not resp.text.startswith("timestamp"):
                continue
            raw = pd.read_csv(io.StringIO(resp.text))
            ratio = raw["adjusted_close"] / raw["close"]
            frame = pd.DataFrame(
                {"open": raw["open"] * ratio, "high": raw["high"] * ratio, "low": raw["low"] * ratio,
                 "close": raw["adjusted_close"], "volume": raw["volume"]}
            )
            frame.index = pd.to_datetime(raw["timestamp"]).dt.date
            frame.index.name = "date"
            frame = frame.sort_index()
            out[t] = frame.loc[frame.index >= start].astype("float64")
            time.sleep(self.pause)
        return out


def build_price_providers(cfg: AfterhoursConfig, client: httpx.Client) -> list[PriceProvider]:
    """Providers in configured order."""
    d = cfg.data
    made: dict[str, PriceProvider] = {
        "yfinance": YFinanceProvider(d.download_batch_size, d.request_pause_seconds),
        "stooq": StooqProvider(d.sources.stooq_daily_url, client, d.request_pause_seconds),
        "alphavantage": AlphaVantageProvider(
            d.sources.alphavantage_url, cfg.env(d.alphavantage_key_env), client, d.request_pause_seconds
        ),
    }
    return [made[name] for name in d.providers]


def load_prices(
    cfg: AfterhoursConfig,
    cache: ParquetCache,
    providers: Sequence[PriceProvider],
    tickers: Sequence[str],
    start: date,
) -> dict[str, pd.DataFrame]:
    """Prices for every ticker: fresh cache first, then providers in order, then stale cache."""
    out: dict[str, pd.DataFrame] = {}
    missing = []
    for t in tickers:
        hit = cache.get(f"prices/{t}")
        if hit is not None:
            out[t] = hit
        else:
            missing.append(t)
    for provider in providers:
        if not missing:
            break
        log.info("fetching %d tickers from %s", len(missing), provider.name)
        try:
            got = provider.daily(missing, start)
        except Exception as exc:  # provider down or rate limited: fall through
            log.warning("%s failed: %s", provider.name, exc)
            continue
        for t, frame in got.items():
            cache.put(f"prices/{t}", frame, provider.name)
            out[t] = frame
        missing = [t for t in missing if t not in got]
    for t in list(missing):
        stale = cache.get(f"prices/{t}", allow_stale=True)
        if stale is not None:
            out[t] = stale
            missing.remove(t)
    if missing:
        log.warning("no prices for %d tickers: %s", len(missing), ", ".join(missing[:20]))
    return out
