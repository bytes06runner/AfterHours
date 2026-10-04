"""Weekend risk for AI agents: the four documents, the REST routes and the rate limit."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from afterhours import agents
from afterhours.config import load_config

CFG = load_config(load_env_file=False)

BOARD: dict[str, Any] = {
    "network": "Robinhood Chain",
    "block": 79871857,
    "as_of": "2026-10-04T10:40:36+00:00",
    "regimes": {
        "calendar": "closed",
        "segment": "frozen",
        "closed_since": "2026-10-03T00:00:00+00:00",
        "counts": {"regular": 0, "extended": 0, "weekend_venue": 0, "frozen": 2},
    },
    "stocks": [
        {
            "symbol": "NVDA",
            "price": 234.99,
            "markets": [{"lltv": 0.625, "cushion": 0.33}, {"lltv": 0.915, "cushion": 0.061}],
            "breached": [0.915],
            "tonight": {
                "symbol": "NVDA",
                "alpha": 0.01,
                "bad_case_drop": 0.071,
                "period": {
                    "starts": "2026-10-02T20:00:00+00:00",
                    "ends": "2026-10-05T13:30:00+00:00",
                    "segment": "weekend",
                    "hours": 65.5,
                },
            },
            "regime": {
                "regime": "frozen",
                "label": "Frozen",
                "line": (
                    "Frozen since Friday 20:00 New York: the feed has posted nothing for 42 hours."
                ),
                "quality": {"score": 58, "grade": "fair", "marks": {}, "used": []},
            },
        },
        {"symbol": "SPY", "price": 700.0, "markets": [], "breached": [], "tonight": None},
    ],
}


def test_weekend_risk_summary() -> None:
    doc = agents.weekend_risk(BOARD, " nvda ")
    assert doc["symbol"] == "NVDA"
    assert doc["bad_case_drop"] == pytest.approx(0.071)
    s = doc["summary"]
    assert s.startswith("Frozen since Friday 20:00 New York")
    assert "1 night in 100, is 7.1%" in s
    assert "beyond the cushion of 1 of 2 USDG Morpho markets" in s
    assert "Fri Oct 2, 16:00 New York" in s
    assert s.endswith(agents.DISCLAIMER)
    assert "—" not in s
    spy = agents.weekend_risk(BOARD, "SPY")["summary"]
    assert "no bad-case forecast" in spy
    with pytest.raises(KeyError):
        agents.weekend_risk(BOARD, "XYZ")


def test_market_status_summary() -> None:
    status = {
        "now": "2026-10-04T10:00:00+00:00",
        "state": "closed",
        "next_open": "2026-10-05T13:30:00+00:00",
        "next_close": "2026-10-05T20:00:00+00:00",
        "seconds_to_open": 99000,
        "seconds_to_close": 122400,
    }
    doc = agents.market_status(status, BOARD["regimes"])
    assert doc["feeds_window"] == "closed"
    assert "opens at Mon Oct 5, 09:30 New York" in doc["summary"]
    assert "began at Fri Oct 2, 20:00 New York" in doc["summary"]
    assert "2 frozen" in doc["summary"]
    assert agents.market_status(status, None)["regime_counts"] is None


def test_position_check_summary() -> None:
    doc = agents.position_check(
        {
            "address": "0x" + "ab" * 20,
            "network": "Robinhood Chain",
            "block": 1,
            "as_of": "2026-10-04T10:00:00+00:00",
            "positions": [
                {
                    "symbol": "NVDA",
                    "market_id": "0x01",
                    "lltv": 0.625,
                    "borrowed": 99000.81,
                    "loan_symbol": "USDG",
                    "collateral_tokens": 1300.0,
                    "ltv": 0.337,
                    "liquidation_price": 121.85,
                    "drop_to_liquidation": 0.46,
                    "tonight": {"bad_case_drop": 0.071},
                    "breach_tonight": False,
                },
                {
                    "symbol": "SPY",
                    "market_id": "0x02",
                    "lltv": 0.77,
                    "borrowed": 0,
                    "collateral_tokens": 1.0,
                },
            ],
        }
    )
    assert len(doc["loans"]) == 1  # supply-only or empty positions are not loans
    assert "99,000.81 USDG borrowed at 62.5% LLTV" in doc["summary"]
    assert "does not reach it" in doc["summary"]


def test_rate_limiter_and_client_address() -> None:
    rl = agents.RateLimiter(per_minute=60, burst=2, max_clients=2)
    assert rl.take("a", now=0) == 0
    assert rl.take("a", now=0) == 0
    assert rl.take("a", now=0) == pytest.approx(1.0)  # empty: one token a second
    assert rl.take("a", now=1.0) == 0
    rl.take("b", now=2)
    rl.take("c", now=3)
    assert len(rl._buckets) == 2  # the least recently seen client is forgotten
    # Render appends the real client; entries to its left are the caller's claims.
    assert agents.client_address("1.1.1.1, 9.9.9.9", "10.0.0.1", 1) == "9.9.9.9"
    assert agents.client_address(None, "10.0.0.1", 1) == "10.0.0.1"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from afterhours.api.app import Context, create_app
    from afterhours.live.mainnet import Mainnet

    monkeypatch.setattr(Mainnet, "board", lambda self, *a, **k: BOARD)
    # The default profile reads its clock from a local chain; a fixed Saturday instead.
    monkeypatch.setattr(Context, "now", lambda self: datetime(2026, 10, 4, 10, tzinfo=UTC))
    return TestClient(create_app(CFG))


def test_agent_routes(client: TestClient) -> None:
    r = client.get("/v1/agent/weekend-risk/nvda")
    assert r.status_code == 200
    assert r.json()["beyond_cushion_of"] == [0.915]
    r = client.get("/v1/agent/weekend-risk/XYZ")
    assert r.status_code == 404
    assert "Known: NVDA, SPY" in r.json()["detail"]
    r = client.get("/v1/agent/market-status")
    assert r.status_code == 200
    assert r.json()["regime_counts"]["frozen"] == 2
    assert client.get("/v1/agent/moves/no-such-card").status_code == 404
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("market-status", "weekend-risk/{ticker}", "positions/{address}", "moves/{reason_id}"):
        assert f"/v1/agent/{p}" in paths
        assert list(paths[f"/v1/agent/{p}"]) == ["get"]  # read-only


def test_agent_routes_are_rate_limited(client: TestClient) -> None:
    burst = CFG.agents.rate_limit_burst
    codes = [
        client.get(
            "/v1/agent/market-status", headers={"x-forwarded-for": "203.0.113.7"}
        ).status_code
        for _ in range(burst + 1)
    ]
    assert codes[:burst] == [200] * burst
    assert codes[burst] == 429
    other = client.get("/v1/agent/market-status", headers={"x-forwarded-for": "203.0.113.8"})
    assert other.status_code == 200  # per client
    assert client.get("/v1/health").status_code == 200  # only /v1/agent/ is limited
