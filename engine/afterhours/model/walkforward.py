"""Walk-forward evaluation of the gap model against the baselines (SPEC 7.4).

For each fold, by calendar year of `session_prev`:
  train     `train_years` years
  calibrate the next `calibrate_years` years (Mondrian CQR corrections)
  test      the next `test_years` years (held out)

Everything reported comes from test years only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.features.dataset import FEATURES, SEGMENTS
from afterhours.model import baselines
from afterhours.model.conformal import MondrianCQR
from afterhours.model.metrics import mean_drop, miss_rate, pinball

log = logging.getLogger(__name__)
BASELINES = ("global_segment", "ticker_segment", "ewma_normal")


@dataclass(frozen=True)
class Fold:
    """Year ranges for one fold (inclusive start, exclusive end)."""

    train: tuple[int, int]
    calibrate: tuple[int, int]
    test: tuple[int, int]


def make_folds(years: Sequence[int], train: int, calibrate: int, test: int) -> list[Fold]:
    """Rolling folds that fit inside `years`; the last test window may be a partial year."""
    first, last = min(years), max(years)
    folds = []
    start = first
    while start + train + calibrate <= last:
        t0 = start + train + calibrate
        folds.append(Fold((start, start + train), (start + train, t0), (t0, t0 + test)))
        start += test
    return folds


def _years(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["session_prev"]).dt.year


def _slice(frame: pd.DataFrame, years: pd.Series, span: tuple[int, int]) -> pd.DataFrame:
    return frame[(years >= span[0]) & (years < span[1])]


def fit_lgbm(cfg: AfterhoursConfig, train: pd.DataFrame, alpha: float) -> Any:
    """One LightGBM quantile model."""
    import lightgbm as lgb

    lg = cfg.model.lightgbm
    model = lgb.LGBMRegressor(
        objective="quantile",
        alpha=alpha,
        num_leaves=lg.num_leaves,
        learning_rate=lg.learning_rate,
        n_estimators=lg.n_estimators,
        min_child_samples=lg.min_child_samples,
        random_state=cfg.model.seed,
        n_jobs=cfg.model.n_jobs,
        verbose=-1,
    )
    model.fit(train[FEATURES], train["g"])
    return model


def predict_all(
    cfg: AfterhoursConfig, train: pd.DataFrame, target: pd.DataFrame, alpha: float, model: Any
) -> dict[str, np.ndarray]:
    """Raw forecasts of the model and every baseline for `target` rows."""
    return {
        "model": np.asarray(model.predict(target[FEATURES]), dtype=float),
        "global_segment": baselines.global_segment(train, target, alpha),
        "ticker_segment": baselines.ticker_segment(
            train, target, alpha, cfg.model.baselines.min_ticker_segment_rows
        ),
        "ewma_normal": baselines.ewma_normal(target, alpha),
    }


def score(y: np.ndarray, q: np.ndarray, seg: pd.Series, alpha: float) -> dict[str, Any]:
    """Miss rate, pinball loss and mean drop, overall and per segment."""
    out: dict[str, Any] = {
        "overall": {
            "n": int(y.size),
            "miss_rate": miss_rate(y, q),
            "pinball": pinball(y, q, alpha),
            "mean_drop": mean_drop(q),
        }
    }
    s = seg.to_numpy()
    for name in SEGMENTS:
        m = s == name
        if m.any():
            out[name] = {
                "n": int(m.sum()),
                "miss_rate": miss_rate(y[m], q[m]),
                "pinball": pinball(y[m], q[m], alpha),
                "mean_drop": mean_drop(q[m]),
            }
    return out


def run(cfg: AfterhoursConfig, data: pd.DataFrame) -> dict[str, Any]:
    """Evaluate every fold; return per-fold results and pooled held-out predictions."""
    wf = cfg.model.walk_forward
    years = _years(data)
    folds = make_folds(sorted(years.unique()), wf.train_years, wf.calibrate_years, wf.test_years)
    held: list[pd.DataFrame] = []
    fold_docs = []
    importances: dict[str, float] = dict.fromkeys(FEATURES, 0.0)
    for fold in folds:
        tr, ca, te = (_slice(data, years, span) for span in (fold.train, fold.calibrate, fold.test))
        if te.empty:
            continue
        t0 = time.time()
        fold_out = te[["ticker", "session_prev", "segment", "g"]].copy()
        doc: dict[str, Any] = {
            "fold": fold.__dict__,
            "rows": {"train": len(tr), "calibrate": len(ca), "test": len(te)},
        }
        for alpha in cfg.model.quantiles:
            model = fit_lgbm(cfg, tr, alpha)
            for f, v in zip(FEATURES, model.booster_.feature_importance("gain"), strict=True):
                importances[f] += float(v)
            raw_cal = predict_all(cfg, tr, ca, alpha, model)
            raw_te = predict_all(cfg, tr, te, alpha, model)
            doc[f"q{alpha:g}"] = {}
            for name in ("model", *BASELINES):
                cqr = MondrianCQR(alpha, SEGMENTS).fit(
                    raw_cal[name], ca["g"].to_numpy(), ca["segment"]
                )
                cal_te = cqr.apply(raw_te[name], te["segment"])
                fold_out[f"{name}_raw_q{alpha:g}"] = raw_te[name]
                fold_out[f"{name}_q{alpha:g}"] = cal_te
                doc[f"q{alpha:g}"][name] = {
                    "raw": score(te["g"].to_numpy(), raw_te[name], te["segment"], alpha),
                    "calibrated": score(te["g"].to_numpy(), cal_te, te["segment"], alpha),
                    "corrections": cqr.corrections,
                }
        doc["seconds"] = round(time.time() - t0, 1)
        log.info("fold test=%s rows=%d in %.0fs", fold.test, len(te), doc["seconds"])
        fold_docs.append(doc)
        held.append(fold_out)
    pooled = pd.concat(held, ignore_index=True) if held else pd.DataFrame()
    total = sum(importances.values()) or 1.0
    return {
        "folds": fold_docs,
        "pooled": pooled,
        "feature_importance_gain_share": {
            k: v / total for k, v in sorted(importances.items(), key=lambda kv: -kv[1])
        },
    }


def acceptance(cfg: AfterhoursConfig, pooled: pd.DataFrame) -> dict[str, Any]:
    """SPEC 7.4 acceptance on pooled held-out predictions at `target_alpha`."""
    a = cfg.model.target_alpha
    acc = cfg.model.acceptance
    y = pooled["g"].to_numpy()
    seg = pooled["segment"]
    results: dict[str, Any] = {"alpha": a}
    scores = {
        name: score(y, pooled[f"{name}_q{a:g}"].to_numpy(), seg, a)
        for name in ("model", *BASELINES)
    }
    results["held_out"] = scores
    cov_all = scores["model"]["overall"]["miss_rate"]
    cov_earn = scores["model"].get("earnings", {}).get("miss_rate", float("nan"))
    results["coverage_overall"] = {
        "miss_rate": cov_all,
        "target": a,
        "tolerance": acc.overall_coverage_tolerance,
        "pass": abs(cov_all - a) <= acc.overall_coverage_tolerance,
    }
    results["coverage_earnings"] = {
        "miss_rate": cov_earn,
        "target": a,
        "tolerance": acc.earnings_coverage_tolerance,
        "pass": bool(abs(cov_earn - a) <= acc.earnings_coverage_tolerance),
    }
    results["pinball_vs_baselines"] = {
        b: {
            "model": scores["model"]["overall"]["pinball"],
            "baseline": scores[b]["overall"]["pinball"],
            "pass": scores["model"]["overall"]["pinball"] < scores[b]["overall"]["pinball"],
        }
        for b in BASELINES
    }
    passed = (
        results["coverage_overall"]["pass"]
        and results["coverage_earnings"]["pass"]
        and all(v["pass"] for v in results["pinball_vs_baselines"].values())
    )
    results["passed"] = passed
    best_baseline = min(BASELINES, key=lambda b: scores[b]["overall"]["pinball"])
    results["shipped"] = "model" if passed else best_baseline
    if not passed:
        results["fallback_reason"] = "the LightGBM model missed at least one acceptance criterion"
    return results


def calibration_curve(
    pooled: pd.DataFrame, quantiles: Sequence[float], name: str
) -> dict[str, Any]:
    """Nominal vs observed miss rate per segment for the calibrated forecasts of `name`."""
    out: dict[str, Any] = {}
    for seg in ["overall", *SEGMENTS]:
        part = pooled if seg == "overall" else pooled[pooled["segment"] == seg]
        if part.empty:
            continue
        out[seg] = [
            {"nominal": q, "observed": miss_rate(part["g"], part[f"{name}_q{q:g}"]), "n": len(part)}
            for q in quantiles
        ]
    return out


def model_version(paths: Sequence[Path], extra: dict[str, Any]) -> str:
    """sha256 over saved model files and the calibration/feature metadata."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.read_bytes())
    h.update(json.dumps(extra, sort_keys=True).encode())
    return h.hexdigest()[:16]
