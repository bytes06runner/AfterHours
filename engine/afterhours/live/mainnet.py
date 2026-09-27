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

import json
import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from eth_utils import is_address, to_checksum_address
from web3 import Web3

from afterhours.chain.abi import get_logs
from afterhours.chain.rpc import Call, call_many, connect
from afterhours.config import AfterhoursConfig
from afterhours.data.pipeline import make_cache
from afterhours.deployments import load_discovered
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
        # Log scans need wide block ranges, which the public RPC allows (live.logs_from_public_rpc).
        self.w3_logs: Web3 = (
            connect(public, timeout=cfg.live.rpc_timeout_seconds, retries=cfg.live.rpc_retries)
            if cfg.live.logs_from_public_rpc and public
            else self.w3
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
        self._lock = threading.Lock()
        self._board_lock = threading.Lock()
        self._board: tuple[float, dict[str, Any]] | None = None
        self._decimals: dict[str, int] = {}
        self._symbols: dict[str, str | None] = {}
        self.store = cfg.path(cfg.paths.state_dir) / "live-markets.json"
        self.borrowers = cfg.path(cfg.paths.state_dir) / "live-borrowers.json"

    # ------------------------------------------------------------------ chain helpers
    def deadline(self) -> float:
        """The time budget for one live read (`live.refresh_budget_seconds`)."""
        return time.monotonic() + self.cfg.live.refresh_budget_seconds

    def block(self) -> int:
        return int(self.w3.eth.block_number) - self.cfg.live.lag_blocks

    def decimals(
        self, tokens: list[str], block: int, deadline: float | None = None
    ) -> dict[str, int]:
        missing = [t for t in tokens if t not in self._decimals]
        if missing:
            calls = [Call(t, "decimals()(uint8)") for t in missing]
            vals = call_many(self.w3, calls, block=block, deadline=deadline)
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
        if not self.store.exists():
            return None
        doc: dict[str, Any] = json.loads(self.store.read_text())
        return doc

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
        self.store.parent.mkdir(parents=True, exist_ok=True)
        self.store.write_text(json.dumps(out))
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
        return f.to_json()

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

    def _refresh_in_background(self, now: datetime | None) -> None:
        try:
            self._refresh_board(now)
        except Exception as exc:  # the last board stays; the next request tries again
            log.warning("board refresh failed: %s", exc)
        finally:
            self._board_lock.release()

    def _refresh_board(self, now: datetime | None) -> dict[str, Any]:
        cached = self._board
        if cached and time.time() - cached[0] < self.cfg.live.board_cache_seconds:
            return cached[1]
        doc = self._board_now(now or datetime.now(UTC))
        self._board = (time.time(), doc)
        return doc

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
            "stocks": rows,
        }
        self._board = (time.time(), doc)
        return doc

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
            doc = json.loads(self.borrowers.read_text()) if self.borrowers.exists() else None
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
            self.borrowers.write_text(json.dumps(out_doc))
        out: list[str] = []
        for who in seen:
            if len(out) >= self.cfg.live.examples:
                break
            if any("ltv" in p for p in self.positions(who)["positions"]):
                out.append(who)
        return out
