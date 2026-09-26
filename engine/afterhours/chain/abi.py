"""cast-style signatures for calls and logs, so ABIs stay one readable line each.

`call(w3, token, "decimals()(uint8)")` works like `cast call token "decimals()(uint8)"`.
Events use Solidity syntax with `indexed`, e.g.
`"AnswerUpdated(int256 indexed current,uint256 indexed roundId,uint256 updatedAt)"`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from eth_abi import decode, encode
from eth_utils import keccak, to_checksum_address
from web3 import Web3
from web3.types import BlockIdentifier

log = logging.getLogger(__name__)


def split_top_level(types: str) -> list[str]:
    """Split `a,(b,c),d` on commas that are not inside parentheses."""
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in types:
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


@dataclass(frozen=True)
class FunctionSig:
    """A parsed `name(inputs)(outputs)` signature."""

    name: str
    inputs: list[str]
    outputs: list[str]

    @property
    def canonical(self) -> str:
        return f"{self.name}({','.join(self.inputs)})"

    @property
    def selector(self) -> bytes:
        return keccak(text=self.canonical)[:4]


def parse_function(signature: str) -> FunctionSig:
    """Parse `name(in1,in2)(out1,out2)`; the output list is optional."""
    name, rest = signature.split("(", 1)
    depth = 1
    for i, ch in enumerate(rest):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0:
            inputs, tail = rest[:i], rest[i + 1 :]
            break
    else:
        raise ValueError(f"unbalanced signature: {signature}")
    outputs = tail[1:-1] if tail.startswith("(") and tail.endswith(")") else ""
    return FunctionSig(name.strip(), split_top_level(inputs), split_top_level(outputs))


def encode_call(signature: str, *args: Any) -> bytes:
    """ABI-encode calldata for a signature and arguments."""
    sig = parse_function(signature)
    return sig.selector + encode(sig.inputs, list(args))


def decode_output(signature: str, data: bytes) -> Any:
    """Decode return data; a single output is returned bare, several as a tuple."""
    sig = parse_function(signature)
    values = decode(sig.outputs, data)
    return values[0] if len(values) == 1 else values


def call(
    w3: Web3,
    to: str,
    signature: str,
    *args: Any,
    block: BlockIdentifier = "latest",
) -> Any:
    """eth_call a view (or a revert-free quoter) and decode its outputs."""
    data = w3.eth.call(
        {"to": to_checksum_address(to), "data": encode_call(signature, *args)},
        block_identifier=block,
    )
    return decode_output(signature, bytes(data))


@dataclass(frozen=True)
class EventSig:
    """A parsed event signature with indexed markers."""

    name: str
    params: list[tuple[str, str, bool]]  # (type, name, indexed)

    @property
    def canonical(self) -> str:
        return f"{self.name}({','.join(t for t, _, _ in self.params)})"

    @property
    def topic0(self) -> str:
        return "0x" + keccak(text=self.canonical).hex()


def parse_event(signature: str) -> EventSig:
    """Parse `Name(type indexed name, type name)`."""
    name, rest = signature.split("(", 1)
    params: list[tuple[str, str, bool]] = []
    for raw in split_top_level(rest.rsplit(")", 1)[0]):
        words = raw.split()
        indexed = "indexed" in words
        words = [w for w in words if w != "indexed"]
        params.append((words[0], words[1] if len(words) > 1 else f"arg{len(params)}", indexed))
    return EventSig(name.strip(), params)


def address_topic(address: str) -> str:
    """Left-pad an address to a 32-byte topic."""
    return "0x" + "0" * 24 + address.lower().removeprefix("0x")


def decode_log(event: EventSig, log: Any) -> dict[str, Any]:
    """Decode one raw log into {param name: value} plus block and tx metadata."""
    topics = [bytes(t) for t in log["topics"]][1:]
    indexed = [(t, n) for t, n, i in event.params if i]
    plain = [(t, n) for t, n, i in event.params if not i]
    out: dict[str, Any] = {}
    for (typ, name), topic in zip(indexed, topics, strict=True):
        out[name] = decode([typ], topic)[0]
    if plain:
        values = decode([t for t, _ in plain], bytes(log["data"]))
        out.update({name: value for (_, name), value in zip(plain, values, strict=True)})
    out["_block"] = int(log["blockNumber"])
    out["_address"] = to_checksum_address(log["address"])
    out["_tx"] = "0x" + bytes(log["transactionHash"]).hex()
    return out


def get_logs(
    w3: Web3,
    event: str,
    addresses: Sequence[str],
    from_block: int,
    to_block: int,
    *,
    topics: Sequence[str | list[str] | None] = (),
    max_range: int,
) -> list[dict[str, Any]]:
    """Fetch and decode logs in chunks of at most `max_range` blocks.

    If the RPC refuses a chunk (too many results or too wide a range), the chunk is split in
    half and retried, down to a single block.
    """
    ev = parse_event(event)
    out: list[dict[str, Any]] = []
    start = from_block
    while start <= to_block:
        end = min(start + max_range - 1, to_block)
        out.extend(_logs_split(w3, ev, addresses, start, end, topics))
        start = end + 1
    return out


def _logs_split(
    w3: Web3,
    ev: EventSig,
    addresses: Sequence[str],
    start: int,
    end: int,
    topics: Sequence[str | list[str] | None],
) -> list[dict[str, Any]]:
    try:
        raw = w3.eth.get_logs(
            {
                "address": [to_checksum_address(a) for a in addresses],
                "fromBlock": start,
                "toBlock": end,
                "topics": [ev.topic0, *topics],
            }
        )
    except Exception as exc:
        text = str(exc).lower()
        if start == end or not any(k in text for k in ("exceed", "limit", "range", "too many")):
            raise
        mid = (start + end) // 2
        log.debug("splitting log query %s..%s: %s", start, end, exc)
        return _logs_split(w3, ev, addresses, start, mid, topics) + _logs_split(
            w3, ev, addresses, mid + 1, end, topics
        )
    return [decode_log(ev, entry) for entry in raw]
