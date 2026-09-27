"""State shared by the bot and the API: reason cards, plans and an event log.

The bot appends; the API reads and tails the event log for server-sent events, so either
process can restart without losing history. Two backends with the same methods:

- files under `paths.state_dir/<profile>/` (local runs and the paid host with a disk);
- Upstash Redis (`state` in config) when its env vars are set, so a bot run in GitHub Actions
  and an API on a host without a disk share one history.
"""

from __future__ import annotations

import fcntl
import json
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from afterhours.config import AfterhoursConfig
from afterhours.kv import KV, kv_from_config

EVENT_TYPES = (
    "status",
    "plan_changed",
    "tx_sent",
    "tx_confirmed",
    "reason_logged",
    "vault_updated",
)

# Releases the lock only if we still hold it (the value is our random token).
UNLOCK = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)


def _event(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    if kind not in EVENT_TYPES:
        raise ValueError(f"unknown event type {kind}")
    return {"type": kind, "at": datetime.now(UTC).isoformat(), "data": data}


class BaseStore:
    """What the bot and the API use; offsets are opaque positions in the event log."""

    poll_seconds: float = 0.5

    def emit(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def events_end(self) -> int:
        raise NotImplementedError

    def events_since(self, offset: int) -> tuple[list[dict[str, Any]], int]:
        raise NotImplementedError

    def add_reason(self, card: dict[str, Any]) -> None:
        raise NotImplementedError

    def reasons(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def write(self, name: str, doc: dict[str, Any]) -> None:
        raise NotImplementedError

    def read(self, name: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @contextmanager
    def lock(self, name: str) -> Iterator[None]:
        raise NotImplementedError
        yield

    def tail(self, start_at_end: bool = True) -> Iterator[dict[str, Any]]:
        """Follow the event log (blocking generator)."""
        offset = self.events_end() if start_at_end else 0
        while True:
            events, offset = self.events_since(offset)
            yield from events
            time.sleep(self.poll_seconds)


@dataclass
class Store(BaseStore):
    """File backend: state for one profile under `paths.state_dir/<profile>/`."""

    root: Path
    poll_seconds: float = 0.5

    @classmethod
    def for_profile(cls, cfg: AfterhoursConfig, profile: str | None = None) -> BaseStore:
        """The shared store when configured (see `state` in config) and the profile is a real
        chain, else files."""
        name = profile or cfg.active_profile
        # Local and fork profiles run on Anvil and are never hosted: they keep files even when
        # the shared store's env vars are in .env, so demos never mix into the hosted history.
        kv = None if cfg.profiles[name].local_rpc_port_env else kv_from_config(cfg)
        if kv is not None:
            return KVStore(kv, name, cfg)
        root = cfg.path(cfg.paths.state_dir) / name
        root.mkdir(parents=True, exist_ok=True)
        return cls(root, cfg.api.sse_poll_seconds)

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def reasons_path(self) -> Path:
        return self.root / "reasons.jsonl"

    def emit(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """Append one event."""
        event = _event(kind, data)
        with self.events_path.open("a") as f:
            f.write(json.dumps(event, default=str) + "\n")
        return event

    def events_end(self) -> int:
        return self.events_path.stat().st_size if self.events_path.exists() else 0

    def events_since(self, offset: int) -> tuple[list[dict[str, Any]], int]:
        """Events appended after byte `offset`, and the new offset."""
        if not self.events_path.exists():
            return [], 0
        with self.events_path.open() as f:
            f.seek(offset)
            lines = f.readlines()
            return [json.loads(line) for line in lines if line.strip()], f.tell()

    def add_reason(self, card: dict[str, Any]) -> None:
        with self.reasons_path.open("a") as f:
            f.write(json.dumps(card, default=str) + "\n")

    def reasons(self) -> list[dict[str, Any]]:
        """All reason cards, newest first."""
        if not self.reasons_path.exists():
            return []
        cards = [
            json.loads(line) for line in self.reasons_path.read_text().splitlines() if line.strip()
        ]
        return list(reversed(cards))

    def write(self, name: str, doc: dict[str, Any]) -> None:
        (self.root / f"{name}.json").write_text(json.dumps(doc, indent=2, default=str) + "\n")

    def read(self, name: str) -> dict[str, Any] | None:
        path = self.root / f"{name}.json"
        if not path.exists():
            return None
        data: dict[str, Any] = json.loads(path.read_text())
        return data

    @contextmanager
    def lock(self, name: str) -> Iterator[None]:
        """One holder at a time across processes on this machine."""
        with (self.root / f"{name}.lock").open("w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


@dataclass
class KVStore(BaseStore):
    """Upstash Redis backend: lists for events and reasons, one key per document.

    Reads are cached for `state.read_cache_seconds` and the event log length for
    `state.event_poll_seconds`, so an API that stays awake stays inside the free command quota.
    Offsets are list indexes.
    """

    kv: KV
    profile: str
    cfg: AfterhoursConfig
    _cache: dict[str, tuple[float, Any]] = field(default_factory=dict)

    @property
    def poll_seconds(self) -> float:  # type: ignore[override]
        return float(self.cfg.state.event_poll_seconds)

    def _key(self, *parts: str) -> str:
        return self.kv.key(self.profile, *parts)

    def _cached(self, name: str, ttl: float, load: Any) -> Any:
        hit = self._cache.get(name)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        value = load()
        self._cache[name] = (time.monotonic(), value)
        return value

    def emit(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        event = _event(kind, data)
        self.kv.cmd("RPUSH", self._key("events"), json.dumps(event, default=str))
        self._cache.pop("events_end", None)
        return event

    def events_end(self) -> int:
        ttl = self.cfg.state.event_poll_seconds
        return int(
            self._cached("events_end", ttl, lambda: self.kv.cmd("LLEN", self._key("events")))
        )

    def events_since(self, offset: int) -> tuple[list[dict[str, Any]], int]:
        end = self.events_end()
        if end <= offset:
            return [], end
        rows = self.kv.cmd("LRANGE", self._key("events"), offset, end - 1)
        return [json.loads(r) for r in rows], end

    def add_reason(self, card: dict[str, Any]) -> None:
        self.kv.cmd("RPUSH", self._key("reasons"), json.dumps(card, default=str))
        self._cache.pop("reasons", None)

    def reasons(self) -> list[dict[str, Any]]:
        def load() -> list[dict[str, Any]]:
            rows = self.kv.cmd("LRANGE", self._key("reasons"), 0, -1)
            return list(reversed([json.loads(r) for r in rows]))

        cards: list[dict[str, Any]] = self._cached(
            "reasons", self.cfg.state.read_cache_seconds, load
        )
        return cards

    def write(self, name: str, doc: dict[str, Any]) -> None:
        self.kv.cmd("SET", self._key("doc", name), json.dumps(doc, default=str))
        self._cache[f"doc:{name}"] = (time.monotonic(), json.loads(json.dumps(doc, default=str)))

    def read(self, name: str) -> dict[str, Any] | None:
        def load() -> dict[str, Any] | None:
            raw = self.kv.cmd("GET", self._key("doc", name))
            return json.loads(raw) if raw else None

        doc: dict[str, Any] | None = self._cached(
            f"doc:{name}", self.cfg.state.read_cache_seconds, load
        )
        return doc

    @contextmanager
    def lock(self, name: str) -> Iterator[None]:
        """One holder at a time anywhere; expires after `state.cycle_lock_seconds`."""
        key, token = self._key("lock", name), secrets.token_hex(16)
        ttl = self.cfg.state.cycle_lock_seconds
        deadline = time.monotonic() + ttl
        while self.kv.cmd("SET", key, token, "NX", "EX", ttl) is None:
            if time.monotonic() > deadline:
                raise TimeoutError(f"{name} lock is held elsewhere")
            time.sleep(1)
        try:
            yield
        finally:
            self.kv.cmd("EVAL", UNLOCK, 1, key, token)


def copy_to_shared(src: Store, dst: KVStore, *, dry_run: bool = False) -> dict[str, int]:
    """One-time copy of a profile's file history into the shared store, unchanged.

    Events and reason cards keep their order and timestamps; documents (plan, forecasts, ...)
    are copied as they are. Refuses if the shared store already has events or reasons for the
    profile, so running it twice cannot duplicate history. Returns what was (or would be) copied.
    """
    events = (
        [line for line in src.events_path.read_text().splitlines() if line.strip()]
        if (src.events_path.exists())
        else []
    )
    reasons = (
        [line for line in src.reasons_path.read_text().splitlines() if line.strip()]
        if (src.reasons_path.exists())
        else []
    )
    docs = {p.stem: json.loads(p.read_text()) for p in sorted(src.root.glob("*.json"))}
    counts = {"events": len(events), "reasons": len(reasons), "documents": len(docs)}
    have = dst.kv.pipeline([["LLEN", dst._key("events")], ["LLEN", dst._key("reasons")]])
    if any(int(n) for n in have):
        raise ValueError(
            f"the shared store already has history for {dst.profile} "
            f"({have[0]} events, {have[1]} reasons); nothing copied"
        )
    if dry_run:
        return counts
    batch = 100  # keeps each request far below Upstash's 10 MB request limit
    for key, rows in (("events", events), ("reasons", reasons)):
        for i in range(0, len(rows), batch):
            dst.kv.cmd("RPUSH", dst._key(key), *rows[i : i + batch])
    for name, doc in docs.items():
        dst.write(name, doc)
    return counts
