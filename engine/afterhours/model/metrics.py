"""Metrics for lower-tail quantile forecasts."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def pinball(y: ArrayLike, q: ArrayLike, alpha: float) -> float:
    """Mean pinball (quantile) loss of predictions `q` for level `alpha`."""
    y_arr = np.asarray(y, dtype=float)
    q_arr = np.asarray(q, dtype=float)
    diff = y_arr - q_arr
    return float(np.mean(np.maximum(alpha * diff, (alpha - 1) * diff)))


def miss_rate(y: ArrayLike, q: ArrayLike) -> float:
    """Share of outcomes below the predicted quantile. Target: alpha."""
    return float(np.mean(np.asarray(y, dtype=float) < np.asarray(q, dtype=float)))


def mean_drop(q: ArrayLike) -> float:
    """Mean predicted bad-case drop (the one-sided band width): mean of -q."""
    return float(np.mean(-np.asarray(q, dtype=float)))
