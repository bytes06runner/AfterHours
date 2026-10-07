"""The curator view (live/curator.py and Mainnet.curator), without any RPC."""

from __future__ import annotations

from typing import Any

import pytest

from afterhours.config import load_config
from afterhours.live import curator as cur
from afterhours.live.mainnet import Mainnet

CFG = load_config(load_env_file=False)
LLTVS = [0.0, 0.385, 0.625, 0.77, 0.86, 0.915, 0.945, 0.965, 0.98]


def stock(
    drop: float | None, *, segment: str = "weekend", state: str = "updating", grade: str = "good"
) -> dict[str, Any]:
    tonight = None
    if drop is not None:
        tonight = {
            "bad_case_drop": drop,
            "alpha": 0.01,
            "period": {"starts": "s", "ends": "e", "segment": segment, "hours": 65.5},
            "held_out_miss_rate": 0.017257,
            "held_out_years": [2017, 2026],
            "model_version": "abc",
        }
    return {
        "symbol": "NVDA",
        "price": 237.0,
        "updated_at": "2026-10-07T15:00:00+00:00",
        "status": {"state": state},
        "regime": {
            "regime": "regular",
            "label": "Regular session",
            "quality": {"score": 90, "grade": grade},
        },
        "tonight": tonight,
    }


def market(
    lltv: float = 0.625, supplied: float = 1000.0, borrowed: float = 500.0
) -> dict[str, Any]:
    return {
        "id": "0x01",
        "symbol": "NVDA",
        "lltv": lltv,
        "supplied": supplied,
        "borrowed": borrowed,
    }


def test_cushion_matches_the_board_and_the_vault() -> None:
    from afterhours.policy.lp import tier_spec

    for lv in (0.625, 0.77, 0.86, 0.915):
        assert cur.cushion(lv) == pytest.approx(tier_spec("x", lv).cushion)
    # Morpho's incentive at 62.5% LLTV (M1 discovery: cushion 0.295775).
    assert cur.cushion(0.625) == pytest.approx(0.295775, abs=1e-6)


def test_breach_means_reduce_cap_and_names_the_lltv_that_survives() -> None:
    r = cur.market_row(CFG, market(lltv=0.915), stock(0.071), LLTVS)
    assert r["breach"] is True
    assert r["recommendation"] == "reduce_cap"
    assert r["label"] == "Reduce cap"
    assert r["highest_surviving_lltv"] == 0.86  # cushion 10.2% > 7.1%
    assert "beyond this market's 6.1% cushion" in r["reason"]
    assert "highest enabled LLTV that survives it is 86.0%" in r["reason"]


def test_inside_cushion_but_past_the_vaults_margin_is_do_not_increase() -> None:
    c = cur.cushion(0.86)  # 10.2%; margin limit = c * (1 - 0.4) = 6.1%
    r = cur.market_row(CFG, market(lltv=0.86), stock(c * 0.8), LLTVS)
    assert r["breach"] is False
    assert r["recommendation"] == "do_not_increase"
    assert r["margin_limit"] == pytest.approx(c * (1 - CFG.policy.pullback_fraction))


def test_full_market_is_watch_with_exit_liquidity() -> None:
    r = cur.market_row(CFG, market(supplied=259_785, borrowed=259_785), stock(0.02), LLTVS)
    assert r["recommendation"] == "watch"
    assert r["utilization"] == pytest.approx(1.0)
    assert r["exit_liquidity_usdg"] == 0
    assert "lenders can withdraw only 0 USDG" in r["reason"]


def test_concentration_is_a_watch_reason_feed_state_is_shown_not_counted() -> None:
    r = cur.market_row(CFG, market(), stock(0.02), LLTVS, {"count": 2, "top_share": 0.9})
    assert r["recommendation"] == "watch"
    assert r["watch"] == ["one borrower holds 90.0% of the debt"]
    # A frozen weekend feed or a poor score alone is not a cap decision (already in the forecast).
    quiet = cur.market_row(CFG, market(), stock(0.02, state="frozen", grade="poor"), LLTVS)
    assert quiet["recommendation"] == "survives"
    assert quiet["oracle"]["state"] == "frozen"
    assert quiet["oracle"]["quality_grade"] == "poor"


def test_survives_is_worded_as_the_modelled_bad_case() -> None:
    r = cur.market_row(CFG, market(), stock(0.024, segment="overnight"), LLTVS)
    assert r["recommendation"] == "survives"
    assert r["label"] == "Survives the modelled bad case"
    assert "safe" not in r["reason"].lower()
    assert r["tonight"]["held_out_miss_rate"] == pytest.approx(0.017257)
    # 96.5% LLTV leaves a 2.5% cushion, just beyond a 2.4% bad case.
    assert r["highest_surviving_lltv"] == 0.965
    assert cur.cushion(0.965) > 0.024 > cur.cushion(0.98)
    assert r["highest_lltv_with_margin"] == max(
        lv for lv in LLTVS if lv and cur.cushion(lv) * (1 - CFG.policy.pullback_fraction) > 0.024
    )
    assert r["headroom"] == pytest.approx(cur.cushion(0.625) - 0.024)


def test_no_forecast_makes_no_call() -> None:
    r = cur.market_row(CFG, market(), stock(None), LLTVS)
    assert r["recommendation"] == "no_forecast"
    assert r["breach"] is None


def test_summary_counts_money_by_recommendation() -> None:
    rows = [
        cur.market_row(CFG, market(lltv=0.915), stock(0.071), LLTVS),
        cur.market_row(CFG, market(), stock(0.02), LLTVS),
    ]
    s = cur.summarize(rows)
    assert s["reduce_cap"]["markets"] == 1
    assert s["survives"]["borrowed_usdg"] == 500.0


class FakeMarket:
    def __init__(self, mid: str, lltv: float, loan: str) -> None:
        self.id, self.symbol, self.lltv, self.loan_token = mid, "NVDA", lltv, loan


def test_mainnet_curator_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    from afterhours.live import mainnet as mn

    live = Mainnet(CFG)
    live.borrowers_by_market = tmp_path / "scan.json"
    board = {"network": "Robinhood Chain", "block": 100, "as_of": "t", "stocks": [stock(0.071)]}
    monkeypatch.setattr(live, "board", lambda *a, **k: board)
    m1, m2 = "0x" + "11" * 32, "0x" + "22" * 32
    monkeypatch.setattr(
        live,
        "markets",
        lambda: [FakeMarket(m1, 0.915, live.usdg), FakeMarket(m2, 0.625, live.usdg)],
    )
    monkeypatch.setattr(live, "decimals", lambda tokens, *a, **k: dict.fromkeys(tokens, 6))
    monkeypatch.setattr(
        live,
        "_scan_borrowers",
        lambda doc: {"last_block": 90, "scanned_at": 1e18, "by_market": {m2: ["0xA", "0xB"]}},
    )

    def fake_call_many(w3: Any, calls: list[Any], **k: Any) -> list[Any]:
        if calls and calls[0].signature == mn.MARKET:  # totalSupply, shares, totalBorrow, shares
            return [
                (1_000_000_000, 0, 900_000_000, 0, 0, 0),
                (2_000_000_000, 0, 1_980_000_000, 1000, 0, 0),
            ]
        return [(0, 900, 0), (0, 100, 0)]  # positions: borrow shares 900 and 100 of 1000

    monkeypatch.setattr(mn, "call_many", fake_call_many)
    doc = live.curator(wait=True)
    rows = {r["market_id"]: r for r in doc["markets"]}
    assert rows[m1]["recommendation"] == "reduce_cap"  # 7.1% beyond the 91.5% cushion
    assert rows[m2]["recommendation"] == "watch"  # fits, but 99% lent and one borrower 90%
    assert rows[m2]["borrowers"] == {"count": 2, "top_share": pytest.approx(0.9)}
    assert doc["markets"][0]["market_id"] == m1  # strongest recommendation first
    assert doc["totals"]["utilization"] == pytest.approx(2880 / 3000)
    assert doc["borrowers_scanned_to_block"] == 90
