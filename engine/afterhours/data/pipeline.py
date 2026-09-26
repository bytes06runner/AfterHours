"""Build the gap dataset end to end: universe, prices, earnings, sessions, rows."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.data import universe as uni
from afterhours.data.cache import ParquetCache
from afterhours.data.earnings import load_earnings
from afterhours.data.providers import build_price_providers, load_prices
from afterhours.features.dataset import build_dataset, sessions

log = logging.getLogger(__name__)
DATASET_KEY = "dataset/gaps"


def make_cache(cfg: AfterhoursConfig) -> ParquetCache:
    """The configured Parquet cache."""
    return ParquetCache(cfg.path(cfg.data.cache_dir), timedelta(hours=cfg.data.cache_max_age_hours))


def vault_symbols(cfg: AfterhoursConfig) -> list[str]:
    """The stocks the vault lends against, as chosen by the backtest."""
    results = cfg.path(cfg.paths.artifacts_dir) / "backtest" / "results.json"
    selected: list[str] = json.loads(results.read_text())["selected"]
    return selected


def fetch_symbols(cfg: AfterhoursConfig, symbols: list[str]) -> dict[str, int]:
    """Prices and earnings for a few symbols only (what the live risk engine reads).

    A clean clone has no cache; `make demo` calls this so it does not need the full M2 build.
    Returns price rows per symbol.
    """
    cache = make_cache(cfg)
    start = date.fromisoformat(cfg.universe.history_start)
    with httpx.Client(timeout=60, headers={"user-agent": cfg.discovery.user_agent}, follow_redirects=True) as client:
        prices = load_prices(cfg, cache, build_price_providers(cfg, client), symbols, start)
        load_earnings(cfg, cache, client, [s for s in symbols if s in prices], start)
    missing = [s for s in symbols if s not in prices]
    if missing:
        raise RuntimeError(f"no prices for {', '.join(missing)}")
    return {s: len(prices[s]) for s in symbols}


def build(cfg: AfterhoursConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch (or reuse) everything and build the dataset. Returns (dataset, data manifest)."""
    cache = make_cache(cfg)
    start = date.fromisoformat(cfg.universe.history_start)
    with httpx.Client(timeout=60, headers={"user-agent": cfg.discovery.user_agent}, follow_redirects=True) as client:
        tickers = uni.training_universe(cfg, cache, client)
        wanted = sorted(set(tickers) | {cfg.data.vix_ticker, cfg.data.market_ticker})
        prices = load_prices(cfg, cache, build_price_providers(cfg, client), wanted, start)
        earnings = load_earnings(cfg, cache, client, [t for t in tickers if t in prices], start)
    for needed in (cfg.data.vix_ticker, cfg.data.market_ticker):
        if needed not in prices:
            raise RuntimeError(f"no prices for {needed}; cannot build features")
    sess = sessions(cfg.data.exchange_calendar, start, datetime.now(UTC).date())
    data = build_dataset(
        prices, earnings, sess, vix_ticker=cfg.data.vix_ticker, market_ticker=cfg.data.market_ticker,
        sectors=uni.sectors(cache),
        ewma_lambda=cfg.model.baselines.ewma_lambda,
    )
    sources = Counter((cache.entry(f"prices/{t}") or {}).get("source", "missing") for t in wanted)
    esources = Counter((cache.entry(f"earnings/{t}") or {}).get("source", "none") for t in tickers)
    timing = Counter(t for frame in earnings.values() for t in frame.get("timing", []))
    manifest = {
        "built_at": datetime.now(UTC).isoformat(),
        "history_start": start.isoformat(),
        "calendar": cfg.data.exchange_calendar,
        "tickers_requested": len(tickers),
        "tickers_with_rows": int(data["ticker"].nunique()),
        "rows": len(data),
        "price_sources": dict(sources),
        "earnings_sources": dict(esources),
        "earnings_timing_counts": dict(timing),
        "universe_note": "current S&P 500 constituents plus Stock Tokens; survivorship bias applies",
    }
    cache.put(DATASET_KEY, data, "afterhours data build")
    return data, manifest
