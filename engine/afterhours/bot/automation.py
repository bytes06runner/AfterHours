"""Recorded pre-close cycles and the automation health built from them.

Every scheduled job invocation writes a heartbeat. Every cycle it starts writes a record with
an id, its trigger source, an input snapshot, the policy, the decision ("hold" or "act"), the
reason and how it ended. A hold is a successful cycle, not "nothing happened", so health can
tell three situations apart: the bot never ran, it ran and held, it ran and moved money.

Pre-close cycles are idempotent per close: the id is the close time, a completed record is
never run again, and a record still "running" blocks a second invocation until it times out
(`automation.running_timeout_minutes`, longer than the job's own timeout), after which the
cycle counts as failed and the next invocation retries it.

All records live in one document (`automation`) in the profile's store, so the API on the host
and the scheduled job in GitHub Actions read and write the same history.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from afterhours.bot.scheduler import pre_close_window
from afterhours.config import AfterhoursConfig
from afterhours.features.dataset import sessions
from afterhours.logsafe import redact
from afterhours.state import BaseStore

DOC = "automation"
HEALTHY = ("ok", "running", "waiting_for_first_close")


class CycleLike(Protocol):
    """What the recorder needs from `allocator.CycleResult`."""

    trigger: str
    now: str
    plan: dict[str, Any]
    executed: bool
    txs: list[str]
    reasons: list[str]


class Runner(Protocol):
    def run_cycle(self, trigger: str, *, execute: bool = True) -> Any: ...


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat()


def _parse(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def load(store: BaseStore) -> dict[str, Any]:
    """The automation document, read past any cache (decisions depend on it)."""
    doc = store.read_fresh(DOC)
    return doc or {"tracking_since": None, "heartbeat": None, "cycles": []}


def _save(store: BaseStore, cfg: AfterhoursConfig, doc: dict[str, Any]) -> None:
    doc["cycles"] = doc["cycles"][-cfg.automation.history_cycles :]
    store.write(DOC, doc)


def heartbeat(
    store: BaseStore,
    cfg: AfterhoursConfig,
    now: datetime,
    source: str,
    run_ref: str | None,
) -> datetime | None:
    """Record that a scheduled job ran; return the close whose pre-close window holds `now`."""
    close = pre_close_window(cfg, now)
    with store.lock(DOC):
        doc = load(store)
        doc["tracking_since"] = doc.get("tracking_since") or _iso(now)
        doc["heartbeat"] = {
            "at": _iso(now),
            "source": source,
            "run_ref": run_ref,
            "in_window": close is not None,
            "close": _iso(close) if close else None,
        }
        _save(store, cfg, doc)
    return close


def close_done(store: BaseStore, close: datetime) -> bool:
    """True once this close's pre-close cycle has completed (later runs have nothing to do)."""
    rec = _find(load(store), f"pre_close:{_iso(close)}")
    return bool(rec and rec["status"] == "completed")


def policy_snapshot(cfg: AfterhoursConfig) -> dict[str, Any]:
    """The policy settings a cycle ran under (option B, frozen since 2026-09-27)."""
    p = cfg.policy
    return {
        "name": "option_b",
        "map_fraction": p.map_fraction,
        "pullback_fraction": p.pullback_fraction,
        "lookahead_closed_periods": p.lookahead_closed_periods,
        "min_rebalance_usd": p.min_rebalance_usd,
    }


def input_snapshot(plan: dict[str, Any]) -> dict[str, Any]:
    """What the cycle saw: vault totals, each stock's forecast and limit, and a plan hash."""
    forecasts = plan.get("driving_forecast", {})
    versions = sorted({f.get("model_version") for f in forecasts.values() if f})
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "as_of": plan.get("now"),
        "total_assets_usdg": plan.get("total_assets_usdg"),
        "idle_usdg": plan.get("idle_usdg"),
        "model_version": versions[0] if len(versions) == 1 else versions,
        "stocks": {
            s: {
                "mapped_tier": d.get("mapped_tier"),
                "forecast_bad_case": d.get("forecast_bad_case"),
                "pull_limit": d.get("pull_limit"),
                "pulled": d.get("pulled"),
            }
            for s, d in sorted(plan.get("decisions", {}).items())
        },
        "plan_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def decide(
    result: CycleLike, min_rebalance_usd: float, *, executed: bool = True
) -> tuple[str, str]:
    """("act" | "hold" | "dry_run", plain-English reason) for a finished cycle."""
    plan = result.plan
    decisions = plan.get("decisions", {})
    pulled = sorted(s for s, d in decisions.items() if d.get("pulled"))
    if not executed:  # planned only: never reported as a hold or a move
        would = "would move money" if plan.get("execute") else "would hold"
        why = f" Over the pullback limit: {', '.join(pulled)}." if pulled else ""
        return "dry_run", f"Dry run, nothing sent: the plan {would}.{why}"
    if result.txs:
        moved = f"{len(result.txs)} transaction(s), {len(result.reasons)} reason card(s) anchored"
        why = f" Pulled: {', '.join(pulled)}." if pulled else ""
        return "act", f"Moved unborrowed USDG ({moved}).{why}"
    if plan.get("status") != "optimal":
        return "hold", f"The planner returned {plan.get('status')}; nothing was moved."
    stocks = f"{len(decisions)} stock(s) checked"
    if not pulled:
        cause = "no forecast bad case crossed its pullback limit"
    else:
        cause = f"{', '.join(pulled)} over the pullback limit, already out of the market"
    turnover = float(plan.get("turnover_usdg") or 0.0)
    return "hold", (
        f"{stocks}; {cause}; the plan changes {turnover:,.0f} USDG, below the "
        f"{min_rebalance_usd:,.0f} USDG minimum, so nothing was moved."
        if not plan.get("execute")
        else f"{stocks}; {cause}; every planned move was dust, so nothing was sent."
    )


def _find(doc: dict[str, Any], cycle_id: str) -> dict[str, Any] | None:
    return next((c for c in reversed(doc["cycles"]) if c["cycle_id"] == cycle_id), None)


def _timed_out(rec: dict[str, Any], now: datetime, cfg: AfterhoursConfig) -> bool:
    started = _parse(rec.get("started_at")) or now
    return now - started > timedelta(minutes=cfg.automation.running_timeout_minutes)


def run_recorded(
    store: BaseStore,
    cfg: AfterhoursConfig,
    *,
    cycle_id: str,
    kind: str,
    close: datetime | None,
    source: str,
    run_ref: str | None,
    make_runner: Callable[[], Runner],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    execute: bool = True,
) -> dict[str, Any]:
    """Run one cycle under a record. Returns {"outcome": ..., "cycle": record}.

    Outcomes: "completed", "already_done" (a completed record has this id), "in_progress"
    (another invocation holds it), or the exception propagates after the record says "failed".
    """
    now = clock()
    with store.lock(DOC):
        doc = load(store)
        doc["tracking_since"] = doc.get("tracking_since") or _iso(now)
        prev = _find(doc, cycle_id)
        if prev and prev["status"] == "completed":
            return {"outcome": "already_done", "cycle": prev}
        if prev and prev["status"] == "running" and not _timed_out(prev, now, cfg):
            return {"outcome": "in_progress", "cycle": prev}
        if prev and prev["status"] == "running":
            prev["status"] = "failed"
            prev["error"] = "timed out without finishing (the job was killed or crashed)"
            prev["finished_at"] = _iso(now)
        rec: dict[str, Any] = {
            "cycle_id": cycle_id,
            "kind": kind,
            "close": _iso(close) if close else None,
            "trigger_source": source,
            "run_ref": run_ref,
            "attempt": (prev["attempt"] + 1) if prev else 1,
            "started_at": _iso(now),
            "finished_at": None,
            "status": "running",
            "executed": execute,
            "decision": None,
            "reason": None,
            "policy": policy_snapshot(cfg),
            "inputs": None,
            "txs": [],
            "reason_ids": [],
            "error": None,
        }
        doc["cycles"].append(rec)
        _save(store, cfg, doc)

    def finish(**fields: Any) -> dict[str, Any]:
        with store.lock(DOC):
            doc = load(store)
            mine = next(
                (
                    c
                    for c in reversed(doc["cycles"])
                    if c["cycle_id"] == cycle_id and c["started_at"] == rec["started_at"]
                ),
                None,
            )
            if mine is None:  # trimmed or overwritten: append ours again
                mine = dict(rec)
                doc["cycles"].append(mine)
            mine.update(fields, finished_at=_iso(clock()))
            _save(store, cfg, doc)
            return mine

    try:
        result: CycleLike = make_runner().run_cycle(kind, execute=execute)
    except Exception as e:
        finish(status="failed", error=redact(f"{type(e).__name__}: {e}")[:500])
        raise
    decision, reason = decide(result, cfg.policy.min_rebalance_usd, executed=execute)
    done = finish(
        status="completed",
        decision=decision,
        reason=reason,
        inputs=input_snapshot(result.plan),
        txs=list(result.txs),
        reason_ids=list(result.reasons),
    )
    return {"outcome": "completed", "cycle": done}


def run_due(
    store: BaseStore,
    cfg: AfterhoursConfig,
    *,
    source: str,
    run_ref: str | None,
    make_runner: Callable[[], Runner],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    force: bool = False,
) -> dict[str, Any]:
    """The scheduled job's entry point: heartbeat, then the pre-close cycle if one is due.

    With `force` (manual dispatch) a cycle runs even outside a window, recorded as "manual"
    under its own id, so it never stands in for a scheduled pre-close cycle.
    """
    now = clock()
    close = heartbeat(store, cfg, now, source, run_ref)
    if close is not None:
        return run_recorded(
            store,
            cfg,
            cycle_id=f"pre_close:{_iso(close)}",
            kind="pre_close",
            close=close,
            source=source,
            run_ref=run_ref,
            make_runner=make_runner,
            clock=clock,
        )
    if force:
        return run_recorded(
            store,
            cfg,
            cycle_id=f"manual:{run_ref or _iso(now)}",
            kind="manual",
            close=None,
            source=source,
            run_ref=run_ref,
            make_runner=make_runner,
            clock=clock,
        )
    return {"outcome": "not_due", "cycle": None}


def expected_closes(cfg: AfterhoursConfig, since: datetime, now: datetime) -> list[datetime]:
    """Closes after tracking began (`since`, the first heartbeat) that have passed by `now`."""
    start = max(since, now - timedelta(days=cfg.automation.lookback_days))
    sess = sessions(cfg.data.exchange_calendar, start.date(), now.date())
    out = []
    for c in sess["close"]:
        close: datetime = c.to_pydatetime()
        if since < close <= now:
            out.append(close)
    return out


def status(
    store: BaseStore, cfg: AfterhoursConfig, now: datetime, *, deployed: bool
) -> dict[str, Any]:
    """Automation health for the API. `healthy` is false for never_ran, missed and failed."""
    doc = store.read(DOC) or {"tracking_since": None, "heartbeat": None, "cycles": []}
    cycles: list[dict[str, Any]] = doc.get("cycles", [])
    hb = doc.get("heartbeat")
    since = _parse(doc.get("tracking_since"))
    finished = [c for c in cycles if c["status"] in ("completed", "failed")]
    completed = [c for c in cycles if c["status"] == "completed"]
    running = [c for c in cycles if c["status"] == "running" and not _timed_out(c, now, cfg)]
    pre = {c["close"]: c for c in cycles if c["kind"] == "pre_close"}
    expected = expected_closes(cfg, since, now) if since else []
    missed = [_iso(c) for c in expected if pre.get(_iso(c), {}).get("status") != "completed"]
    window = pre_close_window(cfg, now)
    later = sessions(cfg.data.exchange_calendar, now.date(), (now + timedelta(days=7)).date())
    upcoming = [c.to_pydatetime() for c in later["close"] if c.to_pydatetime() > now]

    if not deployed:
        state, detail = "not_applicable", f"No deployment for {cfg.active_profile}."
    elif not hb and not cycles:
        state, detail = "never_ran", "No scheduled job has reported in yet."
    elif running:
        state, detail = "running", f"Cycle {running[-1]['cycle_id']} is running."
    elif expected:
        last = pre.get(_iso(expected[-1]))
        if last and last["status"] == "completed":
            state = "ok"
            detail = f"The {_iso(expected[-1])} close ran and decided {last['decision']}."
        elif last and last["status"] == "failed":
            state, detail = "failed", f"The {_iso(expected[-1])} close failed: {last['error']}"
        else:
            state, detail = "missed", f"No pre-close cycle completed for {_iso(expected[-1])}."
    else:
        state, detail = "waiting_for_first_close", "Tracking started; no close has passed since."

    def brief(c: dict[str, Any] | None) -> dict[str, Any] | None:
        if c is None:
            return None
        keys = (
            "cycle_id",
            "kind",
            "status",
            "decision",
            "reason",
            "trigger_source",
            "run_ref",
            "started_at",
            "finished_at",
            "close",
            "error",
        )
        return {k: c.get(k) for k in keys}

    return {
        "status": state,
        "healthy": state in HEALTHY or state == "not_applicable",
        "detail": detail,
        "profile": cfg.active_profile,
        "checked_at": _iso(now),
        "tracking_since": doc.get("tracking_since"),
        "heartbeat": hb,
        "heartbeat_age_minutes": (
            round((now - _parse(hb["at"])).total_seconds() / 60, 1)  # type: ignore[operator]
            if hb
            else None
        ),
        "last_cycle": brief(finished[-1] if finished else None),
        "last_successful_cycle": brief(completed[-1] if completed else None),
        "expected_closes": [_iso(c) for c in expected],
        "missed_closes": missed,
        "current_window_close": _iso(window) if window else None,
        "next_close": _iso(upcoming[0]) if upcoming else None,
        "pre_close_minutes": cfg.schedule.pre_close_minutes,
        "recent_cycles": [brief(c) for c in reversed(cycles[-10:])],
    }
