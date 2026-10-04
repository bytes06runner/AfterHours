"""Price regime monitor: calendar states, classification, the quality score and pool prices."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from afterhours.config import load_config
from afterhours.live import regime as rg
from afterhours.live.mainnet import pool_price

REPO = Path(__file__).resolve().parents[2]
CFG = load_config(load_env_file=False)
CAL = "XNYS"


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(UTC)


@pytest.mark.parametrize(
    ("at", "state", "segment"),
    [
        ("2026-10-02T15:00:00+00:00", "regular", "session"),  # Friday 11:00 New York
        ("2026-10-02T21:00:00+00:00", "extended", "after_hours"),  # Friday 17:00
        ("2026-10-03T00:30:00+00:00", "closed", "frozen"),  # Friday 20:30
        ("2026-10-04T12:00:00+00:00", "closed", "frozen"),  # Sunday 08:00
        ("2026-10-05T01:00:00+00:00", "extended", "overnight"),  # Sunday 21:00
        ("2026-10-05T09:00:00+00:00", "extended", "pre_market"),  # Monday 05:00
        ("2026-11-26T15:00:00+00:00", "closed", "frozen"),  # Thanksgiving
    ],
)
def test_calendar_state(at: str, state: str, segment: str) -> None:
    c = rg.calendar_state(CAL, utc(at))
    assert (c["state"], c["segment"]) == (state, segment)


def test_closed_since_is_the_start_of_the_shut_stretch() -> None:
    # Friday 20:00 New York, to the minute, from any time inside the weekend window.
    for at in (
        "2026-10-03T00:00:30+00:00",
        "2026-10-04T10:23:41+00:00",
        "2026-10-04T23:59:00+00:00",
    ):
        assert rg.closed_since(CAL, utc(at), 5) == utc("2026-10-03T00:00:00+00:00")
    # Thanksgiving: shut from Wednesday 20:00 New York.
    assert rg.closed_since(CAL, utc("2026-11-26T15:00:00+00:00"), 5) == utc(
        "2026-11-26T01:00:00+00:00"
    )


def test_classify() -> None:
    since = utc("2026-10-03T00:00:00+00:00")
    grace = CFG.regime.window_grace_seconds
    assert rg.classify("regular", since, None, grace) == "regular"
    assert rg.classify("extended", since, None, grace) == "extended"
    assert rg.classify("closed", since - timedelta(hours=3), since, grace) == "frozen"
    # A straggler right after the window opened (M1 saw up to 105 s) is not a weekend source.
    assert rg.classify("closed", since + timedelta(seconds=87), since, grace) == "frozen"
    assert rg.classify("closed", since + timedelta(hours=10), since, grace) == "weekend_venue"
    assert rg.classify("closed", None, since, grace) == "frozen"


def test_staleness_mark() -> None:
    r = CFG.regime
    f = rg.staleness_mark
    assert f("frozen", 10, 5, r.stale_multiple, r.stale_floor_minutes) == 0.0
    assert f("regular", 5 * 60, 10, r.stale_multiple, r.stale_floor_minutes) == 1.0
    zero_at = max(10 * r.stale_multiple, r.stale_floor_minutes) * 60
    assert f("regular", zero_at, 10, r.stale_multiple, r.stale_floor_minutes) == 0.0
    half = (10 * 60 + zero_at) / 2
    assert f("regular", half, 10, r.stale_multiple, r.stale_floor_minutes) == pytest.approx(0.5)
    assert f("regular", None, 10, r.stale_multiple, r.stale_floor_minutes) is None


def test_divergence_and_depth_marks() -> None:
    limit = CFG.schedule.triggers.divergence_pct
    assert rg.divergence_mark(0.0, limit) == 1.0
    assert rg.divergence_mark(-limit / 2, limit) == pytest.approx(0.5)
    assert rg.divergence_mark(3 * limit, limit) == 0.0
    r = CFG.regime
    assert rg.depth_mark(r.depth_floor_usd, r.depth_floor_usd, r.depth_full_usd) == 0.0
    assert rg.depth_mark(r.depth_full_usd * 10, r.depth_floor_usd, r.depth_full_usd) == 1.0
    mid = math.sqrt(r.depth_floor_usd * r.depth_full_usd)
    assert rg.depth_mark(mid, r.depth_floor_usd, r.depth_full_usd) == pytest.approx(0.5)


def test_quality_renormalises_missing_marks() -> None:
    w = CFG.regime.weights
    q = rg.quality(CFG, {"staleness": 1.0, "divergence": None, "depth": 0.0})
    assert q["used"] == ["depth", "staleness"]
    assert q["score"] == round(100 * w.staleness / (w.staleness + w.depth))
    assert rg.quality(CFG, {"staleness": None, "divergence": None, "depth": None})["score"] is None
    good = rg.quality(CFG, {"staleness": 1.0, "divergence": 1.0, "depth": 1.0})
    assert (good["score"], good["grade"]) == (100, "good")


def test_pool_price_both_orders() -> None:
    # NVDA/USDG v3 pool on mainnet, 2026-10-04 (cast): USDG (6) is currency0, NVDA (18) currency1.
    usdg, nvda = (
        "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168",
        "0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC",
    )
    p = pool_price(5170342102455874715918082815169958, nvda, usdg, 18, 6)
    assert p == pytest.approx(234.8, rel=1e-3)  # feed then: 234.997
    # The same pool seen from the other side gives the reciprocal.
    q = pool_price(5170342102455874715918082815169958, usdg, nvda, 6, 18)
    assert q == pytest.approx(1 / p)


def test_regime_row_line_and_cadence() -> None:
    now = utc("2026-10-04T10:00:00+00:00")
    cal = rg.calendar_state(CAL, now)
    since = rg.closed_since(CAL, now, 5)
    row = rg.regime_row(
        CFG,
        symbol="RGTI",
        now=now,
        cal=cal,
        since=since,
        updated_at=utc("2026-10-02T19:40:00+00:00"),
        feed_price=10.0,
        dex_price=10.73,
        depth_usd=73.0,
        cadence_doc=None,
    )
    assert row["regime"] == "frozen"
    assert row["divergence"] == pytest.approx(0.073)
    assert row["line"].startswith("Frozen since Friday 20:00 New York")
    assert "7.3% above the feed" in row["line"]
    assert row["quality"]["grade"] == "poor"
    assert "—" not in row["line"]  # no em dashes


def test_cadence_artifact_matches_the_study_files() -> None:
    doc = json.loads((REPO / "artifacts/regime/cadence.json").read_text())
    studies = [json.loads((REPO / "artifacts" / src).read_text()) for src in doc["sources"]]
    studies = [s.get("study", s) for s in studies]
    again = rg.cadence(studies, CFG.regime.cadence_step_minutes)
    assert again["feeds"] == doc["feeds"]
    assert doc["periods_read"] == sum(len(s["periods"]) for s in studies)


def test_regimes_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from afterhours.api.app import create_app
    from afterhours.live.mainnet import Mainnet

    board: dict[str, Any] = {
        "network": "Robinhood Chain",
        "block": 1,
        "as_of": "2026-10-04T10:00:00+00:00",
        "regimes": {"calendar": "closed", "counts": {"frozen": 1}},
        "stocks": [{"symbol": "NVDA", "price": 235.0, "regime": {"regime": "frozen", "line": "x"}}],
    }
    monkeypatch.setattr(Mainnet, "board", lambda self, *a, **k: board)
    res = TestClient(create_app(CFG)).get("/v1/live/regimes")
    assert res.status_code == 200
    body = res.json()
    assert body["tokens"] == [
        {"symbol": "NVDA", "feed_price": 235.0, "regime": "frozen", "line": "x"}
    ]
    assert body["counts"] == {"frozen": 1}
    # A board saved before the monitor existed reads as "still reading", not a crash.
    monkeypatch.setattr(
        Mainnet,
        "board",
        lambda self, *a, **k: {**board, "regimes": None, "stocks": [{"symbol": "NVDA"}]},
    )
    assert TestClient(create_app(CFG)).get("/v1/live/regimes").status_code == 503
