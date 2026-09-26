"""Server-side check that a reason card matches its onchain registry event.

The browser repeats this independently (web/src/lib/verify.ts); this copy lets the API report
the result and the tests prove the round trip.
"""

from __future__ import annotations

from typing import Any

from web3 import Web3

from afterhours.chain.abi import decode_log, parse_event
from afterhours.explain.reason import reason_hash

REASON_LOGGED = (
    "ReasonLogged(uint256 indexed seq,bytes32 indexed subject,bytes32 reasonHash,string uri,"
    "uint64 timestamp)"
)


def verify_card(w3: Web3, card: dict[str, Any], registry: str) -> dict[str, Any]:
    """Recompute the card hash and compare it with the ReasonLogged event in its registry tx."""
    recomputed = reason_hash(card)
    tx = (card.get("tx") or {}).get("registry_tx")
    if not tx:
        return {"status": "no_tx", "recomputed_hash": recomputed}
    receipt = w3.eth.get_transaction_receipt(tx)
    event = parse_event(REASON_LOGGED)
    logs = [
        decode_log(event, log)
        for log in receipt["logs"]
        if log["address"].lower() == registry.lower()
        and "0x" + bytes(log["topics"][0]).hex() == event.topic0
    ]
    if not logs:
        return {"status": "event_missing", "recomputed_hash": recomputed, "registry_tx": tx}
    logged = logs[0]
    onchain = "0x" + bytes(logged["reasonHash"]).hex()
    subject = "0x" + bytes(logged["subject"]).hex()
    matched = onchain == recomputed and subject.lower() == str(card["subject"]).lower()
    return {
        "status": "matched" if matched else "mismatched",
        "recomputed_hash": recomputed,
        "onchain_hash": onchain,
        "seq": int(logged["seq"]),
        "block": int(receipt["blockNumber"]),
        "registry_tx": tx,
        "uri": logged["uri"],
    }
