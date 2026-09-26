"""The allocator: one planning cycle, from chain state to executed moves and anchored reasons.

The policy is option B (`policy/option_b.py`): each stock may use the tiers its yearly rating
allows (trailing data only), and on a night when the forecast bad case over the next
`policy.lookahead_closed_periods` closed periods exceeds every tier's limit, its unborrowed money
goes idle. A cycle reads the vault onchain, applies that policy through the allocation LP,
executes the changes (deallocations before allocations, only unborrowed money moves), and logs
one reason card per stock that moved to the registry. Every step emits an event for the API's
event stream.
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
from afterhours.explain.reason import VAULT_SUBJECT, build_card, reason_hash
from afterhours.policy.lp import Plan, StockState, TierSpec, solve, tier_spec
from afterhours.policy.option_b import Decision, decide, live_ratings, reason
from afterhours.risk.live import Forecast, LiveRisk, session_state
from afterhours.state import Store

log = logging.getLogger(__name__)
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
        self.tiers = deployed_tiers(self.deployment)
        self.tier_names = [t.name for t in self.tiers]
        self._ratings: dict[int, dict[str, float | None]] = {}
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

    def ratings(self, year: int) -> dict[str, float | None]:
        """Option B's yearly ratings (cached per year)."""
        if year not in self._ratings:
            fm = self.cfg.backtest.option_a.fixed_map
            self._ratings[year] = live_ratings(
                {s: self.risk.cache.get(f"prices/{s}", allow_stale=True) for s in self.symbols()},
                year,
                fm.window_days,
                fm.quantile,
                fm.min_observations,
            )
        return self._ratings[year]

    def decisions(self, now: datetime, driving: dict[str, Forecast]) -> dict[str, Decision]:
        p = self.cfg.policy
        ratings = self.ratings(now.year)
        return {
            s: decide(
                s,
                ratings.get(s),
                now.year,
                driving[s].bad_case_drop,
                self.tiers,
                p.map_fraction,
                p.pullback_fraction,
            )
            for s in self.symbols()
        }

    def plan(
        self, state: VaultState, forecasts: dict[str, list[Forecast]]
    ) -> tuple[Plan, dict[str, Forecast]]:
        """Solve the LP for the current state under option B."""
        driving = {s: max(fs, key=lambda f: f.bad_case_drop) for s, fs in forecasts.items()}
        self.last_decisions = self.decisions(self.now(state), driving)
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
                    bad_case_drop=self.last_decisions[s].lp_drop,
                    depth_usd=self.depth.get(s, 1e18)
                    if not self.deployment["simulation"]["collateral"]
                    else 1e18,
                    rate=rate,
                    borrowed={t: by_key[(s, t)].lent_out for t in self.tier_names},
                    cap={t: by_key[(s, t)].absolute_cap for t in self.tier_names},
                    prev={t: by_key[(s, t)].vault_supply for t in self.tier_names},
                )
            )
        p = self.cfg.policy
        plan = solve(
            stocks,
            self.tiers,
            total=state.total_assets,
            safety_margin=0.0,
            turnover_penalty=p.turnover_penalty,
            min_rebalance_usd=p.min_rebalance_usd,
            max_share_per_stock=self.cfg.vault.max_share_per_stock * (1 - 1e-6),
            depth_multiplier=self.cfg.vault.depth_multiplier,
            idle_reserve_share=p.idle_reserve_share,
            margin_fraction=p.map_fraction,
        )
        # The LP's generic reason text talks about bad-case drops; B's reasons say what B did.
        for s, d in self.last_decisions.items():
            text = reason(d, self.tiers, p.map_fraction, p.lookahead_closed_periods)
            for name in self.tier_names:
                plan.reasons[(s, name)] = text
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
        plan_doc = plan_json(plan, driving, state, now, trigger, self.last_decisions)
        last = self.store.read("plan")
        if last is None or last.get("allocation") != plan_doc["allocation"]:
            self.store.emit("plan_changed", plan_doc)
        self.store.write("plan", plan_doc)
        self.store.write("forecasts", {s: [f.to_json() for f in fs] for s, fs in forecasts.items()})
        result = CycleResult(trigger, now.isoformat(), plan_doc, False)
        plan_doc["dust_threshold_usdg"] = self.cfg.policy.min_rebalance_usd
        if not (execute and plan.execute and plan.status == "optimal"):
            return result
        moves = self._execute(state, plan, result)
        self._anchor_reasons(state, plan, driving, moves, result)
        self._route_liquidity(read_state(self.w3, self.deployment), plan, driving, result)
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
            result.plan.setdefault("executed_markets", []).append(f"{m.symbol}:{m.tier}")
            mv = moves.setdefault(m.symbol, {"out": {}, "in": {}, "txs": []})
            mv["out" if amount < 0 else "in"][m.tier] = mv["out" if amount < 0 else "in"].get(
                m.tier, 0.0
            ) + abs(amount)
            mv["txs"].append(sent.tx_hash)
        return moves

    def _route_liquidity(
        self, state: VaultState, plan: Plan, driving: dict[str, Forecast], result: CycleResult
    ) -> None:
        """Point deposits and withdrawals at the safest allowed lowest-LLTV market (SPEC 6.3)."""
        lowest = min(self.tiers, key=lambda t: t.lltv)
        # Deposits land in the liquidity market at once, so it must have room under the stock cap
        # (Vault V2 reverts with RelativeCapExceeded otherwise). No such market: deposits stay idle.
        cap = self.cfg.vault.max_share_per_stock * state.total_assets
        room_needed = self.cfg.policy.liquidity_min_headroom_share * state.total_assets
        held = {
            s: sum(m.vault_supply for m in state.markets if m.symbol == s) for s in self.symbols()
        }
        allowed = [
            m
            for m in state.markets
            if m.tier == lowest.name
            and plan.allowed.get((m.symbol, m.tier))
            and cap - held[m.symbol] >= room_needed
        ]
        if not allowed:
            if state.liquidity_market is not None:
                self._clear_liquidity(state, result)
            return
        target = min(allowed, key=lambda m: driving[m.symbol].bad_case_drop)
        key = f"{target.symbol}:{target.tier}"
        if state.liquidity_market == key:
            return
        vault = self.deployment["vault"]["address"]
        adapter = self.deployment["adapter"]["address"]
        sent = self.allocator.send(
            vault,
            "setLiquidityAdapterAndData(address,bytes)",
            adapter,
            encode([PARAMS_TYPE], [target.params]),
        )
        self.store.emit(
            "tx_confirmed",
            {
                "tx": sent.tx_hash,
                "block": sent.block,
                "symbol": target.symbol,
                "tier": target.tier,
                "function": "setLiquidityAdapterAndData",
            },
        )
        f = driving[target.symbol]
        card = build_card(
            profile=self.profile,
            subject=VAULT_SUBJECT,
            stock=target.symbol,
            action="queue_reorder",
            from_tier=state.liquidity_market,
            to_tier=key,
            amount_usdg=0.0,
            forecast=f,
            rule=(
                f"New deposits and withdrawals now use {target.symbol}'s {lowest.name} tier "
                f"market, the safest allowed market: bad case {f.bad_case_drop:.1%} against a "
                "cushion of "
                f"{lowest.cushion:.1%}."
            ),
            created_at=self.now(),
        )
        self._log_card(card, sent.tx_hash, result)

    def _clear_liquidity(self, state: VaultState, result: CycleResult) -> None:
        """Route deposits to idle cash when no market has room."""
        sent = self.allocator.send(
            self.deployment["vault"]["address"],
            "setLiquidityAdapterAndData(address,bytes)",
            "0x" + "0" * 40,
            b"",
        )
        self.store.emit(
            "tx_confirmed",
            {
                "tx": sent.tx_hash,
                "block": sent.block,
                "function": "setLiquidityAdapterAndData",
                "symbol": None,
            },
        )
        result.txs.append(sent.tx_hash)

    def _log_card(self, card: dict[str, Any], move_tx: str, result: CycleResult) -> None:
        """Hash a card, log it to the registry, store it and emit reason_logged."""
        h = reason_hash(card)
        sent = self.allocator.send(
            self.deployment["registry"]["address"],
            "logReason(bytes32,bytes32,string)",
            bytes.fromhex(card["subject"][2:]),
            bytes.fromhex(h[2:]),
            f"afterhours:reason:{card['id']}",
        )
        card["tx"] = {
            "chain_id": int(self.w3.eth.chain_id),
            "reallocate_tx": move_tx,
            "registry_tx": sent.tx_hash,
        }
        card["reason_hash"] = h
        self.store.add_reason(card)
        self.store.emit(
            "reason_logged",
            {"id": card["id"], "stock": card["stock"], "hash": h, "registry_tx": sent.tx_hash},
        )
        result.reasons.append(card["id"])

    def _why(
        self, plan: Plan, symbol: str, out_tier: str | None, in_tier: str | None, state: VaultState
    ) -> str:
        """Plain-English cause of a move: risk first, then rates, then limits."""
        tiers = self.tier_names
        if out_tier in tiers and not plan.allowed[(symbol, out_tier)]:
            return plan.reasons[(symbol, out_tier)]
        if in_tier in tiers and out_tier not in tiers:
            return (
                f"Placed idle USDG where the tier map allows it. {plan.reasons[(symbol, in_tier)]}"
            )
        rates = {(m.symbol, m.tier): m.supply_apy for m in state.markets}
        if out_tier in tiers and in_tier in tiers:
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
            self._log_card(card, mv["txs"][-1], result)


def _pct(x: float) -> str:
    return f"{x:.2%}"


def deployed_tiers(deployment: dict[str, Any]) -> list[TierSpec]:
    """The deployment's tiers, highest LLTV first."""
    tiers = deployment["tiers"]
    return [
        tier_spec(name, float(v["lltv"]))
        for name, v in sorted(tiers.items(), key=lambda kv: -float(kv[1]["lltv"]))
    ]


def plan_json(
    plan: Plan,
    driving: dict[str, Forecast],
    state: VaultState,
    now: datetime,
    trigger: str,
    decisions: dict[str, Decision] | None = None,
) -> dict[str, Any]:
    """JSON view of a plan."""
    return {
        "policy": "option_b",
        "decisions": {
            s: {
                "rating": d.rating,
                "rating_year": d.rating_year,
                "mapped_tier": d.mapped_tier,
                "forecast_bad_case": d.forecast_bad_case,
                "pull_limit": d.pull_limit,
                "pulled": d.pulled,
            }
            for s, d in (decisions or {}).items()
        },
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
