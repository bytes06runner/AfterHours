"""Fetch and parse the primary sources named in `discovery.sources`.

Parsers are pure functions so they can be tested against saved fixtures.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import httpx
from eth_utils import is_address, to_checksum_address

from afterhours.config import AfterhoursConfig

ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")


def http_client(cfg: AfterhoursConfig) -> httpx.Client:
    """HTTP client with the configured timeout and user agent."""
    return httpx.Client(
        timeout=cfg.discovery.http_timeout_seconds,
        headers={"user-agent": cfg.discovery.user_agent},
        follow_redirects=True,
    )


# ------------------------------------------------------------------ Robinhood


def parse_robinhood_token_page(page: str) -> dict[str, str]:
    """Symbol -> address pairs from the static table on Robinhood's Token Contracts page."""
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: dict[str, str] = {}
    for prev, line in pairwise(lines):
        if ADDRESS_RE.fullmatch(line) and re.fullmatch(r"[A-Z][A-Za-z0-9.]{1,11}", prev):
            out[prev] = to_checksum_address(line)
    return out


@dataclass(frozen=True)
class StockAsset:
    """One Stock Token from Robinhood's `/rhj/assets` API."""

    symbol: str
    name: str
    address: str
    uid: str
    status: str
    multiplier: str
    all_day_tradability: str | None


def parse_assets_api(doc: dict[str, Any], chain_id: int) -> list[StockAsset]:
    """Stock Tokens deployed on `chain_id`, from the `/rhj/assets` response."""
    out: list[StockAsset] = []
    for asset in doc.get("assets", []):
        for dep in asset.get("deployments", []):
            if int(dep.get("chainId", -1)) != chain_id or not is_address(
                dep.get("contractAddress")
            ):
                continue
            caps = asset.get("tradingCapabilities") or {}
            out.append(
                StockAsset(
                    symbol=str(asset["tokenSymbol"]),
                    name=str(asset.get("tokenName", "")),
                    address=to_checksum_address(dep["contractAddress"]),
                    uid=str(asset.get("id", "")),
                    status=str(asset.get("status", "")),
                    multiplier=str(asset.get("currentMultiplier", "")),
                    all_day_tradability=caps.get("allDayTradability"),
                )
            )
    return out


# ------------------------------------------------------------------ Chainlink

_RH_FEED_NAME = re.compile(r"^Robinhood\s+([A-Z][A-Z0-9.]*)\s*[-/]\s*USD$")


@dataclass(frozen=True)
class Feed:
    """One Chainlink feed from the reference data directory."""

    name: str
    proxy: str
    decimals: int
    heartbeat_s: int
    deviation_pct: float
    market_hours: str
    symbol: str | None  # Stock Token symbol for "Robinhood XYZ / USD" feeds


def parse_chainlink_directory(doc: list[dict[str, Any]]) -> list[Feed]:
    """All feeds in Chainlink's directory JSON for one network."""
    out: list[Feed] = []
    for row in doc:
        proxy = row.get("proxyAddress")
        if not is_address(proxy):
            continue
        name = str(row.get("name", "")).strip()
        match = _RH_FEED_NAME.match(name)
        out.append(
            Feed(
                name=name,
                proxy=to_checksum_address(proxy),
                decimals=int(row.get("decimals", 0)),
                heartbeat_s=int(row.get("heartbeat", 0)),
                deviation_pct=float(row.get("threshold", 0)),
                market_hours=str((row.get("docs") or {}).get("marketHours", "")),
                symbol=match.group(1) if match else None,
            )
        )
    return out


# ------------------------------------------------------------------ Morpho


def parse_morpho_address_book(source: str, chain_key: str) -> dict[str, str]:
    """Flattened {dotted name: address} for one chain from the Morpho SDK `addresses.ts`.

    Only the first `[ChainId.<key>]: {` block is read: that is the address registry;
    later blocks with the same key hold deployment blocks.
    """
    marker = f"[ChainId.{chain_key}]: {{"
    start = source.find(marker)
    if start < 0:
        raise KeyError(f"{chain_key} not found in the Morpho address book")
    i = start + len(marker)
    depth = 1
    while depth:
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        i += 1
    block = source[start + len(marker) : i - 1]
    out: dict[str, str] = {}
    stack: list[str] = []
    for token in re.finditer(r"(\w+)\s*:\s*(\{|\"(0x[0-9a-fA-F]{40})\")|(\})", block):
        name, opener, address, closer = (
            token.group(1),
            token.group(2),
            token.group(3),
            token.group(4),
        )
        if closer:
            if stack:
                stack.pop()
        elif opener == "{":
            stack.append(name)
        elif address:
            out[".".join([*stack, name])] = to_checksum_address(address)
    return out


MARKETS_QUERY = """
query Markets($chainId: Int!, $first: Int!, $skip: Int!) {
  markets(first: $first, skip: $skip, where: { chainId_in: [$chainId] }) {
    items {
      marketId lltv irmAddress listed
      oracle { address }
      loanAsset { symbol address decimals }
      collateralAsset { symbol address decimals }
      state { supplyAssets borrowAssets supplyAssetsUsd borrowAssetsUsd utilization }
    }
    pageInfo { countTotal }
  }
}
"""

VAULTS_V2_QUERY = """
query Vaults($chainId: Int!) {
  vaultV2s(first: 100, where: { chainId_in: [$chainId] }) {
    items { address name symbol asset { symbol address } totalAssetsUsd }
  }
}
"""


def morpho_graphql(
    client: httpx.Client, url: str, query: str, variables: dict[str, Any]
) -> dict[str, Any]:
    """POST a GraphQL query to the Morpho API and return `data`."""
    response = client.post(url, json={"query": query, "variables": variables})
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"Morpho API error: {body['errors']}")
    data: dict[str, Any] = body["data"]
    return data


def fetch_morpho_markets(client: httpx.Client, url: str, chain_id: int) -> list[dict[str, Any]]:
    """Every Morpho Blue market the API knows on a chain."""
    items: list[dict[str, Any]] = []
    skip = 0
    while True:
        data = morpho_graphql(
            client, url, MARKETS_QUERY, {"chainId": chain_id, "first": 100, "skip": skip}
        )
        page = data["markets"]["items"]
        items.extend(page)
        skip += len(page)
        if not page or skip >= int(data["markets"]["pageInfo"]["countTotal"]):
            return items


# ------------------------------------------------------------------ Uniswap


def parse_uniswap_deployments(doc: dict[str, Any], chain_id: int) -> dict[str, str]:
    """{"v3.UniswapV3Factory": address, ...} for active deployments on a chain."""
    out: dict[str, str] = {}
    for rec in doc.get("records", []):
        if int(rec.get("chainId", -1)) != chain_id or rec.get("status", "active") != "active":
            continue
        if is_address(rec.get("address")):
            out[f"{rec['protocol']}.{rec['contract']}"] = to_checksum_address(rec["address"])
    return out
