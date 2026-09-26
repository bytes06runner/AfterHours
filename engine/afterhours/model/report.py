"""Train, evaluate and publish the gap model: `artifacts/model/`.

- `report_card.json`: folds, pooled held-out metrics per segment, acceptance, what shipped
- `calibration_<segment>.png`: nominal vs observed miss rate
- `lgbm_q<alpha>.txt` and `production.json`: the production model and its CQR corrections
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.features.dataset import FEATURES, SEGMENTS
from afterhours.features.gaps import code_version
from afterhours.model import walkforward as wf
from afterhours.model.conformal import MondrianCQR

log = logging.getLogger(__name__)


def train_production(
    cfg: AfterhoursConfig, data: pd.DataFrame, out: Path, shipped: str
) -> dict[str, Any]:
    """Fit on the latest train window and calibrate every method on the latest year.

    The API serves `shipped`: the LightGBM model if it passed acceptance, else the best
    baseline. Corrections for every method are stored so the report card can show them all.
    """
    w = cfg.model.walk_forward
    years = pd.to_datetime(data["session_prev"]).dt.year
    last = int(years.max())
    cal_span = (last - w.calibrate_years + 1, last + 1)
    train_span = (cal_span[0] - w.train_years, cal_span[0])
    train = data[(years >= train_span[0]) & (years < train_span[1])]
    cal = data[(years >= cal_span[0]) & (years < cal_span[1])]
    norm = cfg.model.conformal.normalize == "ewma"
    files: list[Path] = []
    corrections: dict[str, dict[str, dict[str, float]]] = {}
    tables: dict[str, dict[str, Any]] = {}
    for alpha in cfg.model.quantiles:
        model = wf.fit_lgbm(cfg, train, alpha)
        path = out / f"lgbm_q{alpha:g}.txt"
        model.booster_.save_model(str(path))
        files.append(path)
        raw = wf.predict_all(cfg, train, cal, alpha, model)
        for method, preds in raw.items():
            corrections.setdefault(method, {})[f"{alpha:g}"] = (
                MondrianCQR(alpha, SEGMENTS)
                .fit(
                    preds, cal["g"].to_numpy(), cal["segment"], wf.gap_scale(cal) if norm else None
                )
                .corrections
            )
        # Quantile tables the two empirical baselines need at serving time.
        tables.setdefault("global_segment", {})[f"{alpha:g}"] = (
            train.groupby("segment")["g"].quantile(alpha).to_dict()
        )
    meta: dict[str, Any] = {
        "shipped": shipped,
        "alpha": cfg.model.target_alpha,
        "target_scaling": cfg.model.target_scaling,
        "conformal_normalize": cfg.model.conformal.normalize,
        "ewma_lambda": cfg.model.baselines.ewma_lambda,
        "features": FEATURES,
        "segments": SEGMENTS,
        "quantiles": cfg.model.quantiles,
        "train_years": list(train_span),
        "calibrate_years": list(cal_span),
        "corrections": corrections,
        "tables": tables,
        "rows": {"train": len(train), "calibrate": len(cal)},
    }
    meta["model_version"] = wf.model_version(files, meta)
    (out / "production.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def calibration_figures(curves: dict[str, Any], out: Path, method: str) -> list[Path]:
    """One nominal-vs-observed plot per segment for `method`."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written = []
    for seg, points in curves.items():
        fig, ax = plt.subplots(figsize=(4.5, 4.5), dpi=150)
        top = max(v for p in points for v in (p["nominal"], p["observed"])) * 1.4
        ax.plot([0, top], [0, top], color="#B9B19C", lw=1.25, label="perfect calibration")
        ax.plot(
            [p["nominal"] for p in points],
            [p["observed"] for p in points],
            "o-",
            color="#2E6B62",
            lw=2,
        )
        for p in points:
            ax.annotate(
                f"{p['observed']:.2%}",
                (p["nominal"], p["observed"]),
                textcoords="offset points",
                xytext=(6, -10),
                fontsize=8,
            )
        ax.set_xlabel("target miss rate (alpha)")
        ax.set_ylabel("observed miss rate, held-out years")
        ax.set_title(f"{method}, {seg} (n={points[0]['n']:,})", fontsize=10)
        ax.set_xlim(0, top)
        ax.set_ylim(0, top)
        fig.tight_layout()
        path = out / f"calibration_{seg}.png"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)
    return written


def variants(out: Path) -> list[dict[str, Any]]:
    """Earlier configurations kept for disclosure (artifacts/model/variants/*.json)."""
    found = []
    for path in sorted((out / "variants").glob("*.json")):
        doc = json.loads(path.read_text())
        acc = doc["acceptance"]
        found.append(
            {
                "file": f"variants/{path.name}",
                "target_scaling": doc["config"].get("target_scaling", "none"),
                "conformal_normalize": doc["config"]["conformal"].get("normalize", "none"),
                "shipped": acc["shipped"],
                "model_pinball": acc["pinball_vs_baselines"]["ewma_normal"]["model"],
                "miss_rate_overall": acc["coverage_overall"]["miss_rate"],
            }
        )
    return found


def build_report(
    cfg: AfterhoursConfig, data: pd.DataFrame, data_manifest: dict[str, Any]
) -> dict[str, Any]:
    """Run everything and write the artifacts; return the report card."""
    out = cfg.path(cfg.paths.artifacts_dir) / "model"
    out.mkdir(parents=True, exist_ok=True)
    result = wf.run(cfg, data)
    pooled: pd.DataFrame = result["pooled"]
    acc = wf.acceptance(cfg, pooled)
    curves = {
        name: wf.calibration_curve(pooled, cfg.model.quantiles, name)
        for name in ("model", *wf.BASELINES)
    }
    production = train_production(cfg, data, out, acc["shipped"])
    card = {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_version": code_version(),
        "label": "historical stock prices; walk-forward held-out years only",
        "config": cfg.model.model_dump(),
        "data": data_manifest,
        "first_sentence": (
            "The LightGBM model with Mondrian conformal calibration met every acceptance criterion."
            if acc["passed"]
            else (
                "The model missed acceptance, so Afterhours ships the best baseline "
                f"({acc['shipped']})."
            )
        ),
        "acceptance": acc,
        "shipped_performance": acc["held_out"][acc["shipped"]],
        "calibration_curves": curves,
        "folds": result["folds"],
        "feature_importance_gain_share": result["feature_importance_gain_share"],
        "production": production,
        "variants_tried": variants(out),
    }
    (out / "report_card.json").write_text(json.dumps(card, indent=2, default=str) + "\n")
    pooled.to_parquet(cfg.path(cfg.data.cache_dir) / "heldout_predictions.parquet")
    calibration_figures(curves[acc["shipped"]], out, acc["shipped"])
    return card
