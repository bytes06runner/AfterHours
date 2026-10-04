"""Find Uniswap v3 and v4 pools for Stock Tokens and measure sell-side depth.

Depth is what the policy caps exposure with: the USD value of a Stock Token that can be sold
into a pool before execution slippage (against the Chainlink price, fees included) passes
`vault.max_slippage`. We measure it with the official quoters at the probe sizes in
`discovery.pool_scan.depth_probe_usd` and interpolate linearly between probes. Selling is the
direction that matters, because liquidators sell collateral.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from eth_utils import to_checksum_address
from web3 import Web3
from web3.types import BlockIdentifier

from afterhours.chain.abi import address_topic, get_logs
from afterhours.chain.rpc import Call, call_many

ZERO = "0x" + "0" * 40

V3_QUOTE_SIG = (
    "quoteExactInputSingle((address,address,uint256,uint24,uint160))"
    "(uint256,uint160,uint32,uint256)"
)
V4_QUOTE_SIG = (
    "quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))"
    "(uint256,uint256)"
)
V4_INITIALIZE = (
    "Initialize(bytes32 indexed id,address indexed currency0,address indexed currency1,"
    "uint24 fee,int24 tickSpacing,address hooks,uint160 sqrtPriceX96,int24 tick)"
)


@dataclass
class Pool:
    """A pool between a Stock Token and a quote token, with its measured depth."""

    version: str  # "v3" | "v4"
    address_or_id: str
    token: str
    quote: str
    quote_symbol: str
    fee: int
    tick_spacing: int | None = None
    hooks: str | None = None
    liquidity: int = 0
    probes: list[dict[str, float]] = field(default_factory=list)
    depth_usd: float = 0.0

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly dict."""
        return asdict(self)


def find_v3_pools(
    w3: Web3,
    factory: str,
    tokens: Sequence[str],
    quotes: dict[str, str],
    fee_tiers: Sequence[int],
    *,
    block: int,
) -> list[Pool]:
    """Every v3 pool (token, quote, fee) that exists and has in-range liquidity."""
    keys = [(t, qs, q, f) for t in tokens for qs, q in quotes.items() for f in fee_tiers]
    addrs = call_many(
        w3,
        [
            Call(factory, "getPool(address,address,uint24)(address)", (t, q, f))
            for t, _, q, f in keys
        ],
        block=block,
    )
    found = [(k, str(a)) for k, a in zip(keys, addrs, strict=True) if a and str(a).lower() != ZERO]
    liqs = call_many(w3, [Call(a, "liquidity()(uint128)") for _, a in found], block=block)
    pools: list[Pool] = []
    for ((token, qsym, quote, fee), addr), liq in zip(found, liqs, strict=True):
        if liq:
            pools.append(
                Pool("v3", to_checksum_address(addr), token, quote, qsym, fee, liquidity=int(liq))
            )
    return pools


def find_v4_pools(
    w3: Web3,
    pool_manager: str,
    state_view: str,
    tokens: Sequence[str],
    quotes: dict[str, str],
    *,
    from_block: int,
    to_block: int,
    max_range: int,
) -> list[Pool]:
    """Hookless v4 pools pairing a token with a quote token, from `Initialize` events."""
    token_topics = [address_topic(t) for t in tokens]
    logs = get_logs(
        w3,
        V4_INITIALIZE,
        [pool_manager],
        from_block,
        to_block,
        topics=[None, token_topics],
        max_range=max_range,
    ) + get_logs(
        w3,
        V4_INITIALIZE,
        [pool_manager],
        from_block,
        to_block,
        topics=[None, None, token_topics],
        max_range=max_range,
    )
    by_quote = {q.lower(): s for s, q in quotes.items()}
    token_set = {t.lower() for t in tokens}
    candidates: list[Pool] = []
    for log in logs:
        c0, c1 = str(log["currency0"]).lower(), str(log["currency1"]).lower()
        hooks = to_checksum_address(log["hooks"])
        if hooks.lower() != ZERO:
            continue
        token, quote = (c0, c1) if c0 in token_set else (c1, c0)
        if token not in token_set or quote not in by_quote:
            continue
        candidates.append(
            Pool(
                "v4",
                "0x" + bytes(log["id"]).hex(),
                to_checksum_address(token),
                to_checksum_address(quote),
                by_quote[quote],
                int(log["fee"]),
                tick_spacing=int(log["tickSpacing"]),
                hooks=hooks,
            )
        )
    liqs = call_many(
        w3,
        [
            Call(
                state_view, "getLiquidity(bytes32)(uint128)", (bytes.fromhex(p.address_or_id[2:]),)
            )
            for p in candidates
        ],
        block=int(w3.eth.block_number),  # the log scan can outlast a non-archive RPC's state
    )
    out = []
    for p, liq in zip(candidates, liqs, strict=True):
        if liq:
            p.liquidity = int(liq)
            out.append(p)
    return out


def measure_depth(
    w3: Web3,
    pools: Sequence[Pool],
    *,
    v3_quoter: str,
    v4_quoter: str,
    token_price_usd: dict[str, float],
    quote_price_usd: dict[str, float],
    token_decimals: dict[str, int],
    quote_decimals: dict[str, int],
    probes_usd: Sequence[float],
    max_slippage: float,
    block: BlockIdentifier,
    deadline: float | None = None,
) -> None:
    """Fill `probes` and `depth_usd` on each pool by quoting sells of token for quote."""
    calls: list[Call] = []
    index: list[tuple[Pool, float, int]] = []
    for p in pools:
        price = token_price_usd[p.token]
        for usd in probes_usd:
            amount_in = int(usd / price * 10 ** token_decimals[p.token])
            if p.version == "v3":
                calls.append(
                    Call(v3_quoter, V3_QUOTE_SIG, ((p.token, p.quote, amount_in, p.fee, 0),))
                )
            else:
                zero_for_one = p.token.lower() < p.quote.lower()
                c0, c1 = sorted([p.token, p.quote], key=str.lower)
                key = (c0, c1, p.fee, p.tick_spacing, p.hooks)
                calls.append(Call(v4_quoter, V4_QUOTE_SIG, ((key, zero_for_one, amount_in, b""),)))
            index.append((p, usd, amount_in))
    results = call_many(w3, calls, block=block, chunk=20, deadline=deadline)
    for (p, usd, _), res in zip(index, results, strict=True):
        if res is None:
            p.probes.append({"usd_in": usd, "usd_out": 0.0, "slippage": 1.0})
            continue
        amount_out = int(res[0])
        usd_out = amount_out / 10 ** quote_decimals[p.quote] * quote_price_usd[p.quote]
        p.probes.append({"usd_in": usd, "usd_out": usd_out, "slippage": 1 - usd_out / usd})
    for p in pools:
        p.depth_usd = depth_at_slippage(p.probes, max_slippage)


def depth_at_slippage(probes: Sequence[dict[str, float]], max_slippage: float) -> float:
    """Largest trade size (USD) whose slippage stays within `max_slippage`.

    Interpolates linearly in slippage between the last probe inside the limit and the first
    probe outside it, starting from (0 USD, 0 slippage). Returns the largest probe size if
    every probe is inside the limit; that is a lower bound, flagged by the caller.
    """
    pts = sorted(probes, key=lambda p: p["usd_in"])
    prev_usd, prev_slip = 0.0, 0.0
    for pt in pts:
        slip = max(pt["slippage"], 0.0)
        if slip > max_slippage:
            frac = (max_slippage - prev_slip) / (slip - prev_slip) if slip > prev_slip else 0.0
            return prev_usd + frac * (pt["usd_in"] - prev_usd)
        prev_usd, prev_slip = pt["usd_in"], slip
    return prev_usd
