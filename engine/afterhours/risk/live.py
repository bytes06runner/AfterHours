"""Live risk: the calibrated bad-case drop for each Stock Token's upcoming closed periods.

Uses the shipped forecaster recorded in `artifacts/model/production.json` (M3). Everything is
computed "as of" a given time (the chain's clock on fork and local profiles), using only prices
up to that time and the scheduled earnings calendar.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from afterhours.config import AfterhoursConfig
from afterhours.data.cache import ParquetCache
from afterhours.features.dataset import closed_periods, earnings_flags, sessions

NORMAL = NormalDist()  # the standard normal


@dataclass(frozen=True)
class Period:
    """One closed period of the exchange."""

    starts: datetime
    ends: datetime
    session_prev: date
    session_next: date
    segment: str
    hours: float

    def to_json(self) -> dict[str, Any]:
        return {
            "starts": self.starts.isoformat(),
            "ends": self.ends.isoformat(),
            "segment": self.segment,
            "hours": round(self.hours, 2),
        }


@dataclass
class Forecast:
    """Bad-case drop for one stock and one closed period, with its drivers."""

    symbol: str
    period: Period
    bad_case_drop: float
    alpha: float
    model_version: str
    method: str
    drivers: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        out = asdict(self)
        out["period"] = self.period.to_json()
        return out


@dataclass
class SessionState:
    """Where the exchange clock stands."""

    now: datetime
    state: str  # "open" | "closed" | "holiday"
    next_open: datetime
    next_close: datetime
    last_close: datetime | None

    def to_json(self) -> dict[str, Any]:
        return {
            "now": self.now.isoformat(),
            "state": self.state,
            "next_open": self.next_open.isoformat(),
            "next_close": self.next_close.isoformat(),
            "seconds_to_open": max(0, int((self.next_open - self.now).total_seconds())),
            "seconds_to_close": max(0, int((self.next_close - self.now).total_seconds())),
        }


def session_state(calendar: str, now: datetime) -> SessionState:
    """Open or closed at `now`, with the next bells."""
    sess = sessions(calendar, (now - timedelta(days=10)).date(), (now + timedelta(days=20)).date())
    opens, closes = list(sess["open"]), list(sess["close"])
    for o, c in zip(opens, closes, strict=True):
        if o <= now < c:
            later = [x for x in opens if x > now]
            return SessionState(now, "open", later[0], c, None)
    next_open = min(o for o in opens if o > now)
    next_close = min(c for c in closes if c > now)
    last_close = max(c for c in closes if c <= now)
    gap_days = (next_open.date() - last_close.date()).days
    weekday_skipped = any(
        (last_close.date() + timedelta(days=k)).weekday() < 5 for k in range(1, gap_days)
    )
    return SessionState(
        now, "holiday" if weekday_skipped else "closed", next_open, next_close, last_close
    )


def upcoming_periods(
    calendar: str, now: datetime, count: int, earnings: pd.DataFrame | None
) -> list[Period]:
    """The closed period in progress (if any) and the next ones, `count` in total."""
    sess = sessions(calendar, (now - timedelta(days=10)).date(), (now + timedelta(days=60)).date())
    periods = closed_periods(sess)
    periods = periods[periods["open_next"] > now].head(count).reset_index(drop=True)
    flags = (
        earnings_flags(periods, earnings) if earnings is not None and not earnings.empty else None
    )
    out = []
    for pos, (_, row) in enumerate(periods.iterrows()):
        seg = (
            "earnings"
            if flags is not None and bool(flags.iloc[pos])
            else str(row["calendar_segment"])
        )
        out.append(
            Period(
                row["close_prev"].to_pydatetime(),
                row["open_next"].to_pydatetime(),
                row["session_prev"],
                row["session_next"],
                seg,
                float(row["hours_closed"]),
            )
        )
    return out


def ewma_sigma(prices: pd.DataFrame, as_of: date, lam: float) -> float:
    """RiskMetrics daily volatility from closes up to `as_of`."""
    close = prices["close"][[d <= as_of for d in prices.index]]
    logret = np.log(close).diff().dropna()
    var = (logret**2).ewm(alpha=1 - lam, min_periods=20).mean()
    return float(np.sqrt(var.iloc[-1])) if len(var) else float("nan")


def held_out_coverage(cfg: AfterhoursConfig) -> dict[str, Any]:
    """How often the shipped forecaster's bad case was beaten on held-out years, per segment.

    From `artifacts/model/report_card.json` (`shipped_performance`, walk-forward test folds).
    The forecast targets `model.target_alpha`; these are the measured rates, which is what any
    "beaten about 1 night in N" sentence must quote.
    """
    path = cfg.path(cfg.paths.artifacts_dir) / "model" / "report_card.json"
    card = json.loads(path.read_text())
    tests = [int(f["fold"]["test"][0]) for f in card.get("folds", [])]
    return {
        "target": cfg.model.target_alpha,
        "test_years": [min(tests), max(tests)] if tests else None,
        "miss_rate": {
            seg: float(v["miss_rate"]) for seg, v in card.get("shipped_performance", {}).items()
        },
        "source": "artifacts/model/report_card.json",
    }


class LiveRisk:
    """Forecasts for the selected Stock Tokens from the shipped method."""

    def __init__(self, cfg: AfterhoursConfig, cache: ParquetCache) -> None:
        self.cfg = cfg
        self.cache = cache
        path = cfg.path(cfg.paths.artifacts_dir) / "model" / "production.json"
        self.production: dict[str, Any] = json.loads(path.read_text())
        self.method = str(self.production["shipped"])
        if self.method != "ewma_normal":
            raise NotImplementedError(
                f"live serving implements the shipped baseline; production ships {self.method}"
            )
        self.coverage = held_out_coverage(cfg)

    def forecast(self, symbol: str, now: datetime, horizon: int) -> list[Forecast]:
        """Forecasts for `symbol` over the next `horizon` closed periods."""
        prices = self.cache.get(f"prices/{symbol}", allow_stale=True)
        if prices is None:
            raise KeyError(f"no cached prices for {symbol}; run `afterhours data build`")
        events = self.cache.get(f"earnings/{symbol}", allow_stale=True)
        alpha = float(self.production["alpha"])
        corrections = self.production["corrections"][self.method][f"{alpha:g}"]
        sigma = ewma_sigma(
            prices, now.astimezone(UTC).date(), float(self.production["ewma_lambda"])
        )
        # Same value as scipy.stats.norm.ppf (bit for bit at alpha 0.01, tested) without
        # loading scipy into the API process.
        z = NORMAL.inv_cdf(alpha)
        out = []
        for period in upcoming_periods(self.cfg.data.exchange_calendar, now, horizon, events):
            scale = sigma * math.sqrt(period.hours / 24)
            c = float(corrections.get(period.segment, corrections["_overall"]))
            raw = math.expm1(z * scale)
            q = raw - c * scale
            drop = max(0.0, -q)
            out.append(
                Forecast(
                    symbol=symbol,
                    period=period,
                    bad_case_drop=drop,
                    alpha=alpha,
                    model_version=str(self.production["model_version"]),
                    method=self.method,
                    drivers=drivers(sigma, period, z, c, drop),
                )
            )
        return out


def drivers(
    sigma: float, period: Period, z: float, correction: float, drop: float
) -> list[dict[str, Any]]:
    """Exact additive split of the bad-case drop for the shipped baseline.

    drop is about -(z + ... ) * sigma * sqrt(h/24) + c * sigma * sqrt(h/24). We report how much of
    it comes from the stock's volatility over a normal overnight, from the length of this closure,
    and from the segment calibration (earnings, weekend, ...). The parts sum to the drop.
    """
    base_scale = sigma * math.sqrt(17.5 / 24)  # a normal weeknight closure (16:00 to 09:30)
    scale = sigma * math.sqrt(period.hours / 24)
    vol_part = -math.expm1(z * base_scale)
    hours_part = -math.expm1(z * scale) - vol_part
    seg_part = drop - vol_part - hours_part
    return [
        {
            "feature": "stock_volatility",
            "contribution": vol_part,
            "detail": f"EWMA daily volatility {sigma:.2%}",
        },
        {
            "feature": "closed_hours",
            "contribution": hours_part,
            "detail": f"{period.hours:.1f} hours closed",
        },
        {
            "feature": f"segment_{period.segment}",
            "contribution": seg_part,
            "detail": f"calibrated {period.segment} correction {correction:+.2f} volatility units",
        },
    ]
