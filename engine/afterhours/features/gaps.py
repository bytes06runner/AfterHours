"""Gap study (M2): the distribution of closed-period gaps by segment.

Writes `artifacts/gaps/summary.json` and figures. Every number in the pitch about gaps
comes from this file.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from afterhours.features.dataset import SEGMENTS


def code_version() -> str:
    """Short git SHA of the working tree, with a dirty flag."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def segment_stats(
    g: pd.Series, quantiles: Sequence[float], drops: Sequence[float], hours: pd.Series
) -> dict[str, Any]:
    """Count, spread, quantiles and drop frequencies for a set of gaps."""
    if g.empty:
        return {"n": 0}
    return {
        "n": int(g.size),
        "mean": float(g.mean()),
        "std": float(g.std()),
        "mean_hours_closed": float(hours.mean()),
        "quantiles": {f"{q:g}": float(g.quantile(q)) for q in quantiles},
        "share_drops_at_least": {f"{d:g}": float((g <= -d).mean()) for d in drops},
        "count_drops_at_least": {f"{d:g}": int((g <= -d).sum()) for d in drops},
        "min": float(g.min()),
    }


def by_segment(
    frame: pd.DataFrame, quantiles: Sequence[float], drops: Sequence[float]
) -> dict[str, Any]:
    """Stats for all rows and per segment."""
    out = {"all": segment_stats(frame["g"], quantiles, drops, frame["hours_closed"])}
    for seg in SEGMENTS:
        part = frame[frame["segment"] == seg]
        out[seg] = segment_stats(part["g"], quantiles, drops, part["hours_closed"])
    return out


def worst(frame: pd.DataFrame, n: int) -> list[dict[str, Any]]:
    """The n most negative gaps."""
    rows = frame.nsmallest(n, "g")
    return [
        {
            "ticker": r.ticker,
            "session_prev": str(r.session_prev),
            "session_next": str(r.session_next),
            "segment": r.segment,
            "g": float(r.g),  # type: ignore[arg-type]
        }
        for r in rows.itertuples()
    ]


def study(
    data: pd.DataFrame,
    *,
    selected: Sequence[str],
    stock_tokens: Sequence[str],
    quantiles: Sequence[float],
    drops: Sequence[float],
    worst_n: int,
    data_manifest: dict[str, Any],
) -> dict[str, Any]:
    """The full gap study document."""
    sel = data[data["ticker"].isin(selected)]
    tok = data[data["ticker"].isin(stock_tokens)]
    per_ticker = {
        t: by_segment(data[data["ticker"] == t], quantiles, drops) for t in sorted(set(selected))
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_version": code_version(),
        "label": "historical stock prices (split and dividend adjusted), NYSE sessions",
        "data": data_manifest,
        "period": {
            "first_close": str(data["session_prev"].min()),
            "last_open": str(data["session_next"].max()),
        },
        "tickers": {
            "universe": int(data["ticker"].nunique()),
            "selected": list(selected),
            "stock_tokens_with_feed": list(stock_tokens),
        },
        "universe": by_segment(data, quantiles, drops),
        "stock_tokens": by_segment(tok, quantiles, drops) if not tok.empty else None,
        "selected": by_segment(sel, quantiles, drops) if not sel.empty else None,
        "selected_per_ticker": per_ticker,
        "worst_selected": worst(sel, worst_n) if not sel.empty else [],
        "worst_stock_tokens": worst(tok, worst_n) if not tok.empty else [],
    }


def figures(data: pd.DataFrame, selected: Sequence[str], out_dir: Path) -> list[Path]:
    """Histogram and tail plots by segment. Returns the files written."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    colors = {
        "earnings": "#A23B2D",
        "holiday": "#9C7431",
        "weekend": "#2E6B62",
        "overnight": "#1D1F33",
    }
    for name, frame in (("selected", data[data["ticker"].isin(selected)]), ("universe", data)):
        if frame.empty:
            continue
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        bins = [float(x) for x in np.linspace(-0.3, 0.3, 121)]
        for seg in SEGMENTS:
            g = frame.loc[frame["segment"] == seg, "g"].clip(-0.3, 0.3)
            if not g.empty:
                ax.hist(
                    g,
                    bins=bins,
                    density=True,
                    histtype="step",
                    lw=1.4,
                    color=colors[seg],
                    label=f"{seg} (n={len(g):,})",
                )
        ax.set_yscale("log")
        ax.set_xlabel("gap: open next / close before - 1 (clipped at +/-30%)")
        ax.set_ylabel("density (log)")
        ax.set_title(f"Closed-period gaps by segment, {name}")
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        path = out_dir / f"gap_hist_{name}.png"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        xs = np.linspace(0.01, 0.4, 80)
        for seg in SEGMENTS:
            tail = frame.loc[frame["segment"] == seg, "g"].to_numpy()
            if tail.size:
                ax.plot(
                    xs * 100,
                    [(tail <= -x).mean() for x in xs],
                    color=colors[seg],
                    lw=1.6,
                    label=seg,
                )
        ax.set_yscale("log")
        ax.set_xlabel("drop at the open of at least (%)")
        ax.set_ylabel("share of closed periods")
        ax.set_title(f"How often the open gaps down, {name}")
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        path = out_dir / f"gap_tail_{name}.png"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)
    return written


def write_summary(doc: dict[str, Any], out_dir: Path) -> Path:
    """Write summary.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.json"
    path.write_text(json.dumps(doc, indent=2) + "\n")
    return path
