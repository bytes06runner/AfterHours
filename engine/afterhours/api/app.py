"""Afterhours API (SPEC 8). Reads chain state, the bot's state files and generated artifacts.

Run with `make api`. Simulation endpoints need the admin token and a fork or local profile.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from web3 import Web3

from afterhours.bot.allocator import deployed_tiers
from afterhours.bot.vault_state import read_state
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import AfterhoursConfig, load_config
from afterhours.data.pipeline import make_cache
from afterhours.deployments import load_deployment
from afterhours.explain.reason import canonical
from afterhours.explain.verify import verify_card
from afterhours.numbers import oracle_summary
from afterhours.policy.option_b import allowed_tiers, decide, live_ratings
from afterhours.policy.option_b import reason as b_reason
from afterhours.public_config import public_config
from afterhours.risk.live import LiveRisk, session_state, upcoming_periods
from afterhours.state import Store

log = logging.getLogger(__name__)

# Shared-store key for the last risk board, so a restarted process can show it at once.
BOARD_SNAPSHOT = "live_board"


def process_info(started: float) -> dict[str, Any]:
    """Uptime and memory for /v1/health: a restart shows as a small uptime, memory near the
    host's limit shows before it is hit (Render free has 512 MB)."""
    import resource
    import sys

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = peak / 2**20 if sys.platform == "darwin" else peak / 2**10  # bytes vs KiB
    rss_mb: float | None = None
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss_mb = int(line.split()[1]) / 2**10
    except OSError:
        pass  # not Linux
    return {
        "uptime_seconds": round(time.time() - started),
        "rss_mb": None if rss_mb is None else round(rss_mb),
        "peak_rss_mb": round(peak_mb),
        "threads": threading.active_count(),
    }


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
        self._mainnet: Any = None
        self._mainnet_lock = threading.Lock()
        self._examples: tuple[float, list[str]] | None = None
        self._chain: tuple[float, dict[str, Any]] | None = None
        self.started = time.time()

    def mainnet(self) -> Any:
        """The read-only mainnet client for the live views (created once, on first use).

        Locked: a burst of visitors on a fresh process must not build one client each, since
        each would start its own full board refresh (that ran a small host out of memory).
        The client starts from the last board saved in the shared store, so a restarted process
        shows it (with its own read time) instead of "still reading".
        """
        if self._mainnet is None:
            with self._mainnet_lock:
                if self._mainnet is None:
                    from afterhours.live.mainnet import Mainnet

                    m = Mainnet(self.cfg)
                    m.restore_board(self.store.read(BOARD_SNAPSHOT))
                    m.on_board = self._save_board
                    m.shared = self.store
                    self._mainnet = m
        return self._mainnet

    def _save_board(self, doc: dict[str, Any]) -> None:
        saved = self.store.read(BOARD_SNAPSHOT)
        every = self.cfg.live.board_snapshot_minutes * 60
        if saved and time.time() - float(saved.get("saved_at", 0)) < every:
            return
        try:
            self.store.write(BOARD_SNAPSHOT, {"saved_at": time.time(), "board": doc})
        except Exception as exc:  # the shared store is a convenience; the board still serves
            log.warning("saving the board snapshot failed: %s", exc)

    def chain_health(self) -> dict[str, Any]:
        """Chain id and head for /v1/health, cached so health checks stay cheap and fast."""
        cached = self._chain
        if cached and time.time() - cached[0] < self.cfg.api.health_chain_cache_seconds:
            return cached[1]
        try:
            w3 = self.w3()
            info: dict[str, Any] = {
                "reachable": True,
                "chain_id": int(w3.eth.chain_id),
                "block": int(w3.eth.block_number),
            }
        except Exception:
            info = {"reachable": False}
        self._chain = (time.time(), info)
        return info

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


def _optional_json(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text()) if path.exists() else None


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
    warm_on_start: list[Any] = []

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        for fn in warm_on_start:
            threading.Thread(target=fn, daemon=True).start()
        yield

    app = FastAPI(
        title="Afterhours API",
        version="1",
        description=(
            "Read-only. Live Stock Token risk on Robinhood Chain mainnet (`/v1/live`, "
            "`/v1/agent`), and the Afterhours vault (a simulation on its local chain, a "
            "testnet deployment when hosted). Nothing here signs or sends a transaction. "
            "Not financial advice."
        ),
        lifespan=lifespan,
    )
    origins = [o.strip() for o in (cfg.env(cfg.api.cors_origins_env) or "").split(",") if o.strip()]
    if not origins:
        ports = [p for p in (cfg.env(e) for e in cfg.api.web_port_envs) if p]
        origins = [t.format(port=p) for p in ports for t in cfg.api.local_web_origin_templates]
        # On a host this means every browser call from the web app will be refused.
        log.warning(
            "%s is not set: only local web origins may call this API (%s)",
            cfg.api.cors_origins_env,
            ", ".join(origins),
        )
    else:
        log.info("CORS origins: %s", ", ".join(origins))
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

    # HEAD too: uptime monitors often probe with HEAD.
    @app.api_route("/v1/health", methods=["GET", "HEAD"])
    def health() -> dict[str, Any]:
        chain: dict[str, Any] = {
            "profile": cfg.active_profile,
            "clock": "chain" if ctx.chain_clock else "wall",
        }
        chain |= ctx.chain_health()
        plan = ctx.store.read("plan")
        prod = ctx.risk.production
        return {
            "service": "ok",
            "process": process_info(ctx.started),
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
        tiers = deployed_tiers(d) if d else []
        symbols = list(dict.fromkeys(m["symbol"] for m in d.get("markets", []))) if d else []
        pol = cfg.policy
        fm = cfg.backtest.option_a.fixed_map
        ratings = live_ratings(
            {s: ctx.risk.cache.get(f"prices/{s}", allow_stale=True) for s in symbols},
            now.year,
            fm.window_days,
            fm.quantile,
            fm.min_observations,
        )
        out = []
        for s in symbols:
            fs = ctx.risk.forecast(s, now, pol.lookahead_closed_periods)
            worst = max(fs, key=lambda f: f.bad_case_drop)
            dec = decide(
                s,
                ratings.get(s),
                now.year,
                worst.bad_case_drop,
                tiers,
                pol.map_fraction,
                pol.pullback_fraction,
            )
            text = b_reason(dec, tiers, pol.map_fraction, pol.lookahead_closed_periods)
            ok = allowed_tiers(dec, tiers, pol.map_fraction)
            out.append(
                {
                    "symbol": s,
                    "next": fs[0].to_json(),
                    "worst_in_lookahead": worst.to_json(),
                    "tiers": {t.name: {"allowed": ok[t.name], "reason": text} for t in tiers},
                    "policy": {
                        "rating": dec.rating,
                        "rating_year": dec.rating_year,
                        "mapped_tier": dec.mapped_tier,
                        "pull_limit": dec.pull_limit,
                        "pulled": dec.pulled,
                        "reason": text,
                    },
                }
            )
        return {
            "now": now.isoformat(),
            "policy": "option_b",
            "lookahead_closed_periods": pol.lookahead_closed_periods,
            "map_fraction": pol.map_fraction,
            "pullback_fraction": pol.pullback_fraction,
            "tier_limits": {
                t.name: {
                    "lltv": t.lltv,
                    "cushion": t.cushion,
                    "map_limit": t.cushion * (1 - pol.map_fraction),
                }
                for t in tiers
            },
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
        study = ctx.artifact("discovery", "oracle_study.json")
        activity = ctx.artifact("backtest", "option_b_activity.json")["universes"]
        market = ctx.artifact("discovery", "market_size.json")
        a_doc = ctx.artifact("backtest", "option_a.json")
        b_doc = ctx.artifact("backtest", "option_b.json")
        numbers = ctx.artifact("report", "numbers.json")["numbers"]

        def point(r: dict[str, Any]) -> dict[str, float]:
            return {
                "yield": r["net_lender_yield_annualised"],
                "worst": float((r.get("worst_event") or {}).get("share_of_vault", 0.0)),
                "bad_debt": r["bad_debt_usdg"],
                "interest": r["interest_usdg"],
            }

        def universe(u: str) -> dict[str, Any]:
            au, bu = a_doc["universes"][u], b_doc["universes"][u]
            return {
                "stocks": len(au["tickers"]),
                "evaluation": au["periods"]["evaluation"],
                "b": point(bu["evaluation"]) | {"share_of_time": bu["evaluation"]["share_of_time"]},
                "b_chosen": bu["chosen"],
                "b_met_cap_on_tuning": bu["met_cap_on_tuning"],
                "b_tuning_worst": float(
                    (bu["tuning_result"].get("worst_event") or {}).get("share_of_vault", 0.0)
                ),
                "b_settings_meeting_cap": bu["settings_meeting_cap_on_tuning"],
                "b_settings": bu["settings"],
                "fixed_map_tuning_smallest_worst": min(
                    x["worst_event_share"] for x in au["grid"]["tuning"] if x["kind"] == "fixed_map"
                ),
                "fixed_map": point(au["evaluation"]["fixed_map"]),
                "dynamic": point(au["evaluation"]["afterhours"]),
                "nearest_blend": point(bu["compare_on_evaluation"]["nearest_blend"])
                | {"w": bu["compare_on_evaluation"]["nearest_blend"]["w"]},
                "blends": [point(x) | {"w": x["w"]} for x in au["blends"]["evaluation"]],
                "pulls": {
                    "per_year": activity[u]["per_year"],
                    "total": activity[u]["total"],
                    "by_symbol": activity[u]["by_symbol"],
                },
            }

        return {
            "decision": {
                "rule": numbers["verdict.rule"]["text"],
                "result": numbers["verdict.result"]["text"],
                "tuning_years": numbers["option_a.tuning_years"]["text"],
                "evaluation_years": numbers["option_a.evaluation_years"]["text"],
                "cap": cfg.backtest.max_worst_event_share,
                "label": b_doc["label"],
                "second_evaluation_note": b_doc["note"],
                "universes": {u: universe(u) for u in ("vault", "stock_tokens")},
                "market_now": {
                    "block": market["block"],
                    "block_time": market["block_time"],
                    "markets": market["stock_token_markets"],
                    "usdg_supplied": market["usdg_loan"]["supplied"],
                    "usdg_borrowed": market["usdg_loan"]["borrowed"],
                    "supply_apy": market["rates"]["usdg_supply_apy_supply_weighted"],
                    "borrow_apy": market["rates"]["usdg_borrow_apy_borrow_weighted"],
                    "utilization": market["rates"]["usdg_utilization"],
                },
                "assumed_apy": {
                    name: cfg.backtest.apy(lltv) for name, lltv in cfg.morpho.lltv_tiers.ordered()
                },
            },
            "oracle": {k: v for k, v in oracle_summary(study).items() if k != "updates"},
            # Dated readings since M1 (make oracle-reading); None until the first one exists.
            "oracle_readings": _optional_json(
                cfg.path(cfg.paths.artifacts_dir) / "discovery" / "oracle_readings" / "index.json"
            ),
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

    # ---------------------------------------------------------------- live mainnet (read-only)
    def _live(fn: Any) -> Any:
        from afterhours.live.mainnet import WarmingError

        try:
            return fn()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except WarmingError as exc:
            wait = str(cfg.live.board_cache_seconds)
            raise HTTPException(503, str(exc), headers={"Retry-After": wait}) from exc
        except TimeoutError as exc:
            log.warning("live read out of time budget: %s", exc)
            raise HTTPException(
                503, "Robinhood Chain is answering slowly right now. Try again in a minute."
            ) from exc
        except Exception as exc:  # RPC down, rate limited, ...
            log.warning("live read failed: %s", exc)
            raise HTTPException(503, "Can't reach Robinhood Chain right now.") from exc

    @app.get("/v1/live/board")
    def live_board() -> dict[str, Any]:
        return cast(dict[str, Any], _live(lambda: ctx.mainnet().board()))

    def regimes_doc() -> dict[str, Any]:
        from afterhours.live.mainnet import WarmingError

        board = cast(dict[str, Any], ctx.mainnet().board())
        rows = [r for r in board["stocks"] if r.get("regime")]
        if not rows or "regimes" not in board:  # a board saved before the monitor existed
            raise WarmingError("Still reading every Stock Token price feed on mainnet.")
        return {
            "network": board["network"],
            "block": board["block"],
            "as_of": board["as_of"],
            **board["regimes"],
            "tokens": [
                {"symbol": r["symbol"], "feed_price": r["price"], **r["regime"]} for r in rows
            ],
        }

    @app.get("/v1/live/regimes")
    def live_regimes() -> dict[str, Any]:
        """Price regime, quality score and one plain line per Stock Token (docs/REGIME.md)."""
        return cast(dict[str, Any], _live(regimes_doc))

    # ---------------------------------------------------------------- agents (docs/AGENTS.md)
    from afterhours import agents

    limiter = agents.RateLimiter(
        cfg.agents.rate_limit_per_minute,
        cfg.agents.rate_limit_burst,
        cfg.agents.max_tracked_clients,
    )

    @app.middleware("http")
    async def agent_rate_limit(request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/v1/agent/"):
            client = agents.client_address(
                request.headers.get("x-forwarded-for"),
                request.client.host if request.client else None,
                cfg.agents.trusted_proxy_hops,
            )
            wait = limiter.take(client)
            if wait > 0:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    {"detail": "Too many requests. Slow down and retry after the given seconds."},
                    status_code=429,
                    headers={"Retry-After": str(max(1, round(wait)))},
                )
        return await call_next(request)

    tag: list[str | Enum] = ["agents"]

    @app.get("/v1/agent/market-status", tags=tag, response_model=agents.MarketStatus)
    def agent_market_status() -> dict[str, Any]:
        """Session state, next open and close, where feeds stand, regime counts."""
        try:  # the regime summary is a bonus: the exchange clock alone still answers
            regimes = cast(dict[str, Any], ctx.mainnet().board()).get("regimes")
        except Exception:
            regimes = None
        return agents.market_status(status(), regimes)

    @app.get("/v1/agent/weekend-risk/{ticker}", tags=tag, response_model=agents.WeekendRisk)
    def agent_weekend_risk(ticker: str) -> dict[str, Any]:
        """One Stock Token: regime, price quality, next closed period, bad case, summary."""
        board = cast(dict[str, Any], _live(lambda: ctx.mainnet().board()))
        try:
            return agents.weekend_risk(board, ticker)
        except KeyError as exc:
            known = ", ".join(sorted(r["symbol"] for r in board["stocks"]))
            raise HTTPException(404, f"No Stock Token {ticker!r}. Known: {known}.") from exc

    @app.get("/v1/agent/positions/{address}", tags=tag, response_model=agents.PositionCheck)
    def agent_positions(address: str) -> dict[str, Any]:
        """Every Stock Token Morpho loan of an address, against tonight's bad case."""
        return agents.position_check(
            cast(dict[str, Any], _live(lambda: ctx.mainnet().positions(address)))
        )

    @app.get("/v1/agents/example-session", tags=tag)
    def agent_example_session() -> dict[str, Any]:
        """A captured session of real tool calls and answers, for the Agents page."""
        path = cfg.path(cfg.paths.artifacts_dir) / "agents" / "example-session.json"
        return _read_json(str(path), path.stat().st_mtime if path.exists() else 0.0)

    @app.get("/v1/agent/moves/{reason_id}", tags=tag, response_model=agents.MoveExplanation)
    def agent_move(reason_id: str) -> dict[str, Any]:
        """A reason card from the vault's ledger and its onchain verification."""
        doc = reason(reason_id)
        return agents.explain_move(doc["card"], doc["canonical_json"], doc["verification"])

    @app.get("/v1/live/positions/{address}")
    def live_positions(address: str) -> dict[str, Any]:
        return cast(dict[str, Any], _live(lambda: ctx.mainnet().positions(address)))

    examples_lock = threading.Lock()

    def refresh_examples(wait: bool = True) -> list[str]:
        """Borrower examples, rescanned at most every `live.market_refresh_minutes`.

        One scan at a time: while one runs, callers that do not wait get what is cached (or
        nothing), so a burst of visitors never starts a burst of scans.
        """
        ttl = cfg.live.market_refresh_minutes * 60
        cached = ctx._examples
        if cached is not None and time.time() - cached[0] <= ttl:
            return cached[1]
        if not examples_lock.acquire(blocking=wait):
            return cached[1] if cached else []
        try:
            cached = ctx._examples
            if cached is None or time.time() - cached[0] > ttl:
                cached = (time.time(), cast(list[str], ctx.mainnet().examples()))
                ctx._examples = cached
            return cached[1]
        finally:
            examples_lock.release()

    def warm() -> None:
        # In this process, not a second one, so a small host's memory holds: prices for every
        # Stock Token (the forecasts need them), then the market registry and board, then the
        # first borrower scan (every Borrow event), all before a visitor asks.
        if cfg.live.warm_prices:
            from afterhours.data.pipeline import fetch_symbols
            from afterhours.data.universe import stock_token_tickers

            try:
                fetch_symbols(cfg, stock_token_tickers(cfg, cfg.live.discovery_profile)[0])
            except Exception as exc:
                log.warning("warming prices failed, using what is cached: %s", exc)
        for name, fn in (
            ("board", lambda: ctx.mainnet().board(wait=True)),
            ("examples", refresh_examples),
        ):
            try:
                fn()
            except Exception as exc:
                log.warning("warming the live %s failed: %s", name, exc)

    warm_on_start.append(warm)

    @app.get("/v1/live/examples")
    def live_examples() -> dict[str, Any]:
        return {"addresses": cast(list[str], _live(lambda: refresh_examples(wait=False)))}

    # ---------------------------------------------------------------- Telegram webhook
    @app.post(cfg.alerts.webhook_path, include_in_schema=False)
    def telegram_webhook(
        request: Request, update: Annotated[dict[str, Any], Body()]
    ) -> dict[str, Any]:
        """Commands from Telegram (setWebhook). Needs the bot token and the webhook secret."""
        from afterhours.live.alerts import Store as Subscriptions
        from afterhours.live.alerts import handle_update, telegram_from_config

        secret = cfg.env(cfg.alerts.webhook_secret_env)
        if not secret or not cfg.env(cfg.alerts.token_env):
            raise HTTPException(404, "Telegram webhook is not configured.")
        sent = request.headers.get(cfg.alerts.webhook_secret_header) or ""
        if not secrets.compare_digest(sent.encode(), secret.encode()):
            raise HTTPException(403, "Bad secret.")
        live = cfg.profiles[cfg.live.profile]
        try:
            answer = handle_update(
                Subscriptions.from_config(cfg),
                update,
                set(ctx.mainnet().feeds),
                cfg.chains[live.chain].name,
                cfg.alerts.max_watches_per_chat,
            )
            if answer:
                telegram_from_config(cfg).send(*answer)
        except Exception as exc:
            # Answer 200 anyway: Telegram retries non-2xx replies, and a retry cannot fix this.
            log.warning("telegram update failed: %s", exc)
        return {"ok": True}

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
            offset = 0 if replay else ctx.store.events_end()
            poll = ctx.store.poll_seconds
            quiet = 0.0
            while True:
                batch, offset = ctx.store.events_since(offset)
                for e in batch:
                    yield {"event": e["type"], "data": json.dumps(e["data"], default=str)}
                    quiet = 0.0
                await asyncio.sleep(poll)
                quiet += poll
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
