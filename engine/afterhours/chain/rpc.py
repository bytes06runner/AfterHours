"""Web3 connections and batched cast-style calls."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import requests
from eth_utils import to_checksum_address
from web3 import Web3
from web3.providers.rpc.utils import ExceptionRetryConfiguration
from web3.types import BlockIdentifier

from afterhours.chain.abi import decode_output, encode_call


def connect(url: str, *, timeout: float = 30) -> Web3:
    """HTTP Web3 client for an RPC URL, retrying rate-limited requests with backoff."""
    retry = ExceptionRetryConfiguration(
        errors=(requests.ConnectionError, requests.HTTPError, requests.Timeout),
        retries=6,
        backoff_factor=1.0,
    )
    return Web3(
        Web3.HTTPProvider(
            url, request_kwargs={"timeout": timeout}, exception_retry_configuration=retry
        )
    )


@dataclass(frozen=True)
class Call:
    """One view call in cast syntax."""

    to: str
    signature: str
    args: tuple[Any, ...] = ()


def call_many(
    w3: Web3,
    calls: Sequence[Call],
    *,
    block: BlockIdentifier = "latest",
    chunk: int = 50,
) -> list[Any]:
    """Run calls in raw JSON-RPC batches. A call that reverts yields None.

    Raw batches let each call fail on its own; web3's batch helper fails the whole batch.
    Node lag is retried with backoff; any other RPC error raises `RpcError`, so a node
    problem is never mistaken for a failed check. Falls back to one-by-one calls if the
    endpoint rejects batches.
    """
    url = getattr(w3.provider, "endpoint_uri", None)
    tag = hex(block) if isinstance(block, int) else str(block)
    results: list[Any] = []
    pending = [calls[i : i + chunk] for i in range(0, len(calls), chunk)]
    attempt = 0
    while pending:
        part = pending.pop(0)
        payload = [
            {
                "jsonrpc": "2.0",
                "id": n,
                "method": "eth_call",
                "params": [
                    {
                        "to": to_checksum_address(c.to),
                        "data": "0x" + encode_call(c.signature, *c.args).hex(),
                    },
                    tag,
                ],
            }
            for n, c in enumerate(part)
        ]
        try:
            if not url:
                raise RuntimeError("provider has no HTTP endpoint")
            body = _post_with_backoff(str(url), payload)
            if not isinstance(body, list):
                raise RuntimeError(f"endpoint does not batch: {str(body)[:120]}")
            by_id = {int(r["id"]): r for r in body}
        except (httpx.HTTPError, RuntimeError, ValueError):
            results.extend(_single(w3, c, block) for c in part)
            continue
        lagging = [r for r in by_id.values() if "error" in r and is_node_lag(r["error"])]
        if lagging and attempt < len(RETRY_DELAYS_S):
            time.sleep(RETRY_DELAYS_S[attempt])
            attempt += 1
            pending.insert(0, part)
            continue
        attempt = 0
        for n, c in enumerate(part):
            r = by_id.get(n, {})
            if "error" in r:
                if not is_revert(r["error"]):
                    raise RpcError(f"{c.signature} on {c.to}: {r['error']}")
                results.append(None)
                continue
            raw = r.get("result")
            results.append(_decode(c, bytes.fromhex(raw[2:])) if raw and raw != "0x" else None)
    return results


RETRY_DELAYS_S = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)


class RpcError(RuntimeError):
    """An RPC failure that is not a contract revert (missing state, bad request, ...)."""


def is_node_lag(error: Any) -> bool:
    """True when a load-balanced node has not reached the requested block yet."""
    text = str(error).lower()
    return "unsupported block number" in text or "header not found" in text


def is_revert(error: Any) -> bool:
    """True for a contract revert, as opposed to an RPC or node problem."""
    text = str(error).lower()
    code = error.get("code") if isinstance(error, dict) else None
    return code == 3 or "revert" in text or "invalid opcode" in text


def _post_with_backoff(url: str, payload: Any) -> Any:
    """POST JSON-RPC, waiting and retrying on HTTP 429 or 5xx before giving up."""
    for delay in (*RETRY_DELAYS_S, None):
        resp = httpx.post(url, json=payload, timeout=60)
        if resp.status_code == 429 or resp.status_code >= 500:
            if delay is None:
                resp.raise_for_status()
            time.sleep(delay)  # type: ignore[arg-type]
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("unreachable")


def _decode(c: Call, raw: bytes) -> Any:
    try:
        return decode_output(c.signature, raw)
    except Exception:
        return None


def _single(w3: Web3, c: Call, block: BlockIdentifier) -> Any:
    try:
        raw = w3.eth.call(
            {"to": to_checksum_address(c.to), "data": encode_call(c.signature, *c.args)},
            block_identifier=block,
        )
    except Exception as exc:
        if is_revert(getattr(exc, "args", [exc])[0] if getattr(exc, "args", None) else exc):
            return None
        raise RpcError(f"{c.signature} on {c.to}: {exc}") from exc
    return _decode(c, bytes(raw))


def block_at_or_after(w3: Web3, timestamp: int, *, hi: int | None = None) -> int:
    """First block whose timestamp is >= `timestamp`, by interpolation then bisection."""
    top = hi if hi is not None else int(w3.eth.block_number)
    lo, lo_ts = 1, int(w3.eth.get_block(1)["timestamp"])
    hi_n, hi_ts = top, int(w3.eth.get_block(top)["timestamp"])
    if timestamp <= lo_ts:
        return lo
    if timestamp > hi_ts:
        raise ValueError("timestamp is in the future of the chain head")
    while hi_n - lo > 1:
        guess = lo + int((timestamp - lo_ts) * (hi_n - lo) / max(hi_ts - lo_ts, 1))
        mid = min(max(guess, lo + 1), hi_n - 1)
        if hi_n - lo < 64:
            mid = (lo + hi_n) // 2
        ts = int(w3.eth.get_block(mid)["timestamp"])
        if ts >= timestamp:
            hi_n, hi_ts = mid, ts
        else:
            lo, lo_ts = mid, ts
    return hi_n
