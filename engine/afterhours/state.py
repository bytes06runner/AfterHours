"""File-backed state shared by the bot and the API: reason cards, plans and an event log.

The bot appends; the API reads and tails the event log for server-sent events, so either
process can restart without losing history.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from afterhours.config import AfterhoursConfig

EVENT_TYPES = (
    "status",
    "plan_changed",
    "tx_sent",
    "tx_confirmed",
    "reason_logged",
    "vault_updated",
)


@dataclass
class Store:
    """State for one profile under `paths.state_dir/<profile>/`."""

    root: Path

    @classmethod
    def for_profile(cls, cfg: AfterhoursConfig, profile: str | None = None) -> Store:
        root = cfg.path(cfg.paths.state_dir) / (profile or cfg.active_profile)
        root.mkdir(parents=True, exist_ok=True)
        return cls(root)

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def reasons_path(self) -> Path:
        return self.root / "reasons.jsonl"

    def emit(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """Append one event."""
        if kind not in EVENT_TYPES:
            raise ValueError(f"unknown event type {kind}")
        event = {"type": kind, "at": datetime.now(UTC).isoformat(), "data": data}
        with self.events_path.open("a") as f:
            f.write(json.dumps(event, default=str) + "\n")
        return event

    def events_since(self, offset: int) -> tuple[list[dict[str, Any]], int]:
        """Events appended after byte `offset`, and the new offset."""
        if not self.events_path.exists():
            return [], 0
        with self.events_path.open() as f:
            f.seek(offset)
            lines = f.readlines()
            return [json.loads(line) for line in lines if line.strip()], f.tell()

    def tail(
        self, poll_seconds: float = 0.5, start_at_end: bool = True
    ) -> Iterator[dict[str, Any]]:
        """Follow the event log (blocking generator)."""
        offset = (
            self.events_path.stat().st_size if start_at_end and self.events_path.exists() else 0
        )
        while True:
            events, offset = self.events_since(offset)
            yield from events
            time.sleep(poll_seconds)

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
