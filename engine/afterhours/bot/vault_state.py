"""Read the vault's state onchain: per-market allocation, lent-out amount, rates and idle cash."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from eth_abi import encode
from eth_utils import keccak
from web3 import Web3

from afterhours.chain.rpc import Call, call_many

SECONDS_PER_YEAR = 365 * 24 * 3600
MARKET_SIG = "market(bytes32)(uint128,uint128,uint128,uint128,uint128,uint128)"
PARAMS_TYPE = "(address,address,address,address,uint256)"


@dataclass
class MarketState:
    """The vault's position in one Morpho market."""

    symbol: str
    tier: str
    market_id: str
    params: tuple[str, str, str, str, int]
    vault_supply: float  # USDG supplied by the vault
    lent_out: float  # the part of vault_supply the vault cannot withdraw now
    market_supply: float
    market_borrow: float
    supply_apy: float
    absolute_cap: float
    allocation_id: str

    def to_json(self) -> dict[str, Any]:
        out = asdict(self)
        out["params"] = list(self.params)
        return out


@dataclass
class VaultState:
    """Everything the planner needs."""

    block: int
    timestamp: int
    total_assets: float
    idle: float
    markets: list[MarketState]
    decimals: int

    def to_json(self) -> dict[str, Any]:
        return {
            "block": self.block,
            "timestamp": self.timestamp,
            "total_assets": self.total_assets,
            "idle": self.idle,
            "decimals": self.decimals,
            "markets": [m.to_json() for m in self.markets],
        }


def allocation_id(adapter: str, params: tuple[str, str, str, str, int]) -> bytes:
    """Vault V2 id for a market: keccak256(abi.encode("this/marketParams", adapter, params))."""
    return keccak(
        encode(["string", "address", PARAMS_TYPE], ["this/marketParams", adapter, params])
    )


def read_state(w3: Web3, deployment: dict[str, Any]) -> VaultState:
    """Snapshot of the vault from chain."""
    vault = deployment["vault"]["address"]
    adapter = deployment["adapter"]["address"]
    morpho = deployment["morpho"]["address"]
    loan = deployment["loan_token"]["address"]
    block = w3.eth.get_block("latest")
    number, ts = int(block["number"]), int(block["timestamp"])
    head = call_many(
        w3,
        [
            Call(loan, "decimals()(uint8)"),
            Call(vault, "totalAssets()(uint256)"),
            Call(loan, "balanceOf(address)(uint256)", (vault,)),
        ],
        block=number,
    )
    dec = int(head[0])
    unit = 10**dec
    markets = deployment["markets"]
    calls: list[Call] = []
    ids = []
    for m in markets:
        params = (m["loan_token"], m["collateral"], m["oracle"], m["irm"], int(m["lltv_wad"]))
        mid = bytes.fromhex(m["market_id"][2:])
        aid = allocation_id(adapter, params)
        ids.append((params, aid))
        calls += [
            Call(morpho, MARKET_SIG, (mid,)),
            Call(adapter, "expectedSupplyAssets(bytes32)(uint256)", (mid,)),
            Call(vault, "absoluteCap(bytes32)(uint256)", (aid,)),
        ]
    res = call_many(w3, calls, block=number)
    irm_calls = []
    for i, m in enumerate(markets):
        mk = res[3 * i]
        irm_calls.append(
            Call(
                m["irm"],
                f"borrowRateView({PARAMS_TYPE},(uint128,uint128,uint128,uint128,uint128,uint128))(uint256)",
                (ids[i][0], tuple(int(x) for x in mk)),
            )
        )
    rates = call_many(w3, irm_calls, block=number)
    out = []
    for i, m in enumerate(markets):
        mk, supplied, cap = res[3 * i], res[3 * i + 1], res[3 * i + 2]
        total_supply, total_borrow, fee = int(mk[0]), int(mk[2]), int(mk[5])
        liquidity = max(total_supply - total_borrow, 0)
        withdrawable = min(int(supplied), liquidity)
        util = total_borrow / total_supply if total_supply else 0.0
        borrow_rate = (int(rates[i]) / 1e18) if rates[i] is not None else 0.0
        apy = (1 + borrow_rate) ** SECONDS_PER_YEAR - 1 if borrow_rate else 0.0
        supply_apy = apy * util * (1 - fee / 1e18)
        out.append(
            MarketState(
                symbol=m["symbol"],
                tier=m["tier"],
                market_id=m["market_id"],
                params=ids[i][0],
                vault_supply=int(supplied) / unit,
                lent_out=(int(supplied) - withdrawable) / unit,
                market_supply=total_supply / unit,
                market_borrow=total_borrow / unit,
                supply_apy=supply_apy,
                absolute_cap=int(cap) / unit,
                allocation_id="0x" + ids[i][1].hex(),
            )
        )
    return VaultState(number, ts, int(head[1]) / unit, int(head[2]) / unit, out, dec)
