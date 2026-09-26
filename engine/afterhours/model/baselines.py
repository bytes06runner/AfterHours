"""The three baselines from SPEC 7.4, each predicting the alpha-quantile of the gap."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def global_segment(train: pd.DataFrame, test: pd.DataFrame, alpha: float) -> np.ndarray:
    """(a) One global empirical quantile per segment."""
    q = train.groupby("segment")["g"].quantile(alpha)
    fallback = float(train["g"].quantile(alpha))
    return test["segment"].map(q).fillna(fallback).to_numpy(dtype=float)


def ticker_segment(
    train: pd.DataFrame, test: pd.DataFrame, alpha: float, min_rows: int
) -> np.ndarray:
    """(b) Per-ticker empirical quantile per segment over all earlier data.

    Falls back to the global segment quantile when a (ticker, segment) cell has fewer than
    `min_rows` observations.
    """
    grouped = train.groupby(["ticker", "segment"])["g"]
    q = grouped.quantile(alpha)
    n = grouped.size()
    q = q[n >= min_rows]
    keys = pd.MultiIndex.from_arrays([test["ticker"], test["segment"]])
    values = q.reindex(keys).to_numpy(dtype=float)
    fallback = global_segment(train, test, alpha)
    return np.where(np.isnan(values), fallback, values)


def ewma_normal(test: pd.DataFrame, alpha: float) -> np.ndarray:
    """(c) EWMA daily volatility, normal quantile, scaled by closed hours / 24."""
    sigma = test["ewma_sigma"].to_numpy(dtype=float) * np.sqrt(
        test["hours_closed"].to_numpy(dtype=float) / 24
    )
    median_sigma = np.nanmedian(sigma)
    sigma = np.where(np.isnan(sigma), median_sigma, sigma)
    return np.asarray(np.expm1(norm.ppf(alpha) * sigma), dtype=float)
