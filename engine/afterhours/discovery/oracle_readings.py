"""Dated readings of the weekend oracle study (deciding fact 1, re-checked over time).

The M1 study (`artifacts/discovery/oracle_study.json`) is never rewritten. Each new reading
covers only the closed periods that ended after everything read before, and is written to its
own file in `artifacts/discovery/oracle_readings/`, with an index that answers the one question
that matters after Robinhood's weekend trading news: does any Stock Token feed now post prices
inside the Friday 20:00 to Sunday 20:00 New York window?
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from afterhours.chain.rpc import connect
from afterhours.config import AfterhoursConfig
from afterhours.deployments import load_discovered
from afterhours.discovery import oracle_study
from afterhours.numbers import oracle_summary

ORIGINAL = ("discovery", "oracle_study.json")
READINGS = ("discovery", "oracle_readings")


def readings_dir(cfg: AfterhoursConfig) -> Path:
    return cfg.path(cfg.paths.artifacts_dir).joinpath(*READINGS)


def original(cfg: AfterhoursConfig) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(
        cfg.path(cfg.paths.artifacts_dir).joinpath(*ORIGINAL).read_text()
    )
    return doc


def readings(cfg: AfterhoursConfig) -> list[dict[str, Any]]:
    """Every dated reading, oldest first (the index is rebuilt from these files)."""
    d = readings_dir(cfg)
    if not d.exists():
        return []
    docs = [json.loads(p.read_text()) for p in sorted(d.glob("reading-*.json"))]
    return sorted(docs, key=lambda r: r["taken_at"])


def last_covered(cfg: AfterhoursConfig) -> datetime:
    """The latest reopening already read, across the original study and every reading."""
    studies = [original(cfg), *(r["study"] for r in readings(cfg))]
    opens = [datetime.fromisoformat(p["open"]) for s in studies for p in s["periods"]]
    return max(opens)


def take(cfg: AfterhoursConfig, now: datetime | None = None) -> dict[str, Any] | None:
    """Read the closed periods since the last reading; None when nothing new has ended."""
    since = last_covered(cfg)
    profile = cfg.live.profile
    w3 = connect(cfg.rpc_url(profile))
    public = cfg.chains[cfg.profiles[profile].chain].public_rpc_url
    w3_logs = connect(public) if public else w3
    head = int(w3_logs.eth.block_number) - cfg.live.lag_blocks
    disc = load_discovered(cfg, cfg.live.discovery_profile)
    proxies = {s: v["feed"]["address"] for s, v in disc["stock_tokens"].items() if v.get("feed")}
    d = cfg.discovery
    study = oracle_study.study(
        w3,
        proxies,
        calendar=cfg.data.exchange_calendar,
        weekends=d.oracle_study.weekends,
        head_block=head,
        max_range=d.oracle_study.max_log_block_range,
        now=now,
        since=since,
        w3_logs=w3_logs,
    )
    if not any(p["kind"] == "weekend" for p in study["periods"]):
        return None
    return {
        "taken_at": datetime.now(UTC).isoformat(),
        "since": since.isoformat(),
        "head_block": head,
        "network": cfg.chains[cfg.profiles[profile].chain].name,
        "method": "same as the M1 study (engine/afterhours/discovery/oracle_study.py)",
        "summary": _summary(study),
        "study": study,
    }


def _summary(study: dict[str, Any]) -> dict[str, Any]:
    s = oracle_summary(study)
    return {k: v for k, v in s.items() if k != "updates"} | {"updates_inside_window": s["updates"]}


def write(cfg: AfterhoursConfig, reading: dict[str, Any]) -> Path:
    """Write a reading to a new file (never over an existing one) and rebuild the index."""
    d = readings_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    day = reading["taken_at"][:10]
    path = d / f"reading-{day}.json"
    n = 2
    while path.exists():
        path = d / f"reading-{day}-{n}.json"
        n += 1
    path.write_text(json.dumps(reading, indent=2) + "\n")
    write_index(cfg)
    return path


def index(cfg: AfterhoursConfig) -> dict[str, Any]:
    """Original plus readings, one row each: does any feed post inside the weekend window?"""
    rows = [
        {
            "file": "/".join(ORIGINAL),
            "taken_at": original(cfg)["now"],
            **_row(oracle_summary(original(cfg))),
        }
    ]
    for p in sorted(readings_dir(cfg).glob("reading-*.json")):
        r = json.loads(p.read_text())
        rows.append(
            {"file": "/".join((*READINGS, p.name)), "taken_at": r["taken_at"], **_row(r["summary"])}
        )
    rows.sort(key=lambda r: r["taken_at"])
    latest = rows[-1]
    return {
        "question": "Does any Stock Token feed post a price inside the weekend window?",
        "window": "Friday 20:00 to Sunday 20:00 New York",
        "readings": rows,
        "weekends_read": sum(r["weekends"] for r in rows),
        "latest": latest,
    }


def _row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "weekends": summary["weekends"],
        "first_weekend_close": summary["first_weekend_close"],
        "last_weekend_close": summary["last_weekend_close"],
        "feeds": summary["feeds"],
        "feeds_without_update": summary["feeds_without_update"],
        "feeds_with_update": summary["feeds_with_update"],
        "updates_in_window": summary["updates_in_window"],
        "max_seconds_after_window_opened": summary["max_seconds_after_window_opened"],
    }


def write_index(cfg: AfterhoursConfig) -> Path:
    path = readings_dir(cfg) / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index(cfg), indent=2) + "\n")
    return path
