"""Tests for folds, conformal calibration, baselines and metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from afterhours.model import baselines
from afterhours.model.conformal import MondrianCQR
from afterhours.model.metrics import miss_rate, pinball
from afterhours.model.walkforward import make_folds


def test_folds_roll_by_test_years() -> None:
    folds = make_folds(list(range(2010, 2027)), train=6, calibrate=1, test=1)
    assert folds[0].train == (2010, 2016)
    assert folds[0].calibrate == (2016, 2017)
    assert folds[0].test == (2017, 2018)
    assert folds[-1].test == (2026, 2027)
    assert len(folds) == 10


def test_pinball_and_miss_rate() -> None:
    y = np.array([-0.1, 0.0, 0.1])
    q = np.array([-0.05, -0.05, -0.05])
    assert miss_rate(y, q) == pytest.approx(1 / 3)
    # alpha 0.05: miss costs 0.95 * 0.05, hits cost 0.05 * gap above q
    assert pinball(y, q, 0.05) == pytest.approx((0.95 * 0.05 + 0.05 * 0.05 + 0.05 * 0.15) / 3)


def test_mondrian_cqr_hits_target_per_segment() -> None:
    rng = np.random.default_rng(0)
    n = 40_000
    seg = pd.Series(np.where(rng.random(n) < 0.2, "earnings", "overnight"))
    scale = np.where(seg == "earnings", 0.08, 0.01)
    y = rng.standard_t(4, n) * scale
    q_raw = np.full(n, -0.01)  # badly miscalibrated for earnings
    half = n // 2
    cqr = MondrianCQR(0.01, ["earnings", "overnight"]).fit(q_raw[:half], y[:half], seg[:half])
    q = cqr.apply(q_raw[half:], seg[half:].reset_index(drop=True))
    y_te, s_te = y[half:], seg[half:].to_numpy()
    for name in ("earnings", "overnight"):
        m = s_te == name
        assert miss_rate(y_te[m], q[m]) == pytest.approx(0.01, abs=0.006)


def test_baselines_shapes_and_fallback() -> None:
    train = pd.DataFrame(
        {
            "ticker": ["A"] * 50 + ["B"] * 5,
            "segment": ["weekend"] * 55,
            "g": np.linspace(-0.1, 0.1, 55),
        }
    )
    test = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "segment": ["weekend", "weekend", "earnings"],
            "ewma_sigma": [0.02, 0.02, np.nan],
            "hours_closed": [65.5, 65.5, 17.5],
        }
    )
    glob = baselines.global_segment(train, test, 0.05)
    tick = baselines.ticker_segment(train, test, 0.05, min_rows=30)
    assert tick[1] == glob[1]  # B has too few rows: falls back to the global segment
    assert tick[0] != glob[0]
    ew = baselines.ewma_normal(test, 0.01)
    assert ew.shape == (3,)
    assert ew[0] < 0
