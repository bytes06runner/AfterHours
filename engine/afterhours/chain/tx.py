"""Sign and send transactions from a role key held in memory (never logged)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_account import Account
from eth_utils import to_checksum_address
from web3 import Web3

from afterhours.chain.abi import encode_call


@dataclass(frozen=True)
class Sent:
    """A mined transaction."""

    tx_hash: str
    block: int
    status: int
    gas_used: int


class Signer:
    """Sends calls from one account."""

    def __init__(self, w3: Web3, private_key: str) -> None:
        self.w3 = w3
        self._account = Account.from_key(private_key)
        self.address = to_checksum_address(self._account.address)

    def send(self, to: str, signature: str, *args: Any, timeout: float = 120) -> Sent:
        """Build, sign, send and wait for one transaction; raises if it reverts."""
        tx: dict[str, Any] = {
            "from": self.address,
            "to": to_checksum_address(to),
            "data": "0x" + encode_call(signature, *args).hex(),
            "nonce": self.w3.eth.get_transaction_count(self.address, "pending"),
            "chainId": int(self.w3.eth.chain_id),
        }
        tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)  # type: ignore[arg-type]
        base = int(self.w3.eth.get_block("latest").get("baseFeePerGas", 0) or 0)
        tip = int(self.w3.eth.max_priority_fee) if base else 0
        tx["maxPriorityFeePerGas"] = tip
        tx["maxFeePerGas"] = 2 * base + tip
        signed = self._account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        sent = Sent(
            "0x" + bytes(tx_hash).hex(),
            int(receipt["blockNumber"]),
            int(receipt["status"]),
            int(receipt["gasUsed"]),
        )
        if sent.status != 1:
            raise RuntimeError(f"transaction {sent.tx_hash} reverted")
        return sent
