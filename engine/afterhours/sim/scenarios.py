"""Scripted scenarios for the demo (Simulation; fork and local chains only).

- closing_bell: step the chain to each next pre-close check and run a cycle, until the bot
  de-risks (a reason card is logged) or `demo.max_closes` bells pass; then ring the bell by
  moving past the close.
- earnings_shock: gap a stock's simulated oracle at the next open, then liquidate every
  unhealthy borrower through Morpho and report the bad debt per market.
- oracle_drift: walk a simulated oracle down in steps so the scheduler's shock trigger fires.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from web3 import Web3

from afterhours.bot.allocator import Allocator
from afterhours.bot.vault_state import PARAMS_TYPE, read_state
from afterhours.chain.rpc import Call, call_many
from afterhours.chain.tx import Signer
from afterhours.config import AfterhoursConfig
from afterhours.deploy import role_keys
from afterhours.risk.live import session_state
from afterhours.sim.seed import Anvil, actor

log = logging.getLogger(__name__)
POSITION = "position(bytes32,address)(uint256,uint128,uint128)"
MARKET = "market(bytes32)(uint128,uint128,uint128,uint128,uint128,uint128)"


def set_time(w3: Web3, when: datetime) -> None:
    """Mine a block at `when` (Anvil)."""
    w3.provider.make_request("evm_setNextBlockTimestamp", [int(when.timestamp())])  # type: ignore[arg-type]
    w3.provider.make_request("evm_mine", [])  # type: ignore[arg-type]


def closing_bell(cfg: AfterhoursConfig, max_closes: int) -> dict[str, Any]:
    """Advance bell by bell until the pullback fires for a stock and its unborrowed money leaves.

    A settling cycle first absorbs rebalancing caused by seeding (new borrowers change live
    rates), so the scenario reports risk-driven moves only.
    """
    bot = Allocator(cfg)
    w3 = bot.w3
    settle = bot.run_cycle("settle")
    pulled_before = {s for s, d in settle.plan["decisions"].items() if d["pulled"]}
    steps = []
    for _ in range(max_closes):
        now = bot.now()
        s = session_state(cfg.data.exchange_calendar, now)
        check = s.next_close - timedelta(minutes=cfg.schedule.pre_close_minutes)
        if check <= now:
            check = now + timedelta(seconds=1)
        set_time(w3, check)
        result = bot.run_cycle("pre_close")
        pulled_now = {s for s, d in result.plan["decisions"].items() if d["pulled"]}
        flipped = sorted(pulled_now - pulled_before)
        pulled_before = pulled_now
        steps.append(
            {
                "at": check.isoformat(),
                "executed": result.executed,
                "reasons": result.reasons,
                "pulled_back": flipped,
                "allocation": result.plan["allocation"],
            }
        )
        set_time(w3, s.next_close + timedelta(seconds=5))  # the bell rings
        bot.store.emit(
            "status",
            session_state(cfg.data.exchange_calendar, bot.now()).to_json()
            | {"trigger": "closing_bell"},
        )
        if flipped and result.executed:
            cards = {c["id"]: c for c in bot.store.reasons()}
            moved = [cards[r] for r in result.reasons if cards[r]["stock"] in flipped]
            return {
                "scenario": "closing_bell",
                "derisked": True,
                "bell": s.next_close.isoformat(),
                "stocks": flipped,
                "reasons": [
                    {
                        "id": c["id"],
                        "stock": c["stock"],
                        "from": c["from_tier"],
                        "to": c["to_tier"],
                        "amount_usdg": c["amount_usdg"],
                        "rule": c["rule_fired"],
                        "registry_tx": c["tx"]["registry_tx"],
                    }
                    for c in moved
                ],
                "steps": steps,
            }
    return {"scenario": "closing_bell", "derisked": False, "steps": steps}


def earnings_shock(cfg: AfterhoursConfig, symbol: str, pct: float) -> dict[str, Any]:
    """Gap `symbol` at the next open, then liquidate unhealthy borrowers and measure bad debt."""
    bot = Allocator(cfg)
    w3 = bot.w3
    d = bot.deployment
    if not d["simulation"]["oracle"]:
        raise RuntimeError("earnings_shock needs simulated oracles (local profile)")
    owner = Signer(w3, role_keys(cfg, cfg.active_profile)["DEPLOYER_PK"])
    anvil = Anvil(w3)
    now = bot.now()
    s = session_state(cfg.data.exchange_calendar, now)
    set_time(w3, s.next_open + timedelta(seconds=5))
    markets = [m for m in read_state(w3, d).markets if m.symbol == symbol]
    oracle = markets[0].params[2]
    price = int(call_many(w3, [Call(oracle, "price8()(uint256)")])[0])
    owner.send(oracle, "setPrice(uint256)", max(1, int(price * (1 + pct))))
    before = read_state(w3, d).total_assets
    morpho = d["morpho"]["address"]
    liquidator = actor("liquidator")
    anvil.fund_eth(liquidator, 10)
    per_market: list[dict[str, Any]] = []
    for m in markets:
        mid = bytes.fromhex(m.market_id[2:])
        pre = call_many(w3, [Call(morpho, MARKET, (mid,))])[0]
        for j in range(cfg.sim.borrowers_per_market):
            who = actor(f"borrower-{m.symbol}-{m.tier}-{j}")
            _, _, collateral = call_many(w3, [Call(morpho, POSITION, (mid, who))])[0]
            if not collateral:
                continue
            owner.send(d["loan_token"]["address"], "mint(address,uint256)", liquidator, 10**15)
            anvil.send_as(
                liquidator, d["loan_token"]["address"], "approve(address,uint256)", morpho, 2**255
            )
            try:
                anvil.send_as(
                    liquidator,
                    morpho,
                    f"liquidate({PARAMS_TYPE},address,uint256,uint256,bytes)(uint256,uint256)",
                    m.params,
                    who,
                    int(collateral),
                    0,
                    b"",
                )
            except Exception:  # Morpho reverts when the position is still healthy
                log.info("%s on %s %s is still healthy", who, m.symbol, m.tier)
        post = call_many(w3, [Call(morpho, MARKET, (mid,))])[0]
        per_market.append(
            {
                "tier": m.tier,
                "lltv": m.params[4] / 1e18,
                "vault_supply_usdg": m.vault_supply,
                "lent_out_usdg": m.lent_out,
                "supply_lost_usdg": (int(pre[0]) - int(post[0])) / 10**6,
            }
        )
    after = read_state(w3, d).total_assets
    bot.store.emit("vault_updated", read_state(w3, d).to_json())
    exposure = sum(float(x["lent_out_usdg"]) for x in per_market)
    return {
        "scenario": "earnings_shock",
        "symbol": symbol,
        "gap": pct,
        "markets": per_market,
        "vault_exposure_usdg": exposure,
        "vault_loss_usdg": before - after,
        "note": (
            f"The vault had no loans against {symbol} when it gapped; nothing to lose."
            if exposure == 0
            else f"Loss from {exposure:,.0f} USDG lent against {symbol}."
        ),
    }


def oracle_drift(
    cfg: AfterhoursConfig, symbol: str, step_pct: float, steps: int, minutes_per_step: int
) -> dict[str, Any]:
    """Walk a simulated oracle in steps of `step_pct`, advancing the chain between steps."""
    from afterhours.bot.scheduler import BotScheduler

    sched = BotScheduler(cfg)
    w3 = sched.allocator.w3
    owner = Signer(w3, role_keys(cfg, cfg.active_profile)["DEPLOYER_PK"])
    oracle = sched.oracles[symbol]
    fired: list[list[str]] = []
    sched.tick()
    for _ in range(steps):
        price = int(call_many(w3, [Call(oracle, "price8()(uint256)")])[0])
        owner.send(oracle, "setPrice(uint256)", max(1, int(price * (1 + step_pct))))
        set_time(
            w3,
            datetime.fromtimestamp(int(w3.eth.get_block("latest")["timestamp"]), UTC)
            + timedelta(minutes=minutes_per_step),
        )
        fired.append(sched.tick())
    return {"scenario": "oracle_drift", "symbol": symbol, "fired": fired}
