"""The shared store (Upstash Redis over REST), the Telegram webhook and the free-hosting files."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from afterhours.config import REPO_ROOT, AfterhoursConfig, load_config
from afterhours.kv import KVError
from afterhours.live import alerts
from afterhours.live.alerts import Store as Subscriptions
from afterhours.live.alerts import handle, run_checks
from afterhours.state import KVStore
from tests.fake_upstash import FakeUpstash

HOSTED_SECRETS = {
    "ALLOCATOR_PK",
    "TELEGRAM_BOT_TOKEN",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "RH_MAINNET_RPC_URL",
    "RH_TESTNET_RPC_URL",
    "ARB_SEPOLIA_RPC_URL",
}
NEVER_HOSTED = {"DEPLOYER_PK", "CURATOR_PK", "GUARDIAN_PK"}


@pytest.fixture
def cfg() -> AfterhoursConfig:
    return load_config(load_env_file=False)


def test_bot_history_round_trip(cfg: AfterhoursConfig) -> None:
    up = FakeUpstash()
    store = KVStore(up.kv(), "rh-testnet", cfg)
    assert store.events_end() == 0
    store.emit("plan_changed", {"n": 1})
    store.emit("reason_logged", {"n": 2})
    events, end = store.events_since(0)
    assert [e["type"] for e in events] == ["plan_changed", "reason_logged"]
    assert store.events_since(end) == ([], 2)
    store.add_reason({"id": "a"})
    store.add_reason({"id": "b"})
    assert [c["id"] for c in store.reasons()] == ["b", "a"]  # newest first
    store.write("plan", {"allocation": [1, 2]})
    assert store.read("plan") == {"allocation": [1, 2]}
    # Another process (the API) sees the same history.
    other = KVStore(up.kv(), "rh-testnet", cfg)
    assert other.read("plan") == {"allocation": [1, 2]}
    assert other.events_end() == 2
    # Profiles do not mix.
    assert KVStore(up.kv(), "arb-sepolia", cfg).read("plan") is None


def test_reads_are_cached(cfg: AfterhoursConfig) -> None:
    up = FakeUpstash()
    writer, reader = KVStore(up.kv(), "p", cfg), KVStore(up.kv(), "p", cfg)
    writer.write("plan", {"v": 1})
    assert reader.read("plan") == {"v": 1}
    before = up.calls
    for _ in range(50):
        reader.read("plan")
        reader.events_end()
    assert up.calls - before == 1  # one LLEN; the plan came from the cache


def test_cycle_lock_is_exclusive(cfg: AfterhoursConfig) -> None:
    up = FakeUpstash()
    a, b = KVStore(up.kv(), "p", cfg), KVStore(up.kv(), "p", cfg)
    with a.lock("cycle"):
        held = [k for k in up.data if k.endswith(":lock:cycle")]
        assert held
        assert up.run(["SET", held[0], "x", "NX", "EX", "5"]) is None
    assert not [k for k in up.data if k.endswith(":lock:cycle")]
    with b.lock("cycle"):
        pass


def test_bad_token_is_an_error() -> None:
    up = FakeUpstash()
    kv = up.kv()
    kv._http.headers["Authorization"] = "Bearer wrong"
    with pytest.raises(KVError, match="Unauthorized"):
        kv.cmd("GET", "x")


def test_api_and_job_do_not_overwrite_each_other() -> None:
    up = FakeUpstash()
    ttl = 7 * 86400
    job = Subscriptions.load_kv(up.kv(), ttl)  # the scheduled job loads first
    api = Subscriptions.load_kv(up.kv(), ttl)
    handle(api, 5, "/watch NVDA", {"NVDA"}, "x", 5)
    api.save_chat(5)

    class Quiet:
        def __init__(self) -> None:
            self.feeds = {"NVDA": "0x1"}

        def board(self, now: datetime | None = None, *, wait: bool = False) -> dict[str, Any]:
            return {"stocks": []}

        def positions(self, address: str, now: datetime | None = None) -> dict[str, Any]:
            return {"positions": []}

    close = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    run_checks(job, Quiet(), close, close)
    job.save_checked()
    again = Subscriptions.load_kv(up.kv(), ttl)
    assert again.chats["5"]["symbols"] == ["NVDA"]  # the API's write survived
    assert close.isoformat() in again.checked
    handle(again, 5, "/stop", {"NVDA"}, "x", 5)
    again.save_chat(5)
    assert Subscriptions.load_kv(up.kv(), ttl).chats == {}


# ---------------------------------------------------------------- the webhook
class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.fixture
def webhook(
    monkeypatch: pytest.MonkeyPatch, cfg: AfterhoursConfig
) -> tuple[TestClient, FakeUpstash, FakeTelegram]:
    from afterhours.api.app import create_app

    up, tg = FakeUpstash(), FakeTelegram()
    monkeypatch.setenv(cfg.alerts.token_env, "123:abc")
    monkeypatch.setenv(cfg.alerts.webhook_secret_env, "s3cret_token")
    monkeypatch.setattr(alerts, "kv_from_config", lambda _cfg: up.kv())
    monkeypatch.setattr(alerts, "telegram_from_config", lambda _cfg: tg)
    return TestClient(create_app(cfg)), up, tg


def update(text: str, chat: int = 42) -> dict[str, Any]:
    return {"update_id": 1, "message": {"chat": {"id": chat}, "text": text}}


def test_webhook_needs_the_secret(
    webhook: tuple[TestClient, FakeUpstash, FakeTelegram], cfg: AfterhoursConfig
) -> None:
    client, up, tg = webhook
    path, header = cfg.alerts.webhook_path, cfg.alerts.webhook_secret_header
    assert client.post(path, json=update("/watch NVDA")).status_code == 403
    assert (
        client.post(path, json=update("/watch NVDA"), headers={header: "nope"}).status_code == 403
    )
    assert tg.sent == []
    assert up.data == {}


def test_webhook_answers_and_saves(
    webhook: tuple[TestClient, FakeUpstash, FakeTelegram], cfg: AfterhoursConfig
) -> None:
    client, up, tg = webhook
    path, header = cfg.alerts.webhook_path, cfg.alerts.webhook_secret_header
    res = client.post(path, json=update("/watch nvda"), headers={header: "s3cret_token"})
    assert res.status_code == 200
    assert tg.sent == [(42, tg.sent[0][1])]
    assert tg.sent[0][1].startswith("Following NVDA")
    subs = Subscriptions.load_kv(up.kv(), 60)
    assert subs.chats["42"]["symbols"] == ["NVDA"]


def test_webhook_off_without_config(monkeypatch: pytest.MonkeyPatch, cfg: AfterhoursConfig) -> None:
    from afterhours.api.app import create_app

    monkeypatch.delenv(cfg.alerts.webhook_secret_env, raising=False)
    client = TestClient(create_app(cfg))
    assert client.post(cfg.alerts.webhook_path, json=update("/help")).status_code == 404


# ---------------------------------------------------------------- free hosting files
def workflow() -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "pre-close.yml").read_text()
    )
    return doc


def secrets_in(obj: Any) -> set[str]:
    return set(re.findall(r"secrets\.([A-Z0-9_]+)", yaml.safe_dump(obj)))


def test_workflow_gets_only_hosted_secrets() -> None:
    wf = workflow()
    used = secrets_in(wf)
    assert used <= HOSTED_SECRETS
    assert not used & NEVER_HOSTED
    (job,) = wf["jobs"].values()
    # Each key reaches only the step that uses it.
    assert not {"ALLOCATOR_PK", "TELEGRAM_BOT_TOKEN"} & secrets_in(job["env"])
    by_step = {s.get("name", ""): secrets_in(s) for s in job["steps"]}
    assert by_step["Bot pre-close cycle"] == {"ALLOCATOR_PK"}
    assert by_step["Telegram pre-close alerts"] == {"TELEGRAM_BOT_TOKEN"}


def test_workflow_env_names_match_config(cfg: AfterhoursConfig) -> None:
    env = set(workflow()["jobs"]["pre-close"]["env"])
    assert {cfg.state.kv_url_env, cfg.state.kv_token_env} <= env


def test_free_render_blueprint(cfg: AfterhoursConfig) -> None:
    doc = yaml.safe_load((REPO_ROOT / "render.free.yaml").read_text())
    (svc,) = doc["services"]
    keys = {e["key"] for e in svc["envVars"]}
    assert svc["plan"] == "free"
    assert "disk" not in svc
    assert {cfg.alerts.webhook_secret_env, cfg.state.kv_url_env, cfg.state.kv_token_env} <= keys
    # The free API never signs: no private key at all.
    assert not keys & (NEVER_HOSTED | {"ALLOCATOR_PK"})


def test_copy_local_history_to_shared(tmp_path: Any, cfg: AfterhoursConfig) -> None:
    from afterhours.state import Store, copy_to_shared

    src = Store(tmp_path)
    for i in range(3):
        src.emit("plan_changed", {"n": i})
    for card in ({"id": "first"}, {"id": "second"}):
        src.add_reason(card)
    src.write("plan", {"allocation": [1]})
    (tmp_path / "cycle.lock").write_text("")  # locks are not copied

    up = FakeUpstash()
    dst = KVStore(up.kv(), "rh-testnet", cfg)
    assert copy_to_shared(src, dst, dry_run=True) == {"events": 3, "reasons": 2, "documents": 1}
    assert up.data == {}  # a dry run writes nothing
    assert copy_to_shared(src, dst) == {"events": 3, "reasons": 2, "documents": 1}

    fresh = KVStore(up.kv(), "rh-testnet", cfg)  # what the hosted API sees
    assert fresh.events_since(0)[0] == src.events_since(0)[0]  # same events, same timestamps
    assert [c["id"] for c in fresh.reasons()] == ["second", "first"]  # newest first, as locally
    assert fresh.read("plan") == {"allocation": [1]}
    assert not [k for k in up.data if "lock" in k]
    with pytest.raises(ValueError, match="already has history"):
        copy_to_shared(src, dst)  # a second run cannot duplicate
    assert fresh.events_end() == 3


def test_anvil_profiles_never_use_the_shared_store(
    monkeypatch: pytest.MonkeyPatch, cfg: AfterhoursConfig, tmp_path: Any
) -> None:
    from afterhours.state import Store

    monkeypatch.setenv(cfg.state.kv_url_env, "https://kv.test")
    monkeypatch.setenv(cfg.state.kv_token_env, "t")
    paths = cfg.paths.model_copy(update={"state_dir": str(tmp_path)})
    c = cfg.model_copy(update={"paths": paths})
    assert isinstance(Store.for_profile(c, "local"), Store)
    assert isinstance(Store.for_profile(c, "fork"), Store)
    assert isinstance(Store.for_profile(c, "rh-testnet"), KVStore)
