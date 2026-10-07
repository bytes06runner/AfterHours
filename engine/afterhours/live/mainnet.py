"""Read-only views of Robinhood Chain mainnet for real users: the risk board, the position
checker and the alert bot. Nothing here signs, sends or holds anything.

Sources for every call (read 2026-09-27):
- Morpho Blue `IMorpho.sol`: `market(Id)` (six uint128), `position(Id, address)` returns
  (uint256 supplyShares, uint128 borrowShares, uint128 collateral), `idToMarketParams`.
- Morpho Blue `SharesMathLib.sol`: assets = shares x (totalAssets + 1) / (totalShares + 1e6),
  rounded up for borrows and down for supply.
- Morpho Blue `EventsLib.sol`: `CreateMarket(Id indexed id, MarketParams)`,
  `Borrow(Id indexed id, address caller, address indexed onBehalf, address indexed receiver,
  uint256 assets, uint256 shares)`.
- Morpho Blue `IOracle.sol`: `price()` is one collateral asset in loan assets, scaled by 1e36.
- Chainlink `latestRoundData()` returns (roundId, answer, startedAt, updatedAt, answeredInRound).
- Addresses (Morpho Blue, USDG, the 35 Stock Tokens and their feeds): M1 discovery,
  `deployments/fork.discovered.json`, each verified onchain.
"""

from __future__ import annotations

import contextlib
import ctypes
import gc
import json
import logging
import math
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from eth_utils import is_address, to_checksum_address
from web3 import Web3

from afterhours.chain.abi import get_logs
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import AfterhoursConfig
from afterhours.data.pipeline import make_cache
from afterhours.deployments import load_discovered
from afterhours.discovery.pools import Pool, measure_depth
from afterhours.live import regime as rg
from afterhours.logsafe import redact
from afterhours.policy.lp import tier_spec
from afterhours.risk.live import LiveRisk

log = logging.getLogger(__name__)

CREATE_MARKET = (
    "CreateMarket(bytes32 indexed id,(address,address,address,address,uint256) marketParams)"
)
BORROW = (
    "Borrow(bytes32 indexed id,address caller,address indexed onBehalf,address indexed receiver,"
    "uint256 assets,uint256 shares)"
)
MARKET = "market(bytes32)(uint128,uint128,uint128,uint128,uint128,uint128)"
POSITION = "position(bytes32,address)(uint256,uint128,uint128)"
LATEST_ROUND = "latestRoundData()(uint80,int256,uint256,uint256,uint80)"
VIRTUAL_SHARES = 10**6
VIRTUAL_ASSETS = 1


def to_assets(shares: int, total_assets: int, total_shares: int, *, up: bool) -> int:
    """Morpho SharesMathLib toAssetsUp / toAssetsDown."""
    num = shares * (total_assets + VIRTUAL_ASSETS)
    den = total_shares + VIRTUAL_SHARES
    return -(-num // den) if up else num // den


@dataclass(frozen=True)
class Market:
    id: str
    symbol: str
    loan_token: str
    collateral: str
    oracle: str
    irm: str
    lltv: float


def frozen_window_start(cfg: AfterhoursConfig, now: datetime) -> datetime:
    """Start of the most recent weekend window (Friday 20:00 New York in the M1 study)."""
    fw = cfg.live.frozen_window
    tz = ZoneInfo(fw.timezone)
    local = now.astimezone(tz)
    hh, mm = (int(x) for x in fw.start_time.split(":"))
    days_back = (local.weekday() - fw.start_weekday) % 7
    start = (local - timedelta(days=days_back)).replace(hour=hh, minute=mm, second=0, microsecond=0)
    if start > local:
        start -= timedelta(days=7)
    return start


def feed_status(cfg: AfterhoursConfig, now: datetime, updated_at: datetime) -> dict[str, Any]:
    """Frozen (inside the weekend window), quiet (no update for a while) or updating."""
    start = frozen_window_start(cfg, now)
    end = start + timedelta(hours=cfg.live.frozen_window.hours)
    age = (now - updated_at).total_seconds()
    if start <= now < end:
        state = "frozen"
    elif age > cfg.live.quiet_after_minutes * 60:
        state = "quiet"
    else:
        state = "updating"
    return {
        "state": state,
        "age_seconds": age,
        "window_start": start.astimezone(UTC).isoformat(),
        "window_end": end.astimezone(UTC).isoformat(),
    }


# Uniswap reads for the regime monitor, verified on Robinhood Chain mainnet on 2026-10-04 with
# cast against the NVDA/USDG pools (docs/REGIME.md): v3 `slot0()` on the pool, v4
# `StateView.getSlot0(poolId)`; both start with sqrtPriceX96.
V3_SLOT0 = "slot0()(uint160,int24,uint16,uint16,uint16,uint8,bool)"
V4_GET_SLOT0 = "getSlot0(bytes32)(uint160,int24,uint24,uint24)"
Q96 = 2**96  # Uniswap's sqrtPriceX96 fixed point


def pool_price(
    sqrt_price_x96: int, token: str, quote: str, token_dec: int, quote_dec: int
) -> float:
    """Price of `token` in `quote` from a pool's sqrtPriceX96 (currency0 is the lower address)."""
    ratio = (sqrt_price_x96 / Q96) ** 2  # raw currency1 per raw currency0
    scale = 10.0 ** (token_dec - quote_dec)
    if token.lower() < quote.lower():  # token is currency0
        return float(ratio * scale)
    return float(scale / ratio)


def lower_thread_priority(nice: int) -> None:
    """Run this thread at a lower CPU priority (Linux sets niceness per thread).

    On a host with a fraction of a CPU, a board refresh then cannot starve request handling
    and health checks. Elsewhere, or without permission, nothing changes.
    """
    if nice <= 0 or not sys.platform.startswith("linux"):
        return
    with contextlib.suppress(OSError):
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), nice)


def release_free_memory() -> None:
    """Hand freed heap back to the OS after a large read (glibc keeps it otherwise)."""
    gc.collect()
    if sys.platform.startswith("linux"):
        with contextlib.suppress(OSError, AttributeError):
            ctypes.CDLL("libc.so.6").malloc_trim(0)


class WarmingError(RuntimeError):
    """The first risk board is still being read; the API answers "still reading"."""


class Mainnet:
    """One read-only client for the live views (thread-safe caches, lazy RPC)."""

    def __init__(self, cfg: AfterhoursConfig) -> None:
        self.cfg = cfg
        self.w3: Web3 = connect(
            cfg.rpc_url(cfg.live.profile),
            timeout=cfg.live.rpc_timeout_seconds,
            retries=cfg.live.rpc_retries,
        )
        public = cfg.chains[cfg.profiles[cfg.live.profile].chain].public_rpc_url
        # The chain's public RPC as a second client when the primary is another endpoint: log
        # scans need its wide block ranges (live.logs_from_public_rpc), and DEX reads fall back
        # to it when the primary fails them.
        self.w3_public: Web3 | None = (
            connect(public, timeout=cfg.live.rpc_timeout_seconds, retries=cfg.live.rpc_retries)
            if public and public != cfg.rpc_url(cfg.live.profile)
            else None
        )
        self.w3_logs: Web3 = (
            self.w3_public if cfg.live.logs_from_public_rpc and self.w3_public else self.w3
        )
        disc = load_discovered(cfg, cfg.live.discovery_profile)
        self.blue = to_checksum_address(disc["core"]["morpho_blue"]["address"])
        self.usdg = to_checksum_address(disc["core"]["usdg"]["address"])
        self.tokens = {
            to_checksum_address(v["address"]): sym for sym, v in disc["stock_tokens"].items()
        }
        self.feeds = {
            sym: to_checksum_address(v["feed"]["address"])
            for sym, v in disc["stock_tokens"].items()
            if v.get("feed")
        }
        self.risk = LiveRisk(cfg, make_cache(cfg))
        # Price regime monitor: the deepest USDG pools per token (depth measured at discovery),
        # the Uniswap contracts to read them with, and each feed's typical update interval.
        core = disc["core"]
        self.v3_quoter = to_checksum_address(core["uniswap_v3_quoter_v2"]["address"])
        self.v4_quoter = to_checksum_address(core["uniswap_v4_quoter"]["address"])
        self.state_view = to_checksum_address(core["uniswap_v4_state_view"]["address"])
        self.pools: dict[str, list[Pool]] = {}
        for sym, v in disc["stock_tokens"].items():
            usdg_pools = [p for p in v.get("pools", []) if p["quote"].lower() == self.usdg.lower()]
            usdg_pools.sort(key=lambda p: p.get("depth_usd") or 0, reverse=True)
            self.pools[sym] = [
                Pool(
                    version=p["version"],
                    address_or_id=p["address_or_id"],
                    token=to_checksum_address(p["token"]),
                    quote=to_checksum_address(p["quote"]),
                    quote_symbol=p["quote_symbol"],
                    fee=int(p["fee"]),
                    tick_spacing=p.get("tick_spacing"),
                    hooks=p.get("hooks"),
                )
                for p in usdg_pools[: cfg.regime.pools_per_token]
            ]
        cadence_file = cfg.path(cfg.paths.artifacts_dir) / "regime" / "cadence.json"
        self.cadence: dict[str, Any] | None = (
            json.loads(cadence_file.read_text()) if cadence_file.exists() else None
        )
        self._depth: tuple[float, dict[str, float]] | None = None
        self._lock = threading.Lock()
        self._board_lock = threading.Lock()
        self._board: tuple[float, dict[str, Any]] | None = None
        self.on_board: Callable[[dict[str, Any]], None] | None = None  # e.g. save a snapshot
        # A store shared across restarts (the API's), for the scan files: a free host's disk is
        # wiped on every restart, and rescanning every event from block 0 takes many minutes.
        self.shared: Any = None
        self._decimals: dict[str, int] = {}
        self._symbols: dict[str, str | None] = {}
        self.store = cfg.path(cfg.paths.state_dir) / "live-markets.json"
        self.borrowers = cfg.path(cfg.paths.state_dir) / "live-borrowers.json"
        # Curator view: Morpho's enabled LLTVs (M1 discovery) and borrowers per market.
        self.enabled_lltvs: list[float] = [
            float(x) for x in disc.get("lltvs", {}).get("values", [])
        ]
        self.borrowers_by_market = cfg.path(cfg.paths.state_dir) / "live-borrowers-by-market.json"
        self._curator: tuple[float, dict[str, Any]] | None = None
        self._curator_lock = threading.Lock()
        self._scan_lock = threading.Lock()

    # ------------------------------------------------------------------ chain helpers
    def deadline(self) -> float:
        """The time budget for one live read (`live.refresh_budget_seconds`)."""
        return time.monotonic() + self.cfg.live.refresh_budget_seconds

    def block(self) -> int:
        return int(self.w3.eth.block_number) - self.cfg.live.lag_blocks

    def decimals(
        self,
        tokens: list[str],
        block: int,
        deadline: float | None = None,
        w3: Web3 | None = None,
    ) -> dict[str, int]:
        missing = [t for t in tokens if t not in self._decimals]
        if missing:
            calls = [Call(t, "decimals()(uint8)") for t in missing]
            vals = call_many(w3 or self.w3, calls, block=block, deadline=deadline)
            for t, v in zip(missing, vals, strict=True):
                self._decimals[t] = int(v) if v is not None else 18
        return {t: self._decimals[t] for t in tokens}

    def symbols(
        self, tokens: list[str], block: int, deadline: float | None = None
    ) -> dict[str, str | None]:
        """Each token's own `symbol()`, read onchain (None if the token has none)."""
        missing = [t for t in tokens if t not in self._symbols]
        if missing:
            calls = [Call(t, "symbol()(string)") for t in missing]
            vals = call_many(self.w3, calls, block=block, deadline=deadline)
            for t, v in zip(missing, vals, strict=True):
                self._symbols[t] = str(v) if v else None
        return {t: self._symbols[t] for t in tokens}

    # ------------------------------------------------------------------ market registry
    def markets(self) -> list[Market]:
        """Every Morpho market with a Stock Token as collateral, from CreateMarket events.

        While another thread rescans, callers use the registry already on disk instead of
        waiting; only the very first scan (no registry yet) is waited for.
        """
        saved = self._read_registry()
        if not self._lock.acquire(blocking=saved is None):
            return [Market(**m) for m in saved["markets"]] if saved else []
        try:
            doc = self._read_registry()
            limit = self.cfg.live.market_refresh_minutes * 60
            if doc is None or time.time() - doc["scanned_at"] >= limit:
                doc = self._scan(doc)
            return [Market(**m) for m in doc["markets"]]
        finally:
            self._lock.release()

    def _read_registry(self) -> dict[str, Any] | None:
        return self._load(self.store, "live_markets")

    def _load(self, path: Path, key: str) -> dict[str, Any] | None:
        """A scan file from disk, else the copy in the shared store (written back to disk)."""
        if path.exists():
            doc: dict[str, Any] = json.loads(path.read_text())
            return doc
        if self.shared is None:
            return None
        try:
            saved = self.shared.read(key)
        except Exception as exc:
            log.warning("reading %s from the shared store failed: %s", key, exc)
            return None
        if saved:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(saved))
        return cast(dict[str, Any] | None, saved)

    def _save(self, path: Path, key: str, doc: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc))
        if self.shared is not None:
            try:
                self.shared.write(key, doc)
            except Exception as exc:  # the disk copy still serves this process
                log.warning("saving %s to the shared store failed: %s", key, exc)

    def _scan(self, doc: dict[str, Any] | None) -> dict[str, Any]:
        head = self.block()
        start = (doc["last_block"] + 1) if doc else 0
        markets = list(doc["markets"]) if doc else []
        if start <= head:
            span = self.cfg.discovery.oracle_study.max_log_block_range * 20
            for ev in get_logs(
                self.w3_logs, CREATE_MARKET, [self.blue], start, head, max_range=span
            ):
                loan, collateral, oracle, irm, lltv = ev["marketParams"]
                collateral = to_checksum_address(collateral)
                if collateral in self.tokens:
                    markets.append(
                        {
                            "id": "0x" + bytes(ev["id"]).hex(),
                            "symbol": self.tokens[collateral],
                            "loan_token": to_checksum_address(loan),
                            "collateral": collateral,
                            "oracle": to_checksum_address(oracle),
                            "irm": to_checksum_address(irm),
                            "lltv": lltv / 1e18,
                        }
                    )
        out = {"last_block": head, "scanned_at": time.time(), "markets": markets}
        self._save(self.store, "live_markets", out)
        return out

    # ------------------------------------------------------------------ forecasts
    def tonight(self, symbol: str, now: datetime) -> dict[str, Any] | None:
        """The forecast for the closed period in progress or the next one."""
        try:
            f = self.risk.forecast(symbol, now, 1)[0]
        except (KeyError, IndexError, ValueError) as exc:
            log.warning("no forecast for %s: %s", symbol, exc)
            return None
        if not math.isfinite(f.bad_case_drop):
            return None
        out = f.to_json()
        cov = self.risk.coverage
        out["held_out_miss_rate"] = cov["miss_rate"].get(f.period.segment)
        out["held_out_years"] = cov["test_years"]
        return out

    # ------------------------------------------------------------------ risk board
    def board(self, now: datetime | None = None, *, wait: bool = False) -> dict[str, Any]:
        """The risk board, never making a visitor wait behind a slow refresh.

        A fresh board comes from the cache. A stale one is returned at once while one background
        refresh runs. With no board yet, `WarmingError` is raised (the API answers "still reading")
        unless `wait` is set (the startup warm-up and scheduled jobs wait).
        """
        cached = self._board
        if cached and time.time() - cached[0] < self.cfg.live.board_cache_seconds:
            return cached[1]
        if wait:
            with self._board_lock:
                return self._refresh_board(now)
        if self._board_lock.acquire(blocking=False):
            threading.Thread(target=self._refresh_in_background, args=(now,), daemon=True).start()
        if cached:
            return cached[1]
        raise WarmingError("Still reading every Stock Token price feed on mainnet.")

    def restore_board(self, snapshot: dict[str, Any] | None) -> None:
        """Start from a saved board (`{"board": ..., "saved_at": ...}`), treated as stale.

        Visitors see it, with its own block and read time, while the first refresh runs.
        """
        if self._board is None and snapshot and isinstance(snapshot.get("board"), dict):
            self._board = (0.0, snapshot["board"])

    def _refresh_in_background(self, now: datetime | None) -> None:
        lower_thread_priority(self.cfg.live.refresh_nice)
        try:
            self._refresh_board(now)
        except Exception as exc:  # the last board stays; the next request tries again
            log.warning("board refresh failed: %s", exc)
        finally:
            self._board_lock.release()
            release_free_memory()

    def _refresh_board(self, now: datetime | None) -> dict[str, Any]:
        cached = self._board
        if cached and time.time() - cached[0] < self.cfg.live.board_cache_seconds:
            return cached[1]
        doc = self._board_now(now or datetime.now(UTC))
        self._board = (time.time(), doc)
        if self.on_board:
            self.on_board(doc)
        return doc

    # ------------------------------------------------------------------ price regime monitor
    def dex_prices(
        self,
        syms: list[str],
        block: int,
        deadline: float | None = None,
        w3: Web3 | None = None,
    ) -> dict[str, float | None]:
        """Mid price in USDG of each token's deepest USDG pool that answers (v3 or v4).

        Raises if the read fails (any RPC error other than a revert); a token whose pools all
        revert or hold no price gets None.
        """
        client = w3 or self.w3
        calls: list[Call] = []
        owners: list[tuple[str, Pool]] = []
        for s in syms:
            for p in self.pools.get(s, []):
                if p.version == "v3":
                    calls.append(Call(p.address_or_id, V3_SLOT0))
                else:
                    calls.append(
                        Call(self.state_view, V4_GET_SLOT0, (bytes.fromhex(p.address_or_id[2:]),))
                    )
                owners.append((s, p))
        dec = self.decimals(
            sorted({p.token for _, p in owners} | {self.usdg}), block, deadline, client
        )
        res = call_many(client, calls, block=block, deadline=deadline) if calls else []
        out: dict[str, float | None] = {s: None for s in syms}
        for (s, p), r in zip(owners, res, strict=True):
            if out[s] is not None or not r or not int(r[0]):
                continue
            out[s] = pool_price(int(r[0]), p.token, self.usdg, dec[p.token], dec[self.usdg])
        return out

    def dex_depth(
        self,
        prices: dict[str, float | None],
        block: int,
        deadline: float | None = None,
        w3: Web3 | None = None,
    ) -> dict[str, float]:
        """USD sellable within `vault.max_slippage` across each token's pools (re-quoted at most
        every `regime.depth_refresh_minutes`)."""
        cached = self._depth
        if cached and time.time() - cached[0] < self.cfg.regime.depth_refresh_minutes * 60:
            return cached[1]
        pools = [
            Pool(**{**p.to_json(), "probes": [], "depth_usd": 0.0})
            for s, price in prices.items()
            if price
            for p in self.pools.get(s, [])
        ]
        if not pools:
            return {}
        dec = self.decimals(sorted({p.token for p in pools} | {self.usdg}), block, deadline, w3)
        by_token: dict[str, str] = {str(a): sym for a, sym in self.tokens.items()}
        measure_depth(
            w3 or self.w3,
            pools,
            v3_quoter=self.v3_quoter,
            v4_quoter=self.v4_quoter,
            token_price_usd={p.token: float(prices[by_token[p.token]] or 0) for p in pools},
            quote_price_usd={self.usdg: 1.0},
            token_decimals=dec,
            quote_decimals=dec,
            probes_usd=self.cfg.regime.depth_probes_usd,
            max_slippage=self.cfg.vault.max_slippage,
            block=block,
            deadline=deadline,
        )
        depth: dict[str, float] = {}
        for p in pools:
            sym = by_token[p.token]
            depth[sym] = depth.get(sym, 0.0) + p.depth_usd
        self._depth = (time.time(), depth)
        return depth

    def regimes(
        self,
        rows: list[dict[str, Any]],
        now: datetime,
        block: int,
        deadline: float | None = None,
    ) -> dict[str, Any]:
        """Add `regime` to each board row; return the calendar state and counts."""
        cal_name = self.cfg.data.exchange_calendar
        cal = rg.calendar_state(cal_name, now)
        since = (
            rg.closed_since(cal_name, now, self.cfg.regime.cadence_step_minutes)
            if cal["state"] == "closed"
            else None
        )
        syms = [r["symbol"] for r in rows]
        # DEX reads add marks to the score; regimes come from the calendar and feeds regardless.
        # A failed read is never shown as "no price": each row says why its DEX mark is missing.
        prices: dict[str, float | None] = {}
        depth: dict[str, float] = {}
        dex = self.read_dex(syms, block, deadline)
        prices, client, dex_block = dex.pop("prices"), dex.pop("client"), dex["block"]
        if client is not None:
            try:
                feed = {r["symbol"]: r["price"] for r in rows}
                depth = self.dex_depth(
                    {s: feed[s] for s in syms if prices.get(s)},
                    dex_block,
                    deadline if client is self.w3 else self.deadline(),
                    client,
                )
            except Exception as exc:  # e.g. out of the refresh budget: re-quoted next time
                log.warning("DEX depth failed: %s", type(exc).__name__)
                dex["depth_error"] = redact(f"{type(exc).__name__}: {exc}")[:200]
                # Depth moves slowly: the last good quote, with its age, beats none.
                depth = self._depth[1] if self._depth else {}
        dex["depth_as_of"] = (
            datetime.fromtimestamp(self._depth[0], UTC).isoformat()
            if self._depth and depth
            else None
        )
        counts = dict.fromkeys(rg.REGIMES, 0)
        for r in rows:
            updated = datetime.fromisoformat(r["updated_at"]) if r["updated_at"] else None
            r["regime"] = rg.regime_row(
                self.cfg,
                symbol=r["symbol"],
                now=now,
                cal=cal,
                since=since,
                updated_at=updated,
                feed_price=r["price"],
                dex_price=prices.get(r["symbol"]),
                depth_usd=depth.get(r["symbol"]),
                cadence_doc=self.cadence,
                dex_status=(
                    "no_pool"
                    if not self.pools.get(r["symbol"])
                    else "unavailable"
                    if client is None
                    else "ok"
                    if prices.get(r["symbol"])
                    else "no_price"
                ),
            )
            counts[r["regime"]["regime"]] += 1
        return {
            "calendar": cal["state"],
            "segment": cal["segment"],
            "closed_since": since.isoformat() if since else None,
            "counts": counts,
            "dex": dex,
            "method": "docs/REGIME.md",
        }

    def read_dex(self, syms: list[str], block: int, deadline: float | None) -> dict[str, Any]:
        """DEX prices from the primary RPC, else the chain's public RPC at its own block.

        Returns {"prices", "client", "source", "block", "errors"}; `client` is None and every
        price None when both failed, with the reason for each in `errors`.
        """
        clients: list[tuple[str, Web3]] = [("primary", self.w3)]
        if self.w3_public is not None:
            clients.append(("public", self.w3_public))
        errors: dict[str, str] = {}
        for label, client in clients:
            try:
                b = (
                    block
                    if client is self.w3
                    else int(client.eth.block_number) - self.cfg.live.lag_blocks
                )
                d = deadline if client is self.w3 else self.deadline()
                prices = self.dex_prices(syms, b, d, client)
                return {
                    "prices": prices,
                    "client": client,
                    "source": label,
                    "block": b,
                    "errors": errors,
                }
            except Exception as exc:
                log.warning("DEX prices failed on the %s RPC: %s", label, type(exc).__name__)
                errors[label] = redact(f"{type(exc).__name__}: {exc}")[:200]
        return {
            "prices": dict.fromkeys(syms),
            "client": None,
            "source": None,
            "block": block,
            "errors": errors,
        }

    def _board_now(self, now: datetime) -> dict[str, Any]:
        block = self.block()
        syms = sorted(self.feeds)
        deadline = self.deadline()
        rounds = call_many(
            self.w3,
            [Call(self.feeds[s], LATEST_ROUND) for s in syms],
            block=block,
            deadline=deadline,
        )
        feed_dec = call_many(
            self.w3,
            [Call(self.feeds[s], "decimals()(uint8)") for s in syms],
            block=block,
            deadline=deadline,
        )
        by_symbol: dict[str, list[Market]] = {}
        for m in self.markets():
            if m.loan_token == self.usdg:
                by_symbol.setdefault(m.symbol, []).append(m)
        rows = []
        for s, rnd, dec in zip(syms, rounds, feed_dec, strict=True):
            f = self.tonight(s, now)
            lltvs = sorted({m.lltv for m in by_symbol.get(s, [])}, reverse=True)
            cushions = [
                {"lltv": lv, "cushion": tier_spec("m", lv).cushion} for lv in lltvs if lv > 0
            ]
            row: dict[str, Any] = {
                "symbol": s,
                "feed": self.feeds[s],
                "price": None,
                "updated_at": None,
                "status": None,
                "tonight": f,
                "markets": cushions,
                "breached": [
                    c["lltv"] for c in cushions if f and f["bad_case_drop"] >= c["cushion"]
                ],
            }
            if rnd is not None and dec is not None:
                updated = datetime.fromtimestamp(int(rnd[3]), UTC)
                row["price"] = int(rnd[1]) / 10 ** int(dec)
                row["updated_at"] = updated.isoformat()
                row["status"] = feed_status(self.cfg, now, updated)
            rows.append(row)
        doc = {
            "network": self.cfg.chains[self.cfg.profiles[self.cfg.live.profile].chain].name,
            "block": block,
            "as_of": now.isoformat(),
            # Its own budget: on a slow host the feed reads can use most of theirs.
            "regimes": self.regimes(rows, now, block, self.deadline()),
            "stocks": rows,
        }
        self._board = (time.time(), doc)
        return doc

    # ------------------------------------------------------------------ curator view
    def curator(self, now: datetime | None = None, *, wait: bool = False) -> dict[str, Any]:
        """Per live USDG Morpho market: tonight's bad case against its cushion (live/curator.py).

        Reuses the risk board (forecast, feed state, regime) and adds each market's Morpho state
        and borrower concentration. Cached like the board; raises `WarmingError` while the first
        board is being read.
        """
        cached = self._curator
        if cached and time.time() - cached[0] < self.cfg.live.board_cache_seconds:
            return cached[1]
        board = self.board(now, wait=wait)
        with self._curator_lock:
            cached = self._curator
            if cached and time.time() - cached[0] < self.cfg.live.board_cache_seconds:
                return cached[1]
            doc = self._curator_now(board, wait=wait)
            self._curator = (time.time(), doc)
            return doc

    def _curator_now(self, board: dict[str, Any], *, wait: bool = False) -> dict[str, Any]:
        from afterhours.live import curator as cur

        # Market state at the current head, not the board's block: the board can be a saved
        # snapshot from before a restart, older than a pruned node keeps state for. Forecasts and
        # feed state keep the board's own time (`forecast_as_of`).
        block = self.block()
        deadline = self.deadline()
        markets = [m for m in self.markets() if m.loan_token == self.usdg]
        states = call_many(
            self.w3,
            [Call(self.blue, MARKET, (bytes.fromhex(m.id[2:]),)) for m in markets],
            block=block,
            deadline=deadline,
        )
        unit = 10 ** self.decimals([self.usdg], block, deadline)[self.usdg]
        live: list[tuple[dict[str, Any], tuple[int, ...]]] = []
        for m, st in zip(markets, states, strict=True):
            if st is None:
                continue
            supplied, borrowed = int(st[0]) / unit, int(st[2]) / unit
            if supplied < self.cfg.curator.min_supplied_usdg:
                continue
            row = {
                "id": m.id,
                "symbol": m.symbol,
                "lltv": m.lltv,
                "supplied": supplied,
                "borrowed": borrowed,
            }
            live.append((row, tuple(int(x) for x in st)))
        conc_error = None
        try:  # concentration adds to the view; a rate-limited read must not take it down
            conc, scanned = self.concentration(live, block, deadline, wait=wait)
        except Exception as exc:
            log.warning("borrower concentration failed: %s", type(exc).__name__)
            conc, scanned = {}, None
            conc_error = redact(f"{type(exc).__name__}: {exc}")[:200]
        by_symbol = {r["symbol"]: r for r in board["stocks"]}
        rows = [
            cur.market_row(
                self.cfg, m, by_symbol.get(m["symbol"]), self.enabled_lltvs, conc.get(m["id"])
            )
            for m, _ in live
        ]
        order = list(cur.LABELS)
        rows.sort(key=lambda r: (order.index(r["recommendation"]), -r["borrowed_usdg"]))
        supplied = sum(r["supplied_usdg"] for r in rows)
        borrowed = sum(r["borrowed_usdg"] for r in rows)
        return {
            "network": board["network"],
            "block": block,
            "as_of": datetime.now(UTC).isoformat(),
            "forecast_as_of": board["as_of"],
            "board_block": board["block"],
            "markets": rows,
            "totals": {
                "markets": len(rows),
                "supplied_usdg": supplied,
                "borrowed_usdg": borrowed,
                "utilization": borrowed / supplied if supplied else 0.0,
            },
            "summary": cur.summarize(rows),
            "enabled_lltvs": self.enabled_lltvs,
            "coverage": self.risk.coverage,
            "borrowers_scanned_to_block": scanned,
            "concentration_error": conc_error,
            "policy": {
                "margin_fraction": self.cfg.policy.pullback_fraction,
                "watch_utilization": self.cfg.curator.watch_utilization,
                "concentration_watch_share": self.cfg.curator.concentration_watch_share,
            },
            "method": "engine/afterhours/live/curator.py",
        }

    def concentration(
        self,
        live: list[tuple[dict[str, Any], tuple[int, ...]]],
        block: int,
        deadline: float | None,
        *,
        wait: bool = False,
    ) -> tuple[dict[str, dict[str, Any]], int | None]:
        """Borrowers per market with open debt, and the largest one's share of the debt.

        Borrowers come from Morpho `Borrow` events (`live-borrowers-by-market.json`, scanned
        incrementally in the background; empty until the first scan ends), and each one's debt
        from `position()` borrow shares against the market's total at `block`.
        """
        doc = self._load(self.borrowers_by_market, "live_borrowers_by_market")
        stale = doc is None or time.time() - doc.get("scanned_at", 0) >= (
            self.cfg.live.market_refresh_minutes * 60
        )
        if stale and wait:
            with self._scan_lock:
                doc = self._scan_borrowers(doc)
        elif stale and self._scan_lock.acquire(blocking=False):

            def run(prev: dict[str, Any] | None) -> None:
                try:
                    self._scan_borrowers(prev)
                except Exception as exc:  # the next request tries again
                    log.warning("borrower scan failed: %s", type(exc).__name__)
                finally:
                    self._scan_lock.release()

            threading.Thread(target=run, args=(doc,), daemon=True).start()
        if doc is None:
            return {}, None
        by_market: dict[str, list[str]] = doc["by_market"]
        pairs = [
            (m, st, who)
            for m, st in live
            if m["borrowed"] > 0
            for who in by_market.get(m["id"], [])
        ]
        pos = call_many(
            self.w3,
            [Call(self.blue, POSITION, (bytes.fromhex(m["id"][2:]), who)) for m, _, who in pairs],
            block=block,
            deadline=deadline,
        )
        shares: dict[str, list[float]] = {}
        for (m, st, _), p in zip(pairs, pos, strict=True):
            if p and int(p[1]) > 0 and st[3] > 0:
                shares.setdefault(m["id"], []).append(int(p[1]) / st[3])
        out = {mid: {"count": len(v), "top_share": max(v)} for mid, v in shares.items()}
        return out, int(doc["last_block"])

    def _scan_borrowers(self, doc: dict[str, Any] | None) -> dict[str, Any]:
        """Add `Borrow` events since the last scan: borrower addresses by market id."""
        head = self.block()
        start = doc["last_block"] + 1 if doc else 0
        by_market: dict[str, list[str]] = {
            k: list(v) for k, v in (doc or {}).get("by_market", {}).items()
        }
        if start <= head:
            span = self.cfg.discovery.oracle_study.max_log_block_range * 20
            for ev in get_logs(self.w3_logs, BORROW, [self.blue], start, head, max_range=span):
                mid = "0x" + bytes(ev["id"]).hex()
                who = str(to_checksum_address(ev["onBehalf"]))
                seen = by_market.setdefault(mid, [])
                if who not in seen:
                    seen.append(who)
        out = {"last_block": head, "scanned_at": time.time(), "by_market": by_market}
        self._save(self.borrowers_by_market, "live_borrowers_by_market", out)
        return out

    # ------------------------------------------------------------------ positions
    def positions(self, address: str, now: datetime | None = None) -> dict[str, Any]:
        if not is_address(address):
            raise ValueError("not an address")
        user = to_checksum_address(address)
        now = now or datetime.now(UTC)
        deadline = self.deadline()
        block = self.block()
        markets = self.markets()
        pos = call_many(
            self.w3,
            [Call(self.blue, POSITION, (bytes.fromhex(m.id[2:]), user)) for m in markets],
            block=block,
            deadline=deadline,
        )
        held = [(m, p) for m, p in zip(markets, pos, strict=True) if p and any(int(x) for x in p)]
        states = call_many(
            self.w3,
            [Call(self.blue, MARKET, (bytes.fromhex(m.id[2:]),)) for m, _ in held],
            block=block,
            deadline=deadline,
        )
        prices = call_many(
            self.w3,
            [Call(m.oracle, "price()(uint256)") for m, _ in held],
            block=block,
            deadline=deadline,
        )
        tokens = sorted({m.loan_token for m, _ in held} | {m.collateral for m, _ in held})
        dec = self.decimals(tokens, block, deadline)
        names = self.symbols(sorted({m.loan_token for m, _ in held}), block, deadline)
        out = []
        for (m, p), st, price in zip(held, states, prices, strict=True):
            supply_shares, borrow_shares, collateral = (int(x) for x in p)
            ldec, cdec = dec[m.loan_token], dec[m.collateral]
            borrowed = to_assets(borrow_shares, int(st[2]), int(st[3]), up=True) / 10**ldec
            supplied = to_assets(supply_shares, int(st[0]), int(st[1]), up=False) / 10**ldec
            coll = collateral / 10**cdec
            px = int(price) * 10**cdec / 1e36 / 10**ldec if price else None  # loan per token
            row: dict[str, Any] = {
                "market_id": m.id,
                "symbol": m.symbol,
                "lltv": m.lltv,
                "loan_is_usdg": m.loan_token == self.usdg,
                "loan_token": m.loan_token,
                "loan_symbol": names[m.loan_token],
                "collateral_tokens": coll,
                "borrowed": borrowed,
                "supplied": supplied,
                "price": px,
            }
            if px and coll > 0 and borrowed > 0 and m.lltv > 0:
                ltv = borrowed / (coll * px)
                liq = borrowed / (coll * m.lltv)
                drop = max(0.0, 1 - liq / px)
                f = self.tonight(m.symbol, now)
                row |= {
                    "ltv": ltv,
                    "liquidation_price": liq,
                    "drop_to_liquidation": drop,
                    "tonight": f,
                    "breach_tonight": bool(f and f["bad_case_drop"] >= drop),
                }
            out.append(row)
        return {
            "network": self.cfg.chains[self.cfg.profiles[self.cfg.live.profile].chain].name,
            "address": user,
            "block": block,
            "as_of": now.isoformat(),
            "markets_checked": len(markets),
            "positions": out,
        }

    # ------------------------------------------------------------------ examples
    def examples(self) -> list[str]:
        """A few addresses with an open USDG borrow in a Stock Token market (from Borrow events).

        Borrowers are kept in `live-borrowers.json`, newest first, and later calls scan only the
        blocks since the last scan.
        """
        block = self.block()
        ids = [m.id for m in self.markets() if m.loan_token == self.usdg]
        if not ids:
            return []
        with self._lock:
            doc = self._load(self.borrowers, "live_borrowers")
            if doc is not None and doc.get("markets") != sorted(ids):
                doc = None  # a new market appeared: rescan from the start
            start = doc["last_block"] + 1 if doc else 0
            seen: list[str] = list(doc["borrowers"]) if doc else []
            if start <= block:
                span = self.cfg.discovery.oracle_study.max_log_block_range * 20
                logs = get_logs(
                    self.w3_logs, BORROW, [self.blue], start, block, topics=[ids], max_range=span
                )
                for ev in logs:
                    who = str(to_checksum_address(ev["onBehalf"]))
                    seen = [who, *(w for w in seen if w != who)]
            out_doc = {"last_block": block, "markets": sorted(ids), "borrowers": seen}
            self._save(self.borrowers, "live_borrowers", out_doc)
        out: list[str] = []
        # Newest first; a rate-limited check skips that borrower instead of losing the list.
        for who in seen[: self.cfg.live.examples * 5]:
            if len(out) >= self.cfg.live.examples:
                break
            try:
                if any("ltv" in p for p in self.positions(who)["positions"]):
                    out.append(who)
            except Exception as exc:
                log.warning("checking example borrower %s failed: %s", who, exc)
        return out
