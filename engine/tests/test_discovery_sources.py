"""Parser tests against saved excerpts of the real source documents (fetched 2026-09-26)."""

from __future__ import annotations

import json
from pathlib import Path

from afterhours.discovery import sources
from afterhours.discovery.pools import depth_at_slippage
from afterhours.discovery.run import liquidation_incentive_factor

FIX = Path(__file__).parent / "fixtures" / "discovery"


def test_robinhood_token_page() -> None:
    tokens = sources.parse_robinhood_token_page((FIX / "rh_token_page.html").read_text())
    assert tokens["USDG"] == "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
    assert tokens["WETH"] == "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73"


def test_assets_api() -> None:
    doc = json.loads((FIX / "rh_assets.json").read_text())
    assets = {a.symbol: a for a in sources.parse_assets_api(doc, 4663)}
    assert assets["NVDA"].address == "0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC"
    assert assets["NVDA"].status == "ASSET_STATUS_ACTIVE"
    assert sources.parse_assets_api(doc, 1) == []


def test_chainlink_directory() -> None:
    feeds = {
        f.name: f
        for f in sources.parse_chainlink_directory(
            json.loads((FIX / "chainlink_feeds.json").read_text())
        )
    }
    nvda = feeds["Robinhood NVDA / USD"]
    assert nvda.symbol == "NVDA"
    assert nvda.proxy == "0x379EC4f7C378F34a1B47E4F3cbeBCbAC3E8E9F15"
    assert nvda.decimals == 8
    assert nvda.market_hours == "us_equities_24/5"
    assert feeds["Robinhood DELL-USD"].symbol == "DELL"
    assert feeds["ETH / USD"].symbol is None


def test_morpho_address_book_flattens_nested_and_wrapped_lines() -> None:
    book = sources.parse_morpho_address_book(
        (FIX / "morpho_addresses_excerpt.ts").read_text(), "RobinhoodMainnet"
    )
    assert book["blue"] == "0x9D53d5E3bd5E8d4Cbfa6DB1ca238AEA02E651010"
    assert book["vaultV2Factory"] == "0x0FBad98595b0186dA120E41f77C102beb49f803c"
    assert book["morphoMarketV1AdapterV2Factory"] == "0x79370Ed003CE325C088E530d5e8655c99c2993e1"
    assert book["bundles.blueBundlesV1"] == "0x53A1eB6589861F686af7c531211E35Aefe30210f"
    assert "metaMorphoFactory" not in book


def test_uniswap_deployments_filters_chain() -> None:
    doc = json.loads((FIX / "uniswap_deployments.json").read_text())
    rh = sources.parse_uniswap_deployments(doc, 4663)
    assert rh["v3.UniswapV3Factory"] == "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA"
    assert rh["v4.PoolManager"] == "0x8366a39CC670B4001A1121B8F6A443A643e40951"
    assert len(rh) == 2


def test_liquidation_incentive_matches_morpho_formula() -> None:
    # min(1.15, 1 / (1 - 0.3 * (1 - lltv)))
    assert abs(liquidation_incentive_factor(0.625) - 1 / 0.8875) < 1e-12
    assert liquidation_incentive_factor(0.385) == 1.15
    assert abs(liquidation_incentive_factor(0.915) - 1 / (1 - 0.3 * 0.085)) < 1e-12


def test_depth_interpolates_between_probes() -> None:
    probes = [
        {"usd_in": 1000, "slippage": 0.005},
        {"usd_in": 10000, "slippage": 0.01},
        {"usd_in": 100000, "slippage": 0.03},
    ]
    assert abs(depth_at_slippage(probes, 0.02) - 55000) < 1e-6
    assert depth_at_slippage(probes, 0.5) == 100000
    assert depth_at_slippage([{"usd_in": 1000, "slippage": 0.04}], 0.02) == 500
