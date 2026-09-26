"""Size of the Stock Token lending market on Morpho Blue, read onchain at one recent block.

Every market ever created is found from `CreateMarket` events (block 0 to the pinned block);
a market counts as a Stock Token market when its collateral is one of the Stock Tokens found in
M1 discovery. Totals are Morpho's stored `market(id)` values at the pinned block: supplied and
borrowed assets as of each market's last update (interest accrued since then is not included).

Sources (read 2026-09-27):
- Event and struct layout: morpho-blue `src/interfaces/IMorpho.sol` and
  `src/libraries/EventsLib.sol` on GitHub (`CreateMarket(Id indexed id, MarketParams
  marketParams)`; `Market` is six uint128 fields, supply assets first, borrow assets third).
- Morpho Blue and USDG addresses and the Stock Token list: `deployments/fork.discovered.json`
  (M1, each verified onchain; sources recorded there).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from eth_utils import to_checksum_address

from afterhours.chain.abi import get_logs
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import AfterhoursConfig
from afterhours.deployments import load_discovered

CREATE_MARKET = (
    "CreateMarket(bytes32 indexed id,(address,address,address,address,uint256) marketParams)"
)
MARKET = "market(bytes32)(uint128,uint128,uint128,uint128,uint128,uint128)"


def read(cfg: AfterhoursConfig, lag_blocks: int = 30) -> dict[str, Any]:
    disc = load_discovered(cfg, "fork")
    blue = disc["core"]["morpho_blue"]["address"]
    usdg = to_checksum_address(disc["core"]["usdg"]["address"])
    tokens = {to_checksum_address(v["address"]): sym for sym, v in disc["stock_tokens"].items()}
    w3 = connect(cfg.rpc_url("rh-mainnet"))
    # A block a little behind the head: public nodes keep state for recent blocks only.
    block = int(w3.eth.block_number) - lag_blocks
    ts = int(w3.eth.get_block(block)["timestamp"])
    created = get_logs(
        w3,
        CREATE_MARKET,
        [blue],
        0,
        block,
        max_range=cfg.discovery.oracle_study.max_log_block_range * 20,
    )
    markets = []
    for ev in created:
        loan, collateral, _oracle, _irm, lltv = ev["marketParams"]
        collateral = to_checksum_address(collateral)
        if collateral in tokens:
            markets.append(
                {
                    "id": "0x" + bytes(ev["id"]).hex(),
                    "symbol": tokens[collateral],
                    "loan_token": to_checksum_address(loan),
                    "lltv": lltv / 1e18,
                    "created_block": ev["_block"],
                }
            )
    states = call_many(
        w3, [Call(blue, MARKET, (bytes.fromhex(m["id"][2:]),)) for m in markets], block=block
    )
    decimals = {
        a: int(d)
        for a, d in zip(
            sorted({m["loan_token"] for m in markets}),
            call_many(
                w3,
                [Call(a, "decimals()(uint8)") for a in sorted({m["loan_token"] for m in markets})],
                block=block,
            ),
            strict=True,
        )
    }
    by_loan: dict[str, dict[str, float]] = defaultdict(
        lambda: {"supplied": 0.0, "borrowed": 0.0, "markets": 0}
    )
    by_symbol: dict[str, dict[str, float]] = defaultdict(lambda: {"supplied": 0.0, "borrowed": 0.0})
    last_updates = []
    for m, st in zip(markets, states, strict=True):
        unit = 10 ** decimals[m["loan_token"]]
        m["supplied"] = int(st[0]) / unit
        m["borrowed"] = int(st[2]) / unit
        m["last_update"] = int(st[4])
        last_updates.append(int(st[4]))
        b = by_loan[m["loan_token"]]
        b["supplied"] += m["supplied"]
        b["borrowed"] += m["borrowed"]
        b["markets"] += 1
        if m["loan_token"] == usdg:
            by_symbol[m["symbol"]]["supplied"] += m["supplied"]
            by_symbol[m["symbol"]]["borrowed"] += m["borrowed"]
    api_count = sum(len(v["morpho_markets"]) for v in disc["stock_tokens"].values())
    u = by_loan.get(usdg, {"supplied": 0.0, "borrowed": 0.0, "markets": 0})
    return {
        "chain_id": int(w3.eth.chain_id),
        "block": block,
        "block_time": datetime.fromtimestamp(ts, UTC).isoformat(),
        "morpho_blue": blue,
        "usdg": usdg,
        "stock_tokens": len(tokens),
        "markets_created_total": len(created),
        "stock_token_markets": len(markets),
        "stock_token_markets_in_morpho_api_at_discovery": api_count,
        "usdg_loan": {
            "markets": u["markets"],
            "supplied": u["supplied"],
            "borrowed": u["borrowed"],
        },
        "by_loan_token": {k: dict(v) for k, v in by_loan.items()},
        "by_symbol_usdg": {
            k: dict(v) for k, v in sorted(by_symbol.items(), key=lambda x: -x[1]["supplied"])
        },
        "oldest_last_update": datetime.fromtimestamp(min(last_updates), UTC).isoformat()
        if last_updates
        else None,
        "note": (
            "stored totals at the block; interest accrued since each market's last update "
            "is not included"
        ),
        "sources": {
            "interface": cfg.discovery.sources.morpho_blue_interface,
            "events": cfg.discovery.sources.morpho_blue_events,
            "addresses": "deployments/fork.discovered.json",
        },
        "markets": markets,
    }
