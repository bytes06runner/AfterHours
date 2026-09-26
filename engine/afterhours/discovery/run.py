"""`afterhours discover`: fetch primary sources, verify every address onchain, write evidence.

Output: `deployments/<profile>.discovered.json` plus `artifacts/discovery/*.json`.
Every address carries the source URL it came from and the onchain checks it passed.
Nothing is written into the discovered file unless its checks pass; failures are listed
under `_failures` so they cannot be used by accident.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from web3 import Web3

from afterhours.chain.abi import get_logs
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import AfterhoursConfig
from afterhours.deployments import discovered_path
from afterhours.discovery import oracle_study, pools, sources

log = logging.getLogger(__name__)
WAD = 10**18
HEAD_LAG_BLOCKS = 30
# Morpho Blue v1.0.0 ConstantsLib.sol; also found in the deployed bytecode (see findings).
MORPHO_CONSTANTS_HEX = {
    "LIQUIDATION_CURSOR=0.3e18": "0429d069189e0000",
    "MAX_LIQUIDATION_INCENTIVE_FACTOR=1.15e18": "0ff59ee833b30000",
    "MAX_FEE=0.25e18": "03782dace9d90000",
}


@dataclass
class Item:
    """A discovered address with its source and evidence."""

    address: str
    source: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def check(self, name: str, actual: Any, expected: Any = None, ok: bool | None = None) -> bool:
        """Record one check; `ok` defaults to actual == expected (or truthy if no expectation)."""
        passed = (
            ok if ok is not None else (actual == expected if expected is not None else bool(actual))
        )
        self.evidence.append(
            {
                "check": name,
                "actual": _jsonable(actual),
                "expected": _jsonable(expected),
                "ok": passed,
            }
        )
        return passed

    def skip(self, name: str, reason: str) -> None:
        """Record a check that could not run; it neither passes nor fails the item."""
        self.evidence.append({"check": name, "skipped": reason, "ok": None})

    @property
    def ok(self) -> bool:
        ran = [e for e in self.evidence if e["ok"] is not None]
        return bool(ran) and all(e["ok"] for e in ran)

    def to_json(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "source": self.source,
            **self.extra,
            "evidence": self.evidence,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, tuple | list):
        return [_jsonable(v) for v in value]
    if isinstance(value, int) and abs(value) > 2**53:
        return str(value)
    return value


def liquidation_incentive_factor(lltv: float) -> float:
    """min(1.15, 1 / (1 - 0.3 * (1 - lltv))), from Morpho.sol `liquidate` (v1.0.0, line 365)."""
    return min(1.15, 1 / (1 - 0.3 * (1 - lltv)))


def discover(cfg: AfterhoursConfig, *, run_oracle_study: bool = True) -> dict[str, Any]:
    """Run discovery for `cfg.discovery.chain` and return the discovered document."""
    d = cfg.discovery
    chain = cfg.chains[d.chain]
    profile = cfg.active_profile
    w3 = connect(cfg.rpc_url(profile), timeout=d.http_timeout_seconds)
    chain_id = int(w3.eth.chain_id)
    if chain.chain_id != chain_id:
        raise RuntimeError(f"RPC chain id {chain_id} != config {chain.chain_id}")
    head = int(w3.eth.block_number)
    head_ts = int(w3.eth.get_block(head)["timestamp"])
    state_blocks: dict[str, int] = {}

    def fresh(step: str) -> int:
        """Latest block, recorded per step: RPCs without archive state keep only minutes."""
        # A few seconds behind the head: load-balanced RPC nodes lag each other slightly.
        state_blocks[step] = int(w3.eth.block_number) - HEAD_LAG_BLOCKS
        return state_blocks[step]

    fork_block = cfg.profile.fork_block
    src = d.sources
    failures: list[dict[str, Any]] = []

    log.info("fetching sources")
    with sources.http_client(cfg) as http:
        token_page = sources.parse_robinhood_token_page(
            http.get(src.robinhood_token_contracts_page).text
        )
        assets = sources.parse_assets_api(http.get(src.robinhood_assets_api).json(), chain_id)
        feeds = sources.parse_chainlink_directory(http.get(src.chainlink_feed_directory).json())
        morpho_book = sources.parse_morpho_address_book(
            http.get(src.morpho_address_book).text, d.morpho_chain_key
        )
        uni = sources.parse_uniswap_deployments(http.get(src.uniswap_deployments).json(), chain_id)
        markets_api = sources.fetch_morpho_markets(http, src.morpho_api, chain_id)
        vaults_api = sources.morpho_graphql(
            http, src.morpho_api, sources.VAULTS_V2_QUERY, {"chainId": chain_id}
        )["vaultV2s"]["items"]

    # ---------------------------------------------------------------- core contracts
    log.info("verifying core contracts")
    core: dict[str, Item] = {
        "morpho_blue": Item(morpho_book["blue"], src.morpho_address_book),
        "adaptive_curve_irm": Item(morpho_book["adaptiveCurveIrm"], src.morpho_address_book),
        "chainlink_oracle_v2_factory": Item(
            morpho_book["chainlinkOracleFactory"], src.morpho_address_book
        ),
        "vault_v2_factory": Item(morpho_book["vaultV2Factory"], src.morpho_address_book),
        "market_v1_adapter_v2_factory": Item(
            morpho_book["morphoMarketV1AdapterV2Factory"], src.morpho_address_book
        ),
        "usdg": Item(token_page[d.loan_token_symbol], src.robinhood_token_contracts_page),
        "weth": Item(token_page["WETH"], src.robinhood_token_contracts_page),
        "uniswap_v3_factory": Item(uni["v3.UniswapV3Factory"], src.uniswap_deployments),
        "uniswap_v3_quoter_v2": Item(uni["v3.QuoterV2"], src.uniswap_deployments),
        "uniswap_v4_pool_manager": Item(uni["v4.PoolManager"], src.uniswap_deployments),
        "uniswap_v4_state_view": Item(uni["v4.StateView"], src.uniswap_deployments),
        "uniswap_v4_quoter": Item(uni["v4.V4Quoter"], src.uniswap_deployments),
    }
    blue = core["morpho_blue"].address
    irm = core["adaptive_curve_irm"].address
    for item in core.values():
        code = w3.eth.get_code(Web3.to_checksum_address(item.address), block_identifier=head)
        item.check("code size at head (bytes)", len(code), ok=len(code) > 0)
        if fork_block:
            name = f"code size at fork_block {fork_block}"
            try:
                fcode = w3.eth.get_code(
                    Web3.to_checksum_address(item.address), block_identifier=fork_block
                )
                item.check(name, len(fcode), ok=len(fcode) > 0)
            except Exception as exc:  # public RPCs keep only recent state
                item.skip(
                    name,
                    f"RPC has no state at that block ({exc.__class__.__name__}); "
                    "needs an archive RPC",
                )
    blue_code = w3.eth.get_code(Web3.to_checksum_address(blue), block_identifier=head).hex()
    for name, hexval in MORPHO_CONSTANTS_HEX.items():
        core["morpho_blue"].check(f"bytecode contains {name}", hexval in blue_code)

    usdg = core["usdg"].address
    weth = core["weth"].address
    checks: list[tuple[str, Call, Any]] = [
        ("morpho_blue", Call(blue, "isIrmEnabled(address)(bool)", (irm,)), True),
        ("morpho_blue", Call(blue, "owner()(address)"), None),
        ("adaptive_curve_irm", Call(irm, "MORPHO()(address)"), blue),
        (
            "market_v1_adapter_v2_factory",
            Call(core["market_v1_adapter_v2_factory"].address, "morpho()(address)"),
            blue,
        ),
        (
            "market_v1_adapter_v2_factory",
            Call(core["market_v1_adapter_v2_factory"].address, "adaptiveCurveIrm()(address)"),
            irm,
        ),
        ("usdg", Call(usdg, "symbol()(string)"), d.loan_token_symbol),
        ("usdg", Call(usdg, "decimals()(uint8)"), None),
        ("usdg", Call(usdg, "name()(string)"), None),
        ("weth", Call(weth, "symbol()(string)"), "WETH"),
        ("weth", Call(weth, "decimals()(uint8)"), 18),
        (
            "uniswap_v3_factory",
            Call(core["uniswap_v3_factory"].address, "feeAmountTickSpacing(uint24)(int24)", (500,)),
            10,
        ),
        (
            "uniswap_v3_quoter_v2",
            Call(core["uniswap_v3_quoter_v2"].address, "factory()(address)"),
            core["uniswap_v3_factory"].address,
        ),
        (
            "uniswap_v4_state_view",
            Call(core["uniswap_v4_state_view"].address, "poolManager()(address)"),
            core["uniswap_v4_pool_manager"].address,
        ),
        (
            "uniswap_v4_quoter",
            Call(core["uniswap_v4_quoter"].address, "poolManager()(address)"),
            core["uniswap_v4_pool_manager"].address,
        ),
    ]
    for (key, c, expected), actual in zip(
        checks, call_many(w3, [c for _, c, _ in checks], block=fresh("core_checks")), strict=True
    ):
        exp = (
            expected.lower()
            if isinstance(expected, str) and expected.startswith("0x")
            else expected
        )
        act = actual.lower() if isinstance(actual, str) and actual.startswith("0x") else actual
        core[key].check(
            c.signature, act, exp, ok=(act == exp) if exp is not None else actual is not None
        )
    usdg_decimals = int(
        call_many(w3, [Call(usdg, "decimals()(uint8)")], block=fresh("usdg_decimals"))[0]
    )

    # ---------------------------------------------------------------- enabled LLTVs
    log.info("scanning EnableLltv events")
    lltv_logs = get_logs(
        w3,
        "EnableLltv(uint256 lltv)",
        [blue],
        0,
        head,
        max_range=d.oracle_study.max_log_block_range * 20,
    )
    lltvs = sorted({int(x["lltv"]) for x in lltv_logs})
    enabled = call_many(
        w3,
        [Call(blue, "isLltvEnabled(uint256)(bool)", (v,)) for v in lltvs],
        block=fresh("lltv_enabled"),
    )
    lltv_doc = {
        "source": (
            "EnableLltv events on Morpho Blue, block 0 to head, each rechecked with isLltvEnabled"
        ),
        "values_wad": [str(v) for v, ok in zip(lltvs, enabled, strict=True) if ok],
        "values": [v / WAD for v, ok in zip(lltvs, enabled, strict=True) if ok],
        "liquidation_incentive": {
            str(v / WAD): {
                "factor": round(liquidation_incentive_factor(v / WAD), 6),
                "allowance_b": round((v / WAD) * (liquidation_incentive_factor(v / WAD) - 1), 6),
                "cushion": round(1 - (v / WAD) * liquidation_incentive_factor(v / WAD), 6),
            }
            for v, ok in zip(lltvs, enabled, strict=True)
            if ok and v > 0
        },
    }

    # ---------------------------------------------------------------- stock tokens + feeds
    log.info("verifying stock tokens and feeds")
    feed_by_symbol = {f.symbol: f for f in feeds if f.symbol}
    candidates = [
        a for a in assets if a.symbol in feed_by_symbol and a.status == "ASSET_STATUS_ACTIVE"
    ]
    token_calls: list[Call] = []
    for a in candidates:
        f = feed_by_symbol[a.symbol]
        token_calls += [
            Call(a.address, "symbol()(string)"),
            Call(a.address, "decimals()(uint8)"),
            Call(a.address, "uiMultiplier()(uint256)"),
            Call(f.proxy, "description()(string)"),
            Call(f.proxy, "decimals()(uint8)"),
            Call(f.proxy, "latestRoundData()(uint80,int256,uint256,uint256,uint80)"),
        ]
    token_results = call_many(w3, token_calls, block=fresh("tokens_feeds"))
    stock: dict[str, Item] = {}
    prices: dict[str, float] = {}
    decimals: dict[str, int] = {}
    for i, a in enumerate(candidates):
        f = feed_by_symbol[a.symbol]
        sym, dec, mult, desc, fdec, rnd = token_results[6 * i : 6 * i + 6]
        item = Item(a.address, src.robinhood_assets_api, extra={"name": a.name, "uid": a.uid})
        item.check("symbol()", sym, a.symbol)
        item.check("decimals()", dec, 18)
        item.check("uiMultiplier() > 0", str(mult) if mult else None, ok=bool(mult))
        feed_item = Item(
            f.proxy,
            src.chainlink_feed_directory,
            extra={
                "name": f.name,
                "heartbeat_s": f.heartbeat_s,
                "deviation_pct": f.deviation_pct,
                "market_hours": f.market_hours,
            },
        )
        feed_item.check(
            "description() names the token", desc, ok=bool(desc) and a.symbol in str(desc)
        )
        feed_item.check("decimals()", fdec, f.decimals)
        feed_item.check(
            "latestRoundData answer > 0", str(rnd[1]) if rnd else None, ok=bool(rnd) and rnd[1] > 0
        )
        if rnd:
            feed_item.extra["latest_answer"] = rnd[1] / 10**f.decimals
            feed_item.extra["latest_updated_at"] = datetime.fromtimestamp(rnd[3], UTC).isoformat()
        item.extra["feed"] = feed_item.to_json()
        if item.ok and feed_item.ok:
            stock[a.symbol] = item
            prices[a.address] = rnd[1] / 10**f.decimals
            decimals[a.address] = int(dec)
        else:
            failures.append(
                {"symbol": a.symbol, "token": item.to_json(), "feed": feed_item.to_json()}
            )

    # ---------------------------------------------------------------- existing Morpho markets
    log.info("verifying existing Morpho markets")
    stock_by_addr = {it.address.lower(): s for s, it in stock.items()}
    rel_markets = [
        m
        for m in markets_api
        if (m.get("loanAsset") or {}).get("address", "").lower() == usdg.lower()
        and (m.get("collateralAsset") or {}).get("address", "").lower() in stock_by_addr
    ]
    mcalls: list[Call] = []
    for m in rel_markets:
        mid = bytes.fromhex(m["marketId"][2:])
        mcalls += [
            Call(
                blue, "idToMarketParams(bytes32)(address,address,address,address,uint256)", (mid,)
            ),
            Call(blue, "market(bytes32)(uint128,uint128,uint128,uint128,uint128,uint128)", (mid,)),
            Call(m["oracle"]["address"], "BASE_FEED_1()(address)"),
            Call(
                core["chainlink_oracle_v2_factory"].address,
                "isMorphoChainlinkOracleV2(address)(bool)",
                (m["oracle"]["address"],),
            ),
        ]
    mres = call_many(w3, mcalls, block=fresh("markets"))
    for i, m in enumerate(rel_markets):
        params, state, base_feed, from_factory = mres[4 * i : 4 * i + 4]
        sym = stock_by_addr[m["collateralAsset"]["address"].lower()]
        onchain_ok = (
            bool(params)
            and str(params[1]).lower() == m["collateralAsset"]["address"].lower()
            and str(params[0]).lower() == usdg.lower()
            and int(params[4]) == int(m["lltv"])
        )
        feed_proxy = stock[sym].extra["feed"]["address"].lower()
        entry = {
            "market_id": m["marketId"],
            "lltv": int(m["lltv"]) / WAD,
            "oracle": m["oracle"]["address"],
            "irm": str(params[3]) if params else None,
            "oracle_from_chainlink_v2_factory": bool(from_factory),
            "oracle_base_feed_is_token_feed": bool(base_feed)
            and str(base_feed).lower() == feed_proxy,
            "total_supply_assets": (int(state[0]) / 10**usdg_decimals) if state else None,
            "total_borrow_assets": (int(state[2]) / 10**usdg_decimals) if state else None,
            "params_match_api": onchain_ok,
            "source": src.morpho_api,
        }
        stock[sym].extra.setdefault("morpho_markets", []).append(entry)

    # ---------------------------------------------------------------- pools and depth
    log.info("finding pools and measuring depth")
    head_time = datetime.fromtimestamp(head_ts, UTC)
    quotes = {s: core[s.lower()].address for s in d.pool_scan.quote_symbols}
    eth_feed = next((f for f in feeds if f.name.replace(" ", "") == "ETH/USD"), None)
    eth_price = None
    if eth_feed:
        rnd = call_many(
            w3,
            [Call(eth_feed.proxy, "latestRoundData()(uint80,int256,uint256,uint256,uint80)")],
            block=fresh("eth_price"),
        )[0]
        eth_price = rnd[1] / 10**eth_feed.decimals if rnd else None
    quote_price = {usdg: 1.0, weth: eth_price or 0.0}
    quote_dec = {usdg: usdg_decimals, weth: 18}
    token_addrs = [it.address for it in stock.values()]
    v3 = pools.find_v3_pools(
        w3,
        core["uniswap_v3_factory"].address,
        token_addrs,
        quotes,
        d.pool_scan.v3_fee_tiers,
        block=fresh("v3_pools"),
    )
    v4 = pools.find_v4_pools(
        w3,
        core["uniswap_v4_pool_manager"].address,
        core["uniswap_v4_state_view"].address,
        token_addrs,
        quotes,
        from_block=0,
        to_block=fresh("v4_state"),
        max_range=d.oracle_study.max_log_block_range * 20,
    )
    all_pools = [p for p in v3 + v4 if quote_price.get(p.quote)]
    # Thousands of quotes outlast a non-archive node's state window, so quote at the head
    # and record the range of blocks the measurement spanned.
    fresh("depth_start")
    pools.measure_depth(
        w3,
        all_pools,
        v3_quoter=core["uniswap_v3_quoter_v2"].address,
        v4_quoter=core["uniswap_v4_quoter"].address,
        token_price_usd=prices,
        quote_price_usd=quote_price,
        token_decimals=decimals,
        quote_decimals=quote_dec,
        probes_usd=d.pool_scan.depth_probe_usd,
        max_slippage=cfg.vault.max_slippage,
        block="latest",
    )
    fresh("depth_end")
    for it in stock.values():
        mine = [p for p in all_pools if p.token.lower() == it.address.lower()]
        it.extra["pools"] = [p.to_json() for p in sorted(mine, key=lambda p: -p.depth_usd)]
        it.extra["depth_usd_at_max_slippage"] = round(sum(p.depth_usd for p in mine), 2)
        it.extra["depth_is_lower_bound"] = any(
            p.probes and all(x["slippage"] <= cfg.vault.max_slippage for x in p.probes)
            for p in mine
        )

    sel_cfg = cfg.universe.onchain_selection
    ranked = sorted(stock, key=lambda s: -stock[s].extra["depth_usd_at_max_slippage"])
    selected = [
        s
        for s in ranked
        if stock[s].extra["depth_usd_at_max_slippage"] >= sel_cfg.min_pool_depth_usd
    ]
    selected = selected[: sel_cfg.max_tokens]

    # ---------------------------------------------------------------- vault factory sanity
    log.info("checking vault factory")
    vault_checks = [
        Call(core["vault_v2_factory"].address, "isVaultV2(address)(bool)", (v["address"],))
        for v in vaults_api
    ]
    vault_flags = call_many(w3, vault_checks, block=fresh("vault_factory")) if vault_checks else []
    known_vaults = [
        {
            "address": v["address"],
            "name": v["name"],
            "asset": (v.get("asset") or {}).get("symbol"),
            "is_vault_v2_from_factory": bool(flag),
        }
        for v, flag in zip(vaults_api, vault_flags, strict=True)
    ]
    core["vault_v2_factory"].check(
        "isVaultV2(...) true for at least one vault listed by the Morpho API",
        sum(1 for v in known_vaults if v["is_vault_v2_from_factory"]),
        ok=any(v["is_vault_v2_from_factory"] for v in known_vaults),
    )
    core["vault_v2_factory"].extra["known_vaults"] = known_vaults

    # ---------------------------------------------------------------- oracle study
    log.info("oracle study")
    study: dict[str, Any] | None = None
    if run_oracle_study:
        proxies = {s: stock[s].extra["feed"]["address"] for s in stock}
        study = oracle_study.study(
            w3,
            proxies,
            calendar=cfg.data.exchange_calendar,
            weekends=d.oracle_study.weekends,
            head_block=fresh("oracle_study"),
            max_range=d.oracle_study.max_log_block_range,
            now=head_time,
        )
        study["latest_update"] = oracle_study.latest_updates(w3, proxies, fresh("latest_updates"))

    for key, item in list(core.items()):
        if not item.ok:
            failures.append({"core": key, **item.to_json()})
            del core[key]

    doc: dict[str, Any] = {
        "_meta": {
            "tool": "afterhours discover",
            "profile": profile,
            "chain": d.chain,
            "chain_id": chain_id,
            "head_block": head,
            "state_blocks": state_blocks,
            "head_time": head_time.isoformat(),
            "fork_block": fork_block,
            "generated_at": datetime.now(UTC).isoformat(),
            "sources": src.model_dump(),
        },
        "core": {k: v.to_json() for k, v in core.items()},
        "lltvs": lltv_doc,
        "stock_tokens": {s: stock[s].to_json() for s in ranked},
        "selected": selected,
        "selection_rule": (
            f"Stock Tokens with a Chainlink feed, ranked by summed Uniswap sell depth at "
            f"{cfg.vault.max_slippage:.0%} slippage; "
            f"keep depth >= {sel_cfg.min_pool_depth_usd:,.0f} USD, "
            f"top {sel_cfg.max_tokens}."
        ),
        "_failures": failures,
    }
    return {"discovered": doc, "oracle_study": study}


def write(cfg: AfterhoursConfig, result: dict[str, Any]) -> list[str]:
    """Write the discovered file and artifacts; return the paths written."""
    written: list[str] = []
    path = discovered_path(cfg)
    path.write_text(json.dumps(result["discovered"], indent=2) + "\n")
    written.append(str(path))
    out = cfg.path(cfg.paths.artifacts_dir) / "discovery"
    out.mkdir(parents=True, exist_ok=True)
    if result.get("oracle_study"):
        p = out / "oracle_study.json"
        p.write_text(json.dumps(result["oracle_study"], indent=2) + "\n")
        written.append(str(p))
    return written
