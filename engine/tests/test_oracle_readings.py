"""Dated readings of the weekend oracle study: new periods only, the M1 reading untouched."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from afterhours.config import load_config
from afterhours.discovery import oracle_readings
from afterhours.discovery.oracle_study import recent_closed_periods

REPO = Path(__file__).resolve().parents[2]


def test_a_new_reading_starts_after_the_last_one() -> None:
    now = datetime(2026, 10, 4, 12, tzinfo=UTC)
    since = datetime(2026, 9, 21, 13, 30, tzinfo=UTC)  # the M1 study's last reopening
    weekends, overnights = recent_closed_periods("XNYS", now, 8, since=since)
    assert [w.close.date().isoformat() for w in weekends] == ["2026-09-25"]
    assert all(p.close > since for p in overnights)
    # The weekend still in progress (Oct 2 to Oct 5) is not read until it has ended.
    later, _ = recent_closed_periods("XNYS", datetime(2026, 10, 5, 14, tzinfo=UTC), 8, since=since)
    assert [w.close.date().isoformat() for w in later] == ["2026-09-25", "2026-10-02"]


@pytest.fixture
def art(tmp_path: Path) -> Any:
    cfg = load_config(load_env_file=False)
    (tmp_path / "discovery").mkdir()
    shutil.copy(REPO / "artifacts/discovery/oracle_study.json", tmp_path / "discovery")
    paths = cfg.paths.model_copy(update={"artifacts_dir": str(tmp_path)})
    return cfg.model_copy(update={"paths": paths})


def reading(taken_at: str, close: str, open_: str) -> dict[str, Any]:
    study = {
        "calendar": "XNYS",
        "now": taken_at,
        "periods": [{"kind": "weekend", "close": close, "open": open_, "hours": 65.5}],
        "feeds": [
            {
                "symbol": "NVDA",
                "frozen_updates": 0,
                "weekends": [{"close": close, "inside_frozen_detail": []}],
            }
        ],
    }
    return {
        "taken_at": taken_at,
        "summary": oracle_readings._summary(study),
        "study": study,
    }


def test_readings_never_overwrite_and_the_original_stays(art: Any) -> None:
    before = (Path(art.paths.artifacts_dir) / "discovery/oracle_study.json").read_bytes()
    r = reading(
        "2026-10-04T10:00:00+00:00", "2026-09-25T20:00:00+00:00", "2026-09-28T13:30:00+00:00"
    )
    first = oracle_readings.write(art, r)
    second = oracle_readings.write(art, r)
    assert first != second  # same day, a second file
    assert (Path(art.paths.artifacts_dir) / "discovery/oracle_study.json").read_bytes() == before
    assert oracle_readings.last_covered(art) == datetime(2026, 9, 28, 13, 30, tzinfo=UTC)
    idx = json.loads((first.parent / "index.json").read_text())
    assert idx["readings"][0]["file"] == "discovery/oracle_study.json"
    assert idx["latest"]["feeds_with_update"] == []
    assert idx["weekends_read"] == 8 + 1 + 1
