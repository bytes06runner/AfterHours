"""Conformalized quantile regression (CQR) for a lower quantile, Mondrian by segment.

For a lower-quantile forecast q(x) at level alpha, the conformity score is s = q(x) - y
(positive when the outcome fell below the forecast). On a calibration set, the correction
c_k for segment k is the ceil((n_k + 1)(1 - alpha)) / n_k empirical quantile of the scores,
and the calibrated forecast is q(x) - c_k. With exchangeable data this gives a miss rate of
at most alpha within each segment (Romano, Patterson and Candes 2019; Vovk's Mondrian CP).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def _conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = scores.size
    if n == 0:
        return 0.0
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level, method="higher"))


@dataclass
class MondrianCQR:
    """Per-segment additive corrections for one quantile level."""

    alpha: float
    segments: Sequence[str]
    corrections: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def fit(self, q_cal: np.ndarray, y_cal: np.ndarray, seg_cal: pd.Series) -> MondrianCQR:
        """Learn corrections from calibration forecasts and outcomes."""
        scores = q_cal - y_cal
        seg = seg_cal.to_numpy()
        overall = _conformal_quantile(scores, self.alpha)
        for s in self.segments:
            mask = seg == s
            self.counts[s] = int(mask.sum())
            self.corrections[s] = (
                _conformal_quantile(scores[mask], self.alpha) if mask.any() else overall
            )
        self.corrections["_overall"] = overall
        return self

    def apply(self, q: np.ndarray, seg: pd.Series) -> np.ndarray:
        """Calibrated forecasts q - c_segment."""
        c = seg.map(self.corrections).fillna(self.corrections["_overall"]).to_numpy(dtype=float)
        return q - c
