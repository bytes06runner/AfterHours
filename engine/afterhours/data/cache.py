"""Parquet cache with a manifest recording source, fetch time and row count per entry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class ParquetCache:
    """Key-value store of DataFrames under `root`, e.g. key `prices/NVDA`."""

    root: Path
    max_age: timedelta

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def _manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            data: dict[str, Any] = json.loads(self.manifest_path.read_text())
            return data
        return {}

    def path(self, key: str) -> Path:
        return self.root / f"{key}.parquet"

    def get(self, key: str, *, allow_stale: bool = False) -> pd.DataFrame | None:
        """Cached frame, or None when missing (or stale unless `allow_stale`)."""
        entry = self._manifest().get(key)
        path = self.path(key)
        if not entry or not path.exists():
            return None
        fetched = datetime.fromisoformat(entry["fetched_at"])
        if not allow_stale and datetime.now(UTC) - fetched > self.max_age:
            return None
        return pd.read_parquet(path)

    def put(self, key: str, frame: pd.DataFrame, source: str) -> None:
        """Store a frame and record where it came from."""
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path)
        manifest = self._manifest()
        manifest[key] = {
            "source": source,
            "fetched_at": datetime.now(UTC).isoformat(),
            "rows": len(frame),
        }
        self.manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True))

    def entry(self, key: str) -> dict[str, Any] | None:
        """Manifest entry for a key."""
        value: dict[str, Any] | None = self._manifest().get(key)
        return value
