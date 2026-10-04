"""Live mainnet views under a slow or rate-limited node: nobody waits behind a refresh."""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import pytest

from afterhours.chain import rpc
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import load_config
from afterhours.live.mainnet import Mainnet, WarmingError


def test_rate_limited_node_cannot_outlast_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    clock, slept = [1000.0], []

    def sleep(seconds: float) -> None:  # a fake clock: sleeping moves time forward
        slept.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(rpc.time, "sleep", sleep)
    monkeypatch.setattr(rpc.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        rpc.httpx, "post", lambda *a, **k: httpx.Response(429, request=httpx.Request("POST", "x"))
    )
    w3 = connect("http://node.invalid")
    deadline = clock[0] + 5
    with pytest.raises(TimeoutError):
        call_many(w3, [Call("0x" + "11" * 20, "decimals()(uint8)")], deadline=deadline)
    # Without a budget the backoff would wait 1+2+4+8+16+30 s; with 5 s it stops early.
    assert sum(slept) < 5


@pytest.fixture
def board_env(monkeypatch: pytest.MonkeyPatch) -> tuple[Mainnet, threading.Event, list[int]]:
    live = Mainnet(load_config(load_env_file=False))
    release, calls = threading.Event(), []

    def slow_board(now: Any) -> dict[str, Any]:
        calls.append(1)
        release.wait(10)
        return {"stocks": [], "n": len(calls)}

    monkeypatch.setattr(live, "_board_now", slow_board)
    return live, release, calls


def test_first_visitors_get_still_reading_and_one_refresh(
    board_env: tuple[Mainnet, threading.Event, list[int]],
) -> None:
    live, release, calls = board_env
    start = time.monotonic()
    for _ in range(5):  # a burst of visitors
        with pytest.raises(WarmingError):
            live.board()
    assert time.monotonic() - start < 1  # nobody waited
    release.set()
    for _ in range(50):
        if live._board:
            break
        time.sleep(0.05)
    assert live.board()["n"] == 1
    assert calls == [1]  # one refresh, not five


def test_a_stale_board_is_served_at_once(
    board_env: tuple[Mainnet, threading.Event, list[int]],
) -> None:
    live, release, _calls = board_env
    live._board = (time.time() - 10 * live.cfg.live.board_cache_seconds, {"stocks": [], "n": 0})
    start = time.monotonic()
    assert live.board()["n"] == 0  # the old board, straight away
    assert time.monotonic() - start < 1
    release.set()


def test_api_says_still_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from afterhours.api.app import create_app

    def warming(self: Mainnet, *a: Any, **k: Any) -> dict[str, Any]:
        raise WarmingError("Still reading every Stock Token price feed on mainnet.")

    monkeypatch.setattr(Mainnet, "board", warming)
    res = TestClient(create_app(load_config(load_env_file=False))).get("/v1/live/board")
    assert res.status_code == 503
    assert res.json()["detail"].startswith("Still reading")
    assert res.headers.get("retry-after")


def test_rate_limited_calls_in_a_batch_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Alchemy answers HTTP 200 with a per-call 429 when compute units run out; retry those."""
    six = "0x" + "00" * 31 + "06"  # uint8 6, ABI-encoded as one 32-byte word
    replies = iter(
        [
            [
                {
                    "id": 0,
                    "error": {
                        "code": 429,
                        "message": "exceeded its compute units per second capacity",
                    },
                }
            ],
            [{"id": 0, "result": six}],
        ]
    )
    monkeypatch.setattr(rpc.time, "sleep", lambda s: None)
    monkeypatch.setattr(rpc, "_post_with_backoff", lambda *a, **k: next(replies))
    w3 = connect("http://node.invalid")
    assert call_many(w3, [Call("0x" + "11" * 20, "decimals()(uint8)")]) == [6]


# ---------------------------------------------------------------- a burst on a fresh process
def test_a_burst_on_a_fresh_process_builds_one_client(monkeypatch: pytest.MonkeyPatch) -> None:
    # Production 2026-10-04: 30 visitors during the warm-up each built a client, each started a
    # full board refresh, and the 512 MB host restarted. One client, one refresh.
    from afterhours.api import app as api
    from afterhours.live import mainnet

    built: list[int] = []

    class SlowMainnet:
        def __init__(self, cfg: Any) -> None:
            built.append(1)
            time.sleep(0.2)  # discovery files, RPC handles
            self.on_board = None

        def restore_board(self, snapshot: Any) -> None:
            pass

    monkeypatch.setattr(mainnet, "Mainnet", SlowMainnet)
    ctx = api.Context(load_config(load_env_file=False))
    got: list[Any] = []
    threads = [threading.Thread(target=lambda: got.append(ctx.mainnet())) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert built == [1]
    assert len({id(m) for m in got}) == 1


def test_a_restarted_process_shows_the_saved_board_at_once(
    board_env: tuple[Mainnet, threading.Event, list[int]],
) -> None:
    live, release, calls = board_env
    saved = {"network": "Robinhood Chain", "block": 7, "as_of": "earlier", "stocks": []}
    live.restore_board({"saved_at": 0, "board": saved})
    start = time.monotonic()
    assert live.board() == saved  # no "still reading" after a restart
    assert time.monotonic() - start < 1
    release.set()
    for _ in range(50):
        if calls and live._board and live._board[0] > 0:
            break
        time.sleep(0.05)
    assert calls == [1]  # and it reads a fresh one in the background


def test_a_fresh_board_is_saved_for_the_next_process(
    board_env: tuple[Mainnet, threading.Event, list[int]],
) -> None:
    live, release, _calls = board_env
    saved: list[dict[str, Any]] = []
    live.on_board = saved.append
    release.set()
    live.board(wait=True)
    assert saved == [{"stocks": [], "n": 1}]


def test_health_is_cheap_and_reports_the_process(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from afterhours.api import app as api

    reads: list[int] = []

    class FakeEth:
        @property
        def chain_id(self) -> int:
            reads.append(1)
            return 46630

        block_number = 1

    class FakeW3:
        eth = FakeEth()

    monkeypatch.setattr(api.Context, "w3", lambda self: FakeW3())
    client = TestClient(api.create_app(load_config(load_env_file=False)))
    for _ in range(5):  # a host's health checks, seconds apart
        body = client.get("/v1/health").json()
    assert reads == [1]  # the chain was read once, not five times
    assert body["process"]["uptime_seconds"] >= 0
    assert body["process"]["peak_rss_mb"] > 0
