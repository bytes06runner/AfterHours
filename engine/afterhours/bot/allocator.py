"""The allocator: one planning cycle, from chain state to executed moves and anchored reasons.

A cycle reads the vault onchain, forecasts each stock's bad case over the next
`policy.lookahead_closed_periods` closed periods, solves the allocation LP, executes the changes
(deallocations before allocations, only unborrowed money moves), and logs one reason card per
stock that moved to the registry. Every step emits an event for the API's event stream.
"""

from __future__ import annotations

import fcntl
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from eth_abi import encode

from afterhours.bot.vault_state import PARAMS_TYPE, VaultState, read_state
from afterhours.chain.rpc import connect
from afterhours.chain.tx import Signer
from afterhours.config import AfterhoursConfig
from afterhours.data.pipeline import make_cache
from afterhours.deploy import role_keys
from afterhours.deployments import load_deployment, load_discovered
from afterhours.explain.reason import build_card, reason_hash
from afterhours.policy.lp import Plan, StockState, solve, tier_spec
from afterhours.risk.live import Forecast, LiveRisk, session_state
from afterhours.state import Store

log = logging.getLogger(__name__)
TIERS = ("weekday", "weekend")
DUST_UNITS = 2  # stay a hair inside caps and withdrawable amounts


@dataclass
class CycleResult:
    """What one cycle decided and did."""

    trigger: str
    now: str
    plan: dict[str, Any]
    executed: bool
    txs: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@contextmanager
def cycle_lock(store: Store) -> Iterator[None]:
    """One cycle at a time across processes (bot scheduler and API sim endpoints)."""
    with (store.root / "cycle.lock").open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class Allocator:
    """Runs planning cycles for the active profile."""

    def __init__(self, cfg: AfterhoursConfig) -> None:
        self.cfg = cfg
        self.profile = cfg.active_profile
        self.deployment = load_deployment(cfg)
        if not self.deployment:
            raise RuntimeError(f"no deployments/{self.profile}.json; run `make deploy`")
        self.w3 = connect(cfg.node_url(self.profile))
        self.store = Store.for_profile(cfg)
        self.risk = LiveRisk(cfg, make_cache(cfg))
        keys = role_keys(cfg, self.profile)
        self.allocator = Signer(self.w3, keys["ALLOCATOR_PK"])
        tiers = self.deployment["tiers"]
        self.tiers = [
            tier_spec("weekday", tiers["weekday"]["lltv"]),
            tier_spec("weekend", tiers["weekend"]["lltv"]),
        ]
        self.depth = {
            s: float(v.get("depth_usd_at_max_slippage", 0.0))
            for s, v in load_discovered(cfg, "fork").get("stock_tokens", {}).items()
        }
        self.chain_clock = cfg.profile.local_rpc_port_env is not None
        self.rate_source = "assumed (no borrowing yet)"

    def now(self, state: VaultState | None = None) -> datetime:
        """Chain time on local and fork profiles (the demo moves it), wall time elsewhere."""
        if self.chain_clock:
            ts = state.timestamp if state else int(self.w3.eth.get_block("latest")["timestamp"])
            return datetime.fromtimestamp(ts, UTC)
        return datetime.now(UTC)

    def symbols(self) -> list[str]:
        return list(dict.fromkeys(m["symbol"] for m in self.deployment["markets"]))

    def forecasts(self, now: datetime) -> dict[str, list[Forecast]]:
        h = self.cfg.policy.lookahead_closed_periods
        return {s: self.risk.forecast(s, now, h) for s in self.symbols()}

    def plan(
        self, state: VaultState, forecasts: dict[str, list[Forecast]]
    ) -> tuple[Plan, dict[str, Forecast]]:
        """Solve the LP for the current state and forecasts."""
        driving = {s: max(fs, key=lambda f: f.bad_case_drop) for s, fs in forecasts.items()}
        by_key = {(m.symbol, m.tier): m for m in state.markets}
        # Live supply rates once anything is borrowed; the backtest's assumed rates only at cold
        # start. Mixing the two makes the planner chase empty markets.
        live = any(m.supply_apy > 0 for m in state.markets)
        self.rate_source = "live" if live else "assumed (no borrowing yet)"
        stocks = []
        for s in self.symbols():
            rate = {}
            for t in self.tiers:
                m = by_key[(s, t.name)]
                rate[t.name] = m.supply_apy if live else self.cfg.backtest.apy(t.lltv)
            stocks.append(
                StockState(
                    symbol=s,
                    bad_case_drop=driving[s].bad_case_drop,
                    depth_usd=self.depth.get(s, 1e18)
                    if not self.deployment["simulation"]["collateral"]
                    else 1e18,
                    rate=rate,
                    borrowed={t: by_key[(s, t)].lent_out for t in TIERS},
                    cap={t: by_key[(s, t)].absolute_cap for t in TIERS},
                    prev={t: by_key[(s, t)].vault_supply for t in TIERS},
                )
            )
        p = self.cfg.policy
        plan = solve(
            stocks,
            self.tiers,
            total=state.total_assets,
            safety_margin=p.safety_margin,
            turnover_penalty=p.turnover_penalty,
            min_rebalance_usd=p.min_rebalance_usd,
            max_share_per_stock=self.cfg.vault.max_share_per_stock * (1 - 1e-6),
            depth_multiplier=self.cfg.vault.depth_multiplier,
        )
        return plan, driving

    def run_cycle(self, trigger: str, *, execute: bool = True) -> CycleResult:
        """One full cycle under the cross-process lock."""
        with cycle_lock(self.store):
            return self._cycle(trigger, execute=execute)

    def _cycle(self, trigger: str, *, execute: bool) -> CycleResult:
        state = read_state(self.w3, self.deployment)
        now = self.now(state)
        session = session_state(self.cfg.data.exchange_calendar, now)
        self.store.emit("status", session.to_json() | {"trigger": trigger})
        self.store.emit("vault_updated", state.to_json())
        forecasts = self.forecasts(now)
        plan, driving = self.plan(state, forecasts)
        plan_doc = plan_json(plan, driving, state, now, trigger)
        last = self.store.read("plan")
        if last is None or last.get("allocation") != plan_doc["allocation"]:
            self.store.emit("plan_changed", plan_doc)
        self.store.write("plan", plan_doc)
        self.store.write("forecasts", {s: [f.to_json() for f in fs] for s, fs in forecasts.items()})
        result = CycleResult(trigger, now.isoformat(), plan_doc, False)
        if not (execute and plan.execute and plan.status == "optimal"):
            return result
        moves = self._execute(state, plan, result)
        self._anchor_reasons(state, plan, driving, moves, result)
        after = read_state(self.w3, self.deployment)
        self.store.emit("vault_updated", after.to_json())
        result.executed = True
        return result

    def _execute(
        self, state: VaultState, plan: Plan, result: CycleResult
    ) -> dict[str, dict[str, Any]]:
        """Send deallocations then allocations; return per-stock moves."""
        unit = 10**state.decimals
        dust = DUST_UNITS / unit
        vault = self.deployment["vault"]["address"]
        adapter = self.deployment["adapter"]["address"]
        deltas = []
        min_move = self.cfg.policy.min_rebalance_usd
        for m in state.markets:
            target = plan.allocation.get((m.symbol, m.tier), m.vault_supply)
            delta = target - m.vault_supply
            if abs(delta) < min_move and plan.allowed.get((m.symbol, m.tier), True):
                continue  # dust: not worth a transaction or a reason card
            if delta < -dust:
                amount = min(-delta, m.vault_supply - m.lent_out) - dust
                deltas.append((m, -amount))
            elif delta > dust:
                deltas.append((m, delta - dust))
        moves: dict[str, dict[str, Any]] = {}
        for m, amount in sorted(deltas, key=lambda d: d[1]):  # deallocations (negative) first
            if abs(amount) * unit < 1:
                continue
            data = encode([PARAMS_TYPE], [m.params])
            fn = (
                "deallocate(address,bytes,uint256)"
                if amount < 0
                else "allocate(address,bytes,uint256)"
            )
            self.store.emit(
                "tx_sent",
                {
                    "function": fn.split("(", maxsplit=1)[0],
                    "symbol": m.symbol,
                    "tier": m.tier,
                    "amount_usdg": abs(amount),
                },
            )
            sent = self.allocator.send(vault, fn, adapter, data, int(abs(amount) * unit))
            self.store.emit(
                "tx_confirmed",
                {
                    "tx": sent.tx_hash,
                    "block": sent.block,
                    "symbol": m.symbol,
                    "tier": m.tier,
                    "amount_usdg": abs(amount),
                    "function": fn.split("(", maxsplit=1)[0],
                },
            )
            result.txs.append(sent.tx_hash)
            mv = moves.setdefault(m.symbol, {"out": {}, "in": {}, "txs": []})
            mv["out" if amount < 0 else "in"][m.tier] = mv["out" if amount < 0 else "in"].get(
                m.tier, 0.0
            ) + abs(amount)
            mv["txs"].append(sent.tx_hash)
        return moves

    def _why(
        self, plan: Plan, symbol: str, out_tier: str | None, in_tier: str | None, state: VaultState
    ) -> str:
        """Plain-English cause of a move: risk first, then rates, then limits."""
        if out_tier in ("weekday", "weekend") and not plan.allowed[(symbol, out_tier)]:
            text = plan.reasons[(symbol, out_tier)]
            return text[0].upper() + text[1:] + ". Only money not lent out can move."
        if in_tier in ("weekday", "weekend") and out_tier not in ("weekday", "weekend"):
            text = plan.reasons[(symbol, in_tier)]
            return f"Placed idle USDG where it is allowed: {text}."
        rates = {(m.symbol, m.tier): m.supply_apy for m in state.markets}
        if out_tier in ("weekday", "weekend") and in_tier in ("weekday", "weekend"):
            return (
                f"Moved toward a higher supply rate: {in_tier} {_pct(rates[(symbol, in_tier)])} "
                f"vs {out_tier} {_pct(rates[(symbol, out_tier)])} ({self.rate_source} rates)."
            )
        limit = plan.stock_limits.get(symbol, 0.0)
        return (
            f"Returned to idle to keep {symbol} within its limit of {limit:,.0f} USDG "
            f"({self.cfg.vault.max_share_per_stock:.0%} of the vault) or where no market pays more."
        )

    def _anchor_reasons(
        self,
        state: VaultState,
        plan: Plan,
        driving: dict[str, Forecast],
        moves: dict[str, dict[str, Any]],
        result: CycleResult,
    ) -> None:
        """One card per stock that moved, hashed and logged to the registry."""
        registry = self.deployment["registry"]["address"]
        chain_id = int(self.w3.eth.chain_id)
        weekday_id = {m.symbol: m.market_id for m in state.markets if m.tier == "weekday"}
        for symbol, mv in moves.items():
            out_tier = max(mv["out"], key=mv["out"].get) if mv["out"] else None
            in_tier = max(mv["in"], key=mv["in"].get) if mv["in"] else None
            amount = max(sum(mv["out"].values()), sum(mv["in"].values()))
            rule = self._why(plan, symbol, out_tier, in_tier, state)
            if out_tier and in_tier:
                action = "reallocate"
            elif out_tier:
                action, in_tier = "reallocate", "idle"
            else:
                action, out_tier = "reallocate", "idle"
            card = build_card(
                profile=self.profile,
                subject=weekday_id[symbol],
                stock=symbol,
                action=action,
                from_tier=out_tier,
                to_tier=in_tier,
                amount_usdg=amount,
                forecast=driving[symbol],
                rule=rule,
                created_at=self.now(),
            )
            h = reason_hash(card)
            sent = self.allocator.send(
                registry,
                "logReason(bytes32,bytes32,string)",
                bytes.fromhex(card["subject"][2:]),
                bytes.fromhex(h[2:]),
                f"afterhours:reason:{card['id']}",
            )
            card["tx"] = {
                "chain_id": chain_id,
                "reallocate_tx": mv["txs"][-1],
                "registry_tx": sent.tx_hash,
            }
            card["reason_hash"] = h
            self.store.add_reason(card)
            self.store.emit(
                "reason_logged",
                {"id": card["id"], "stock": symbol, "hash": h, "registry_tx": sent.tx_hash},
            )
            result.reasons.append(card["id"])


def _pct(x: float) -> str:
    return f"{x:.2%}"


def plan_json(
    plan: Plan, driving: dict[str, Forecast], state: VaultState, now: datetime, trigger: str
) -> dict[str, Any]:
    """JSON view of a plan."""
    return {
        "trigger": trigger,
        "now": now.isoformat(),
        "status": plan.status,
        "execute": plan.execute,
        "turnover_usdg": plan.turnover,
        "idle_usdg": plan.idle,
        "total_assets_usdg": state.total_assets,
        "allocation": {f"{s}:{t}": round(v, 2) for (s, t), v in sorted(plan.allocation.items())},
        "allowed": {f"{s}:{t}": v for (s, t), v in sorted(plan.allowed.items())},
        "reasons": {f"{s}:{t}": v for (s, t), v in sorted(plan.reasons.items())},
        "driving_forecast": {s: f.to_json() for s, f in driving.items()},
    }


def dump(result: CycleResult) -> str:
    """Pretty summary for the CLI."""
    return json.dumps(
        {
            "trigger": result.trigger,
            "now": result.now,
            "executed": result.executed,
            "txs": len(result.txs),
            "reasons": result.reasons,
            "allocation": result.plan["allocation"],
        },
        indent=2,
    )
