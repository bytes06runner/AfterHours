"""Afterhours API (SPEC 8). Reads chain state, the bot's state files and generated artifacts.

Run with `make api`. Simulation endpoints need the admin token and a fork or local profile.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from web3 import Web3

from afterhours.bot.vault_state import read_state
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import AfterhoursConfig, load_config
from afterhours.data.pipeline import make_cache
from afterhours.deployments import load_deployment
from afterhours.explain.reason import canonical
from afterhours.explain.verify import verify_card
from afterhours.policy.lp import allowed_tier, tier_spec
from afterhours.public_config import public_config
from afterhours.risk.live import LiveRisk, session_state, upcoming_periods
from afterhours.state import Store


class Shock(BaseModel):
    """Body of POST /v1/sim/shock."""

    symbol: str
    pct: float  # e.g. -0.2 for a 20% drop


class FaucetRequest(BaseModel):
    """Body of POST /v1/sim/faucet."""

    address: str


class Context:
    """Per-process handles, created lazily so the API starts even when the chain is down."""

    def __init__(self, cfg: AfterhoursConfig) -> None:
        self.cfg = cfg
        self.store = Store.for_profile(cfg)
        self.risk = LiveRisk(cfg, make_cache(cfg))
        self._w3: Web3 | None = None
        self._verified: dict[str, dict[str, Any]] = {}

    @property
    def deployment(self) -> dict[str, Any]:
        return load_deployment(self.cfg)

    @property
    def chain_clock(self) -> bool:
        return self.cfg.profile.local_rpc_port_env is not None

    def w3(self) -> Web3:
        if self._w3 is None:
            self._w3 = connect(self.cfg.node_url())
        return self._w3

    def now(self) -> datetime:
        if self.chain_clock:
            try:
                return datetime.fromtimestamp(
                    int(self.w3().eth.get_block("latest")["timestamp"]), UTC
                )
            except Exception as exc:
                raise HTTPException(
                    503, f"Can't reach the {self.cfg.active_profile} chain. Retrying shortly."
                ) from exc
        return datetime.now(UTC)

    def artifact(self, *parts: str) -> dict[str, Any]:
        path = self.cfg.path(self.cfg.paths.artifacts_dir).joinpath(*parts)
        return _read_json(str(path), path.stat().st_mtime if path.exists() else 0)

    def verified(self, card: dict[str, Any]) -> dict[str, Any]:
        cid = str(card["id"])
        if cid not in self._verified:
            self._verified[cid] = verify_card(
                self.w3(), card, self.deployment["registry"]["address"]
            )
        return self._verified[cid]


@lru_cache(maxsize=64)
def _read_json(path: str, mtime: float) -> dict[str, Any]:
    if not mtime:
        raise HTTPException(404, f"{Path(path).name} has not been generated yet")
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def next_pre_close(cfg: AfterhoursConfig, now: datetime) -> datetime:
    """The next pre-close check strictly after `now`: today's if ahead, else the next session's."""
    from afterhours.features.dataset import sessions

    sess = sessions(cfg.data.exchange_calendar, now.date(), (now + timedelta(days=10)).date())
    lead = timedelta(minutes=cfg.schedule.pre_close_minutes)
    checks: list[datetime] = [c.to_pydatetime() - lead for c in sess["close"]]
    return min(t for t in checks if t > now)


def create_app(cfg: AfterhoursConfig | None = None) -> FastAPI:
    """Build the FastAPI app."""
    cfg = cfg or load_config()
    ctx = Context(cfg)
    app = FastAPI(title="Afterhours API", version="1")
    origins = [o.strip() for o in (cfg.env(cfg.api.cors_origins_env) or "").split(",") if o.strip()]
    if not origins:
        port = cfg.env(cfg.api.web_port_env) or ""
        origins = [t.format(port=port) for t in cfg.api.local_web_origin_templates] if port else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["authorization", "content-type"],
    )

    def admin(authorization: Annotated[str | None, Header()] = None) -> None:
        token = cfg.env(cfg.api.admin_token_env)
        if not token:
            raise HTTPException(403, "Simulation endpoints are off: set ADMIN_TOKEN.")
        if not authorization or not secrets.compare_digest(authorization, f"Bearer {token}"):
            raise HTTPException(401, "Wrong or missing admin token.")
        if not ctx.chain_clock:
            raise HTTPException(403, "Simulation endpoints run only on fork and local chains.")

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        chain: dict[str, Any] = {
            "profile": cfg.active_profile,
            "clock": "chain" if ctx.chain_clock else "wall",
        }
        try:
            w3 = ctx.w3()
            chain |= {
                "reachable": True,
                "chain_id": int(w3.eth.chain_id),
                "block": int(w3.eth.block_number),
            }
        except Exception:
            chain |= {"reachable": False}
        plan = ctx.store.read("plan")
        prod = ctx.risk.production
        return {
            "service": "ok",
            "chain": chain,
            "model": {"shipped": prod["shipped"], "model_version": prod["model_version"]},
            "scheduler": {
                "last_cycle": plan.get("now") if plan else None,
                "last_trigger": plan.get("trigger") if plan else None,
            },
        }

    @app.get("/v1/config/public")
    def config_public() -> dict[str, Any]:
        return public_config(cfg)

    @app.get("/v1/status")
    def status() -> dict[str, Any]:
        now = ctx.now()
        s = session_state(cfg.data.exchange_calendar, now)
        return s.to_json() | {
            "clock": "chain" if ctx.chain_clock else "wall",
            "profile": cfg.active_profile,
        }

    @app.get("/v1/vault")
    def vault() -> dict[str, Any]:
        d = ctx.deployment
        if not d:
            raise HTTPException(404, "No deployment for this profile yet.")
        try:
            w3 = ctx.w3()
            state = read_state(w3, d)
            v = d["vault"]["address"]
            share_dec = int(call_many(w3, [Call(v, "decimals()(uint8)")])[0])
            assets_per_share = call_many(
                w3, [Call(v, "convertToAssets(uint256)(uint256)", (10**share_dec,))]
            )[0]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                503, f"Can't reach the {cfg.active_profile} chain. Retrying shortly."
            ) from exc
        placed = sum(m.vault_supply for m in state.markets)
        apy = (
            sum(m.vault_supply * m.supply_apy for m in state.markets) / state.total_assets
            if state.total_assets
            else 0.0
        )
        return {
            "profile": cfg.active_profile,
            "simulation": d["simulation"],
            "block": state.block,
            "tvl_usdg": state.total_assets,
            "idle_usdg": state.idle,
            "placed_usdg": placed,
            "liquidity_market": state.liquidity_market,
            "withdrawable_now_usdg": state.withdrawable_now,
            "idle_reserve_share": cfg.policy.idle_reserve_share,
            "max_share_per_stock": cfg.vault.max_share_per_stock,
            "apy": apy,
            "share_price": int(assets_per_share) / 10**state.decimals,
            "tiers": d["tiers"],
            "markets": [m.to_json() for m in state.markets],
        }

    @app.get("/v1/prices")
    def prices() -> dict[str, Any]:
        """Each Stock Token's price from its market oracle (Morpho IOracle, 1e36 scale)."""
        d = ctx.deployment
        if not d:
            raise HTTPException(404, "No deployment for this profile yet.")
        oracles = {m["symbol"]: m for m in d["markets"] if m["tier"] == "weekday"}
        try:
            w3 = ctx.w3()
            loan_dec = int(
                call_many(w3, [Call(d["loan_token"]["address"], "decimals()(uint8)")])[0]
            )
            coll_dec = call_many(
                w3, [Call(m["collateral"], "decimals()(uint8)") for m in oracles.values()]
            )
            raw = call_many(w3, [Call(m["oracle"], "price()(uint256)") for m in oracles.values()])
        except Exception as exc:
            raise HTTPException(
                503, f"Can't reach the {cfg.active_profile} chain. Retrying shortly."
            ) from exc
        source = "simulated" if d["simulation"]["oracle"] else "chainlink"
        items = []
        for (sym, _), dec, price in zip(oracles.items(), coll_dec, raw, strict=True):
            if price is None or dec is None:
                continue
            scale = 10 ** (36 + loan_dec - int(dec))
            items.append({"symbol": sym, "price_usdg": int(price) / scale})
        return {"source": source, "prices": items}

    @app.get("/v1/risk")
    def risk() -> dict[str, Any]:
        now = ctx.now()
        d = ctx.deployment
        tiers = (
            [tier_spec(n, float(d["tiers"][n]["lltv"])) for n in ("weekday", "weekend")]
            if d
            else []
        )
        symbols = list(dict.fromkeys(m["symbol"] for m in d.get("markets", []))) if d else []
        out = []
        for s in symbols:
            fs = ctx.risk.forecast(s, now, cfg.policy.lookahead_closed_periods)
            worst = max(fs, key=lambda f: f.bad_case_drop)
            allowed = {
                t.name: dict(
                    zip(
                        ("allowed", "reason"),
                        allowed_tier(worst.bad_case_drop, cfg.policy.safety_margin, t),
                        strict=True,
                    )
                )
                for t in tiers
            }
            out.append(
                {
                    "symbol": s,
                    "next": fs[0].to_json(),
                    "worst_in_lookahead": worst.to_json(),
                    "tiers": allowed,
                }
            )
        return {
            "now": now.isoformat(),
            "lookahead_closed_periods": cfg.policy.lookahead_closed_periods,
            "safety_margin": cfg.policy.safety_margin,
            "stocks": out,
        }

    @app.get("/v1/almanac")
    def almanac(days: Annotated[int, Query(ge=1)] = 14) -> dict[str, Any]:
        days = min(days, cfg.api.almanac_max_days)
        now = ctx.now()
        end = now + timedelta(days=days)
        d = ctx.deployment
        symbols = list(dict.fromkeys(m["symbol"] for m in d.get("markets", []))) if d else []
        periods = [
            p
            for p in upcoming_periods(cfg.data.exchange_calendar, now, days * 2, None)
            if p.starts < end
        ]
        cache = make_cache(cfg)
        stocks = []
        for s in symbols:
            fs = ctx.risk.forecast(s, now, len(periods))
            ev = cache.get(f"earnings/{s}", allow_stale=True)
            earnings = (
                []
                if ev is None
                else [
                    {"date": str(r["date"]), "timing": r["timing"]}
                    for r in ev.to_dict("records")
                    if now.date() <= r["date"] <= end.date()
                ]
            )
            stocks.append(
                {"symbol": s, "earnings": earnings, "forecasts": [f.to_json() for f in fs]}
            )
        return {
            "now": now.isoformat(),
            "days": days,
            "periods": [p.to_json() for p in periods],
            "stocks": stocks,
        }

    @app.get("/v1/reasons")
    def reasons(
        cursor: int = 0, stock: str | None = None, action: str | None = None
    ) -> dict[str, Any]:
        cards = [
            c
            for c in ctx.store.reasons()
            if (stock is None or c["stock"] == stock) and (action is None or c["action"] == action)
        ]
        page = cards[cursor : cursor + cfg.api.reasons_page_size]
        nxt = cursor + len(page)
        plan = ctx.store.read("plan")
        return {
            "items": page,
            "next_cursor": nxt if nxt < len(cards) else None,
            "total": len(cards),
            "next_plan": plan.get("driving_forecast") if plan else None,
        }

    @app.get("/v1/reasons/{card_id}")
    def reason(card_id: str) -> dict[str, Any]:
        card = next((c for c in ctx.store.reasons() if c["id"] == card_id), None)
        if card is None:
            raise HTTPException(404, "No reason card with that id.")
        return {
            "card": card,
            "canonical_json": canonical(card).decode(),
            "verification": ctx.verified(card),
        }

    @app.get("/v1/report-card")
    def report_card() -> dict[str, Any]:
        card = ctx.artifact("model", "report_card.json")
        bt = ctx.artifact("backtest", "results.json")
        gaps = ctx.artifact("gaps", "summary.json")
        return {
            "model": {
                k: card[k]
                for k in (
                    "first_sentence",
                    "label",
                    "acceptance",
                    "shipped_performance",
                    "calibration_curves",
                    "variants_tried",
                    "code_version",
                    "config",
                )
            }
            | {"model_version": card["production"]["model_version"], "folds": len(card["folds"])},
            "backtest": {
                k: bt[k]
                for k in (
                    "label",
                    "period",
                    "selected",
                    "chosen",
                    "strategies",
                    "sensitivity",
                    "assumptions",
                    "forecast",
                )
            },
            "gaps": {
                k: gaps[k]
                for k in (
                    "label",
                    "period",
                    "tickers",
                    "universe",
                    "selected",
                    "worst_selected",
                    "histograms",
                    "tail",
                )
            },
        }

    @app.get("/v1/replay/scenarios")
    def replay_scenarios() -> dict[str, Any]:
        return ctx.artifact("backtest", "scenarios.json")

    @app.get("/v1/replay/{scenario_id}")
    def replay(scenario_id: str) -> dict[str, Any]:
        if "/" in scenario_id or ".." in scenario_id:
            raise HTTPException(400, "Bad scenario id.")
        return ctx.artifact("backtest", "replay", f"{scenario_id}.json")

    @app.post("/v1/sim/close-out", dependencies=[Depends(admin)])
    def sim_close_out() -> dict[str, Any]:
        from afterhours.bot.allocator import Allocator

        w3 = ctx.w3()
        now = ctx.now()
        target = next_pre_close(cfg, now)
        w3.provider.make_request("evm_setNextBlockTimestamp", [int(target.timestamp())])  # type: ignore[arg-type]
        w3.provider.make_request("evm_mine", [])  # type: ignore[arg-type]
        result = Allocator(cfg).run_cycle("close_out")
        return {
            "moved_to": target.isoformat(),
            "executed": result.executed,
            "txs": result.txs,
            "reasons": result.reasons,
            "plan": result.plan,
        }

    @app.post("/v1/sim/shock", dependencies=[Depends(admin)])
    def sim_shock(body: Shock) -> dict[str, Any]:
        from afterhours.chain.tx import Signer
        from afterhours.deploy import role_keys

        d = ctx.deployment
        if not d["simulation"]["oracle"]:
            raise HTTPException(400, "Shocks need simulated oracles (local profile).")
        oracle = next((m["oracle"] for m in d["markets"] if m["symbol"] == body.symbol), None)
        if oracle is None:
            raise HTTPException(404, f"No market for {body.symbol}.")
        w3 = ctx.w3()
        price = int(call_many(w3, [Call(oracle, "price8()(uint256)")])[0])
        new = max(1, int(price * (1 + body.pct)))
        Signer(w3, role_keys(cfg, cfg.active_profile)["DEPLOYER_PK"]).send(
            oracle, "setPrice(uint256)", new
        )
        ctx.store.emit("status", {"shock": body.symbol, "pct": body.pct, "price8": new})
        return {"symbol": body.symbol, "old_price8": price, "new_price8": new}

    faucet_log: dict[str, float] = {}

    @app.post("/v1/sim/faucet")
    def sim_faucet(body: FaucetRequest) -> dict[str, Any]:
        """Simulated USDG and gas for a browser wallet (local profile, simulated loan token)."""
        import time as _time

        from afterhours.chain.tx import Signer
        from afterhours.deploy import role_keys

        d = ctx.deployment
        if cfg.active_profile != "local" or not d or not d["simulation"]["collateral"]:
            raise HTTPException(403, "The faucet runs only on the local simulation.")
        if not Web3.is_address(body.address):
            raise HTTPException(400, "That is not an address.")
        who = Web3.to_checksum_address(body.address)
        f = cfg.sim.faucet
        last = faucet_log.get(who, 0.0)
        if _time.time() - last < f.cooldown_seconds:
            raise HTTPException(429, f"One faucet request per {f.cooldown_seconds} seconds.")
        faucet_log[who] = _time.time()
        w3 = ctx.w3()
        w3.provider.make_request("anvil_setBalance", [who, hex(int(f.eth * 1e18))])  # type: ignore[arg-type]
        loan = d["loan_token"]["address"]
        dec = int(call_many(w3, [Call(loan, "decimals()(uint8)")])[0])
        Signer(w3, role_keys(cfg, cfg.active_profile)["DEPLOYER_PK"]).send(
            loan, "mint(address,uint256)", who, int(f.usdg * 10**dec)
        )
        return {"address": who, "usdg": f.usdg, "eth": f.eth, "label": "Simulation"}

    @app.get("/v1/stream")
    async def stream(replay: bool = False) -> EventSourceResponse:
        """Server-sent events. `replay=true` starts from the beginning of the log."""

        async def events() -> Any:
            exists = ctx.store.events_path.exists()
            offset = 0 if replay or not exists else ctx.store.events_path.stat().st_size
            quiet = 0.0
            while True:
                batch, offset = ctx.store.events_since(offset)
                for e in batch:
                    yield {"event": e["type"], "data": json.dumps(e["data"], default=str)}
                    quiet = 0.0
                await asyncio.sleep(cfg.api.sse_poll_seconds)
                quiet += cfg.api.sse_poll_seconds
                if quiet >= cfg.api.sse_heartbeat_seconds:
                    quiet = 0.0
                    try:
                        yield {"event": "status", "data": json.dumps(status())}
                    except HTTPException:
                        yield {"event": "status", "data": json.dumps({"reachable": False})}

        return EventSourceResponse(events())

    return app


def serve() -> None:
    """Run uvicorn with host and port from the environment variables named in config."""
    import uvicorn

    cfg = load_config()
    host = cfg.env(cfg.api.host_env, required=True) or ""
    port = int(cfg.env(cfg.api.port_env, required=True) or "0")
    uvicorn.run(
        create_app(cfg), host=host, port=port, log_level=os.environ.get("LOG_LEVEL", "info").lower()
    )
