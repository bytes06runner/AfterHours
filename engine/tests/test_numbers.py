"""The submission numbers are generated from the committed artifacts and stay consistent."""

from __future__ import annotations

from afterhours.config import load_config
from afterhours.numbers import build, oracle_summary


def test_numbers_build_from_artifacts() -> None:
    doc = build(load_config(load_env_file=False))
    n = doc["numbers"]
    assert n["model.first_sentence"]["text"].startswith("The model")
    for key, entry in n.items():
        assert entry["source"], key
        assert entry["text"] != "", key
    s = n["backtest.afterhours.bad_debt"]["value"]
    w = n["backtest.always_weekday.bad_debt"]["value"]
    assert round(w / s) == int(n["backtest.bad_debt_ratio_weekday_vs_afterhours"]["text"])


def test_oracle_summary_counts_window_updates() -> None:
    study = {
        "periods": [
            {"kind": "weekend", "close": "2026-07-31T20:00:00+00:00"},
            {"kind": "overnight", "close": "2026-08-03T20:00:00+00:00"},
        ],
        "feeds": [
            {
                "symbol": "A",
                "frozen_updates": 0,
                "weekends": [{"close": "2026-07-31T20:00:00+00:00", "inside_frozen_detail": []}],
            },
            {
                "symbol": "B",
                "frozen_updates": 1,
                "weekends": [
                    {
                        "close": "2026-07-31T20:00:00+00:00",
                        # Friday 20:00 New York in summer is 00:00 UTC Saturday.
                        "inside_frozen_detail": [{"at": "2026-08-01T00:01:30+00:00"}],
                    }
                ],
            },
        ],
    }
    o = oracle_summary(study)
    assert o["weekends"] == 1
    assert o["feeds_without_update"] == 1
    assert o["feeds_with_update"] == ["B"]
    assert o["max_seconds_after_window_opened"] == 90
