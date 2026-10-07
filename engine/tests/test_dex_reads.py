"""DEX reads for the regime monitor: a failed read falls back to the public RPC, and a read
that fails everywhere is reported as unavailable, never as a token without a price."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from afterhours.chain.rpc import RpcError
from afterhours.config import load_config
from afterhours.live.mainnet import Mainnet

CFG = load_config(load_env_file=False)
NOW = datetime(2026, 10, 7, 16, tzinfo=UTC)


class FakeEth:
    block_number = 1_000


class FakeW3:
    eth = FakeEth()


def rows(live: Mainnet) -> list[dict[str, Any]]:
    return [
        {"symbol": s, "price": 100.0, "updated_at": NOW.isoformat()} for s in sorted(live.feeds)
    ]


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> Mainnet:
    m = Mainnet(CFG)
    m.w3_public = FakeW3()  # type: ignore[assignment]
    monkeypatch.setattr(m, "dex_depth", lambda prices, *a, **k: dict.fromkeys(prices, 50_000.0))
    return m


def test_primary_failure_falls_back_to_the_public_rpc(
    live: Mainnet, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "https://rpc.example/v2/sekret"  # hardcode-ok: test fixture

    def dex_prices(syms: list[str], block: int, deadline: Any, w3: Any) -> dict[str, Any]:
        if w3 is live.w3:
            raise RpcError(f"slot0() on 0xpool: rate limited at {secret}")
        return {s: 101.0 for s in syms}

    monkeypatch.setattr(live, "dex_prices", dex_prices)
    rs = rows(live)
    out = live.regimes(rs, NOW, 2_000, None)
    assert out["dex"]["source"] == "public"
    assert out["dex"]["block"] == FakeEth.block_number - CFG.live.lag_blocks
    assert "RpcError" in out["dex"]["errors"]["primary"]
    assert "sekret" not in out["dex"]["errors"]["primary"]
    assert all(r["regime"]["dex_price"] == 101.0 for r in rs)
    assert all(r["regime"]["dex_status"] == "ok" for r in rs)
    assert all("divergence" in r["regime"]["quality"]["used"] for r in rs)


def test_read_failing_everywhere_is_unavailable_not_missing(
    live: Mainnet, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*a: Any, **k: Any) -> dict[str, Any]:
        raise TimeoutError("budget spent")

    monkeypatch.setattr(live, "dex_prices", broken)
    rs = rows(live)
    out = live.regimes(rs, NOW, 2_000, None)
    assert out["dex"]["source"] is None
    assert set(out["dex"]["errors"]) == {"primary", "public"}
    assert {r["regime"]["dex_status"] for r in rs} == {"unavailable"}
    assert all(r["regime"]["dex_price"] is None for r in rs)
    assert all(r["regime"]["quality"]["used"] == ["staleness"] for r in rs)


def test_a_token_whose_pool_holds_no_price(live: Mainnet, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        live, "dex_prices", lambda syms, *a, **k: {s: (None if s == "NVDA" else 5.0) for s in syms}
    )
    rs = rows(live)
    out = live.regimes(rs, NOW, 2_000, None)
    assert out["dex"]["source"] == "primary"
    by = {r["symbol"]: r["regime"] for r in rs}
    assert by["NVDA"]["dex_status"] == "no_price"
    assert by["SPY"]["dex_status"] == "ok"


def test_failed_depth_requote_keeps_the_last_good_depth_with_its_age(
    live: Mainnet, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    monkeypatch.setattr(live, "dex_prices", lambda syms, *a, **k: dict.fromkeys(syms, 5.0))

    def rate_limited(*a: Any, **k: Any) -> dict[str, float]:
        raise TimeoutError("the node is rate limiting; out of time budget")

    monkeypatch.setattr(live, "dex_depth", rate_limited)
    rs = rows(live)
    out = live.regimes(rs, NOW, 2_000, None)
    assert "TimeoutError" in out["dex"]["depth_error"]
    assert out["dex"]["depth_as_of"] is None  # nothing quoted yet: no depth, said so
    assert all(r["regime"]["depth_usd"] is None for r in rs)
    live._depth = (time.time() - 600, {"NVDA": 120_000.0})
    rs = rows(live)
    out = live.regimes(rs, NOW, 2_000, None)
    assert out["dex"]["depth_as_of"] is not None
    assert {r["symbol"]: r["regime"]["depth_usd"] for r in rs}["NVDA"] == 120_000
