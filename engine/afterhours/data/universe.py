"""Training universe (S&P 500 constituents or an explicit list) plus the Stock Token tickers."""

from __future__ import annotations

import io
import json
import logging

import httpx
import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.data.cache import ParquetCache
from afterhours.deployments import load_discovered

log = logging.getLogger(__name__)


def sp500_tickers(cfg: AfterhoursConfig, cache: ParquetCache, client: httpx.Client) -> list[str]:
    """Current S&P 500 constituents from the configured page (survivorship bias noted in docs)."""
    key = "universe/sp500"
    hit = cache.get(key)
    if hit is None:
        try:
            html = client.get(cfg.data.sources.sp500_constituents_url).text
            table = pd.read_html(io.StringIO(html))[0]
            hit = pd.DataFrame({"ticker": table["Symbol"].astype(str).str.strip(),
                                "sector": table.get("GICS Sector", pd.Series(dtype=str)).astype(str)})
            cache.put(key, hit, cfg.data.sources.sp500_constituents_url)
        except Exception as exc:
            log.warning("S&P 500 list fetch failed (%s); using cached copy", exc)
            hit = cache.get(key, allow_stale=True)
            if hit is None:
                raise
    return sorted(hit["ticker"].tolist())


def sectors(cache: ParquetCache) -> dict[str, str]:
    """Ticker to GICS sector where the constituents table has it."""
    hit = cache.get("universe/sp500", allow_stale=True)
    if hit is None:
        return {}
    return dict(zip(hit["ticker"], hit["sector"], strict=True))


def stock_token_tickers(cfg: AfterhoursConfig) -> tuple[list[str], list[str]]:
    """(all Stock Tokens with a verified feed, the selected ones) from the discovered file."""
    doc = load_discovered(cfg)
    return list(doc.get("stock_tokens", {})), list(doc.get("selected", []))


def training_universe(cfg: AfterhoursConfig, cache: ParquetCache, client: httpx.Client) -> list[str]:
    """Training tickers: the configured base universe plus every Stock Token with a feed."""
    u = cfg.universe
    base = u.explicit_tickers if u.training_universe_source == "explicit" else sp500_tickers(cfg, cache, client)
    tokens, _ = stock_token_tickers(cfg)
    universe = sorted(set(base) | set(tokens))
    log.info("universe: %d tickers (%d base, %d stock tokens)", len(universe), len(base), len(tokens))
    return universe


def describe(universe: list[str]) -> str:
    """Short JSON description for manifests."""
    return json.dumps({"count": len(universe), "first": universe[:5]})
