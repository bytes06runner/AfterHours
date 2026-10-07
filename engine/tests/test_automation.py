"""Recorded pre-close cycles and automation health (bot/automation.py), without any chain.

The allocator is replaced by a fake runner, the clock is fixed, and the store is either local
files or the in-memory Upstash fake, so nothing here depends on an RPC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from afterhours.bot import automation
from afterhours.bot.allocator import CycleResult
from afterhours.config import load_config
from afterhours.state import KVStore, Store
from tests.fake_upstash import FakeUpstash

CFG = load_config(load_env_file=False)
REPO_ROOT = Path(__file__).resolve().parents[2]
# Wednesday 2026-10-07: NYSE closes 16:00 New York = 20:00 UTC (daylight time).
CLOSE = datetime(2026, 10, 7, 20, tzinfo=UTC)
IN_WINDOW = CLOSE - timedelta(minutes=53)
OUT_OF_WINDOW = CLOSE - timedelta(hours=5)


def plan(*, execute: bool = False, pulled: bool = False, turnover: float = 12.0) -> dict[str, Any]:
    return {
        "policy": "option_b",
        "now": IN_WINDOW.isoformat(),
        "status": "optimal",
        "execute": execute,
        "turnover_usdg": turnover,
        "idle_usdg": 81_000.0,
        "total_assets_usdg": 1_622_954.0,
        "allocation": {"META:weekday": 100.0},
        "decisions": {
            "META": {
                "mapped_tier": "weekday",
                "forecast_bad_case": 0.071 if pulled else 0.021,
                "pull_limit": 0.05,
                "pulled": pulled,
            },
            "SPY": {
                "mapped_tier": "weekday",
                "forecast_bad_case": 0.012,
                "pull_limit": 0.05,
                "pulled": False,
            },
        },
        "driving_forecast": {"META": {"model_version": "abc"}, "SPY": {"model_version": "abc"}},
    }


class FakeRunner:
    """Stands in for `Allocator`: returns a canned result, or raises."""

    def __init__(self, result: CycleResult | None = None, error: Exception | None = None):
        self.result = result or CycleResult("pre_close", IN_WINDOW.isoformat(), plan(), False)
        self.error = error
        self.calls: list[tuple[str, bool]] = []

    def run_cycle(self, trigger: str, *, execute: bool = True) -> CycleResult:
        self.calls.append((trigger, execute))
        if self.error:
            raise self.error
        return self.result


def due(store: Any, runner: FakeRunner, now: datetime, **kw: Any) -> dict[str, Any]:
    return automation.run_due(
        store,
        CFG,
        source=kw.pop("source", "schedule"),
        run_ref=kw.pop("run_ref", "github-actions:1"),
        make_runner=lambda: runner,
        clock=lambda: now,
        **kw,
    )


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path)


def test_scheduled_run_in_window_records_a_hold(store: Store) -> None:
    runner = FakeRunner()
    out = due(store, runner, IN_WINDOW)
    assert out["outcome"] == "completed"
    assert runner.calls == [("pre_close", True)]
    rec = out["cycle"]
    assert rec["cycle_id"] == f"pre_close:{CLOSE.isoformat()}"
    assert rec["status"] == "completed"
    assert rec["decision"] == "hold"
    assert "no forecast bad case crossed its pullback limit" in rec["reason"]
    assert rec["trigger_source"] == "schedule"
    assert rec["run_ref"] == "github-actions:1"
    assert rec["policy"]["name"] == "option_b"
    assert rec["policy"]["pullback_fraction"] == CFG.policy.pullback_fraction
    assert rec["inputs"]["stocks"]["META"]["pull_limit"] == 0.05
    assert rec["inputs"]["model_version"] == "abc"
    assert len(rec["inputs"]["plan_sha256"]) == 64
    assert rec["started_at"]
    assert rec["finished_at"]
    doc = automation.load(store)
    assert doc["heartbeat"]["in_window"] is True


def test_act_records_transactions_and_pulled_stocks(store: Store) -> None:
    result = CycleResult(
        "pre_close",
        IN_WINDOW.isoformat(),
        plan(execute=True, pulled=True),
        True,
        txs=["0xaa", "0xbb"],
        reasons=["card-1"],
    )
    rec = due(store, FakeRunner(result), IN_WINDOW)["cycle"]
    assert rec["decision"] == "act"
    assert rec["txs"] == ["0xaa", "0xbb"]
    assert rec["reason_ids"] == ["card-1"]
    assert "Pulled: META" in rec["reason"]


def test_hold_when_already_pulled(store: Store) -> None:
    result = CycleResult("pre_close", IN_WINDOW.isoformat(), plan(pulled=True), False)
    rec = due(store, FakeRunner(result), IN_WINDOW)["cycle"]
    assert rec["decision"] == "hold"
    assert "META over the pullback limit, already out of the market" in rec["reason"]


def test_outside_window_only_heartbeat(store: Store) -> None:
    runner = FakeRunner()
    out = due(store, runner, OUT_OF_WINDOW)
    assert out == {"outcome": "not_due", "cycle": None}
    assert runner.calls == []
    doc = automation.load(store)
    assert doc["heartbeat"]["in_window"] is False
    assert doc["cycles"] == []


def test_manual_dispatch_forces_a_manual_cycle(store: Store) -> None:
    runner = FakeRunner()
    out = due(store, runner, OUT_OF_WINDOW, source="workflow_dispatch", run_ref="gh:9", force=True)
    rec = out["cycle"]
    assert rec["kind"] == "manual"
    assert rec["cycle_id"] == "manual:gh:9"
    assert rec["trigger_source"] == "workflow_dispatch"
    assert runner.calls == [("manual", True)]
    # A manual cycle never stands in for a scheduled close.
    st = automation.status(store, CFG, CLOSE + timedelta(minutes=5), deployed=True)
    assert st["status"] == "missed"
    assert st["last_cycle"]["kind"] == "manual"


def test_manual_dispatch_inside_window_runs_the_close_cycle(store: Store) -> None:
    out = due(store, FakeRunner(), IN_WINDOW, source="workflow_dispatch", force=True)
    assert out["cycle"]["kind"] == "pre_close"


def test_duplicate_invocation_runs_once(store: Store) -> None:
    runner = FakeRunner()
    due(store, runner, IN_WINDOW)
    again = due(store, runner, IN_WINDOW + timedelta(minutes=10), run_ref="github-actions:2")
    assert again["outcome"] == "already_done"
    assert len(runner.calls) == 1
    assert len(automation.load(store)["cycles"]) == 1


def test_duplicate_while_running_is_blocked_until_timeout(store: Store) -> None:
    doc = automation.load(store)
    doc["cycles"].append(
        {
            "cycle_id": f"pre_close:{CLOSE.isoformat()}",
            "kind": "pre_close",
            "status": "running",
            "started_at": IN_WINDOW.isoformat(),
            "attempt": 1,
            "close": CLOSE.isoformat(),
        }
    )
    store.write(automation.DOC, doc)
    runner = FakeRunner()
    assert due(store, runner, IN_WINDOW + timedelta(minutes=5))["outcome"] == "in_progress"
    assert runner.calls == []
    late = IN_WINDOW + timedelta(minutes=CFG.automation.running_timeout_minutes + 1)
    out = due(store, runner, late)
    assert out["outcome"] == "completed"
    assert out["cycle"]["attempt"] == 2
    cycles = automation.load(store)["cycles"]
    assert cycles[0]["status"] == "failed"
    assert "timed out" in cycles[0]["error"]


def test_failure_is_recorded_redacted_and_retried(store: Store) -> None:
    secret_url = "https://rpc.example/v2/sekret-key"  # hardcode-ok: test fixture
    bad = FakeRunner(error=ConnectionError(f"cannot reach {secret_url}"))
    with pytest.raises(ConnectionError):
        due(store, bad, IN_WINDOW)
    rec = automation.load(store)["cycles"][-1]
    assert rec["status"] == "failed"
    assert "ConnectionError" in rec["error"]
    assert "sekret-key" not in rec["error"]
    st = automation.status(store, CFG, CLOSE + timedelta(minutes=1), deployed=True)
    assert st["status"] == "failed"
    assert st["healthy"] is False
    # The next run in the window retries and succeeds.
    out = due(store, FakeRunner(), IN_WINDOW + timedelta(minutes=10))
    assert out["outcome"] == "completed"
    assert out["cycle"]["attempt"] == 2
    st = automation.status(store, CFG, CLOSE + timedelta(minutes=1), deployed=True)
    assert st["status"] == "ok"


def test_health_tells_never_ran_from_ran_and_held(store: Store) -> None:
    after = CLOSE + timedelta(hours=1)
    st = automation.status(store, CFG, after, deployed=True)
    assert st["status"] == "never_ran"
    assert st["healthy"] is False
    automation.heartbeat(store, CFG, OUT_OF_WINDOW, "schedule", "r1")
    st = automation.status(store, CFG, OUT_OF_WINDOW + timedelta(minutes=1), deployed=True)
    assert st["status"] == "waiting_for_first_close"
    assert st["healthy"] is True
    assert st["heartbeat"]["run_ref"] == "r1"
    # The close passes with heartbeats but no cycle: missed, unhealthy.
    st = automation.status(store, CFG, after, deployed=True)
    assert st["status"] == "missed"
    assert st["missed_closes"] == [CLOSE.isoformat()]
    due(store, FakeRunner(), IN_WINDOW)
    st = automation.status(store, CFG, after, deployed=True)
    assert st["status"] == "ok"
    assert st["healthy"] is True
    assert st["last_cycle"]["decision"] == "hold"
    assert st["last_successful_cycle"]["cycle_id"] == f"pre_close:{CLOSE.isoformat()}"
    assert st["missed_closes"] == []
    assert st["next_close"] == "2026-10-08T20:00:00+00:00"


def test_heartbeat_ages_and_profiles_without_deployment(store: Store) -> None:
    st = automation.status(store, CFG, CLOSE, deployed=False)
    assert st["status"] == "not_applicable"
    automation.heartbeat(store, CFG, IN_WINDOW, "schedule", None)
    st = automation.status(store, CFG, IN_WINDOW + timedelta(minutes=30), deployed=True)
    assert st["heartbeat_age_minutes"] == 30.0
    assert st["current_window_close"] == CLOSE.isoformat()


def test_shared_store_two_processes_run_once() -> None:
    up = FakeUpstash()
    first, second = KVStore(up.kv(), "rh-testnet", CFG), KVStore(up.kv(), "rh-testnet", CFG)
    runner = FakeRunner()
    due(first, runner, IN_WINDOW)
    second.read(automation.DOC)  # warm the second process's read cache before it runs
    assert due(second, runner, IN_WINDOW + timedelta(minutes=10))["outcome"] == "already_done"
    assert len(runner.calls) == 1


def test_workflow_covers_every_pre_close_window() -> None:
    """Each weekday window (regular and early closes, both offsets from UTC) gets many runs."""
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "pre-close.yml").read_text())
    on = wf[True]  # YAML 1.1 reads the key `on` as True
    assert "workflow_dispatch" in on
    assert on["workflow_dispatch"]["inputs"]["force_cycle"]["type"] == "boolean"
    minutes: set[tuple[int, int]] = set()
    for entry in on["schedule"]:
        minute, hour, _, _, dow = entry["cron"].split()
        assert dow == "1-5"
        m_range, m_step = minute.split("/")
        m0, m1 = (int(x) for x in m_range.split("-"))
        h0, h1 = (int(x) for x in hour.split("-"))
        minutes |= {(h, m) for h in range(h0, h1 + 1) for m in range(m0, m1 + 1, int(m_step))}
    lead = CFG.schedule.pre_close_minutes
    for close_hour in (17, 18, 20, 21):  # early and regular closes, daylight and standard time
        start = close_hour * 60 - lead
        inside = [hm for hm in minutes if start <= hm[0] * 60 + hm[1] < close_hour * 60]
        assert len(inside) >= 5, close_hour
    steps = {s.get("name", ""): s for s in wf["jobs"]["pre-close"]["steps"]}
    window = steps["Heartbeat; inside a pre-close window?"]["run"]
    assert "--heartbeat" in window
    assert "--run-ref" in window
    bot = steps["Bot pre-close cycle"]["run"]
    assert "afterhours bot due" in bot
    assert "--source" in bot


def test_api_automation_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from afterhours.api.app import Context, create_app

    files = Store(tmp_path)
    monkeypatch.setattr(Store, "for_profile", classmethod(lambda cls, cfg, profile=None: files))
    monkeypatch.setattr(Context, "now", lambda self: CLOSE + timedelta(hours=1))
    import time

    # /v1/automation is cached for api.health_chain_cache_seconds: the shortest, 1 s, here.
    fast = CFG.model_copy(
        update={"api": CFG.api.model_copy(update={"health_chain_cache_seconds": 1})}
    )
    client = TestClient(create_app(fast))
    health = client.get("/v1/health")
    assert health.status_code == 200
    assert health.json()["service"] == "ok"
    assert health.json()["automation"]["heartbeat_at"] is None  # never ran, said cheaply
    r = client.get("/v1/automation")
    assert r.status_code == 200
    if r.json()["status"] == "never_ran":
        assert client.get("/v1/automation?strict=true").status_code == 503
    due(files, FakeRunner(), IN_WINDOW)
    time.sleep(1.1)
    r = client.get("/v1/automation?strict=true")
    assert r.json()["last_cycle"]["decision"] == "hold"
    if r.json()["status"] != "not_applicable":
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_dry_run_is_recorded_as_dry_run_not_hold(store: Store) -> None:
    from afterhours.bot.automation import run_recorded

    result = CycleResult("manual", IN_WINDOW.isoformat(), plan(execute=True, pulled=True), False)
    out = run_recorded(
        store,
        CFG,
        cycle_id="manual:cli:test",
        kind="manual",
        close=None,
        source="cli:smoke",
        run_ref=None,
        make_runner=lambda: FakeRunner(result),
        clock=lambda: IN_WINDOW,
        execute=False,
    )
    rec = out["cycle"]
    assert rec["decision"] == "dry_run"
    assert rec["executed"] is False
    assert "Dry run, nothing sent: the plan would move money" in rec["reason"]
    assert "META" in rec["reason"]


def test_close_done_lets_later_runs_skip_the_work(store: Store) -> None:
    from afterhours.bot.automation import close_done

    assert close_done(store, CLOSE) is False
    with pytest.raises(ConnectionError):  # a failed cycle is not done: the next run retries
        due(store, FakeRunner(error=ConnectionError("down")), IN_WINDOW)
    assert close_done(store, CLOSE) is False
    due(store, FakeRunner(), IN_WINDOW + timedelta(minutes=10))
    assert close_done(store, CLOSE) is True


def test_workflow_skips_prices_and_bot_once_the_close_is_done() -> None:
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "pre-close.yml").read_text())
    steps = {s.get("name", ""): s for s in wf["jobs"]["pre-close"]["steps"]}
    window = steps["Heartbeat; inside a pre-close window?"]["run"]
    assert '"$window" = done' in window
    for name in ("Refresh every Stock Token's prices", "Bot pre-close cycle"):
        assert steps[name]["if"] == "steps.window.outputs.cycle == 'true'"
    assert "steps.window.outputs.due == 'true'" in steps["Telegram pre-close alerts"]["if"]


def test_status_agrees_with_the_window_and_expected_closes(store: Store) -> None:
    """status() builds one schedule; it must match pre_close_window and expected_closes."""
    from afterhours.bot.automation import expected_closes
    from afterhours.bot.scheduler import pre_close_window

    automation.heartbeat(store, CFG, CLOSE - timedelta(days=3), "schedule", None)
    since = automation.load(store)["tracking_since"]
    for now in (IN_WINDOW, CLOSE + timedelta(hours=1), datetime(2026, 10, 10, 12, tzinfo=UTC)):
        st = automation.status(store, CFG, now, deployed=True)
        w = pre_close_window(CFG, now)
        assert st["current_window_close"] == (w.isoformat() if w else None)
        exp = expected_closes(CFG, datetime.fromisoformat(since), now)
        assert st["expected_closes"] == [c.isoformat() for c in exp]
        assert st["next_close"] > now.isoformat()


def test_health_reads_the_record_without_calendar_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    from afterhours.api.app import Context, create_app

    files = Store(tmp_path)
    monkeypatch.setattr(Store, "for_profile", classmethod(lambda cls, cfg, profile=None: files))
    monkeypatch.setattr(Context, "now", lambda self: CLOSE + timedelta(hours=1))
    due(files, FakeRunner(), IN_WINDOW)

    def no_calendar(*a: Any, **k: Any) -> Any:
        raise AssertionError("health must not build an exchange schedule")

    client = TestClient(create_app(CFG))
    monkeypatch.setattr(automation, "sessions", no_calendar)
    monkeypatch.setattr(automation, "pre_close_window", no_calendar)
    h = client.get("/v1/health").json()["automation"]
    assert h["last_decision"] == "hold"
    assert h["last_status"] == "completed"
    assert h["heartbeat_at"] == IN_WINDOW.isoformat()
    assert h["detail"] == "/v1/automation"
