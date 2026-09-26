"""Seed simulated lenders and borrowers on a fork or local chain (Simulation).

Actors are fixed addresses derived from a label and driven with Anvil's account impersonation,
so no keys are created for them. On the local profile, USDG (sim) and Stock Tokens (sim) are
minted by the deployer. On the fork, balances come from real holders (the deepest Uniswap
pools), also through impersonation. Nothing here runs outside Anvil.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

from eth_abi import encode
from eth_utils import keccak, to_checksum_address
from web3 import Web3

from afterhours.bot.vault_state import PARAMS_TYPE, read_state
from afterhours.chain.abi import encode_call
from afterhours.chain.rpc import Call, call_many
from afterhours.chain.tx import Signer
from afterhours.config import AfterhoursConfig
from afterhours.deploy import role_keys
from afterhours.deployments import load_discovered

log = logging.getLogger(__name__)
WAD = 10**18


def actor(label: str) -> str:
    """Deterministic simulated account for a label."""
    return to_checksum_address("0x" + keccak(text=f"afterhours:sim:{label}")[-20:].hex())


@dataclass
class Anvil:
    """Impersonation helpers for an Anvil node."""

    w3: Web3

    def fund_eth(self, address: str, eth: float) -> None:
        self.w3.provider.make_request("anvil_setBalance", [address, hex(int(eth * 1e18))])  # type: ignore[arg-type]

    def send_as(self, sender: str, to: str, signature: str, *args: Any) -> str:
        """Send a transaction from any address (Anvil impersonation)."""
        self.w3.provider.make_request("anvil_impersonateAccount", [sender])  # type: ignore[arg-type]
        try:
            tx_hash = self.w3.eth.send_transaction(
                {
                    "from": to_checksum_address(sender),
                    "to": to_checksum_address(to),
                    "data": "0x" + encode_call(signature, *args).hex(),  # type: ignore[typeddict-item]
                }
            )
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            if int(receipt["status"]) != 1:
                raise RuntimeError(f"{signature} from {sender} reverted")
            return "0x" + bytes(tx_hash).hex()
        finally:
            self.w3.provider.make_request("anvil_stopImpersonatingAccount", [sender])  # type: ignore[arg-type]


class Seeder:
    """Creates lenders and borrowers for the active profile."""

    def __init__(self, cfg: AfterhoursConfig, w3: Web3, deployment: dict[str, Any]) -> None:
        self.cfg = cfg
        self.w3 = w3
        self.d = deployment
        self.anvil = Anvil(w3)
        self.rng = random.Random(cfg.sim.seed)
        self.sim_collateral = bool(deployment["simulation"]["collateral"])
        keys = role_keys(cfg, cfg.active_profile)
        self.owner = Signer(w3, keys["DEPLOYER_PK"])
        self.discovered = load_discovered(cfg, "fork")

    def _token_source(self, symbol: str) -> str:
        """A real holder of a Stock Token or USDG on the fork: its deepest Uniswap v3 pool."""
        pools = self.discovered["stock_tokens"][symbol]["pools"]
        v3 = [p for p in pools if p["version"] == "v3"]
        if v3:
            return str(v3[0]["address_or_id"])
        return str(self.discovered["core"]["uniswap_v4_pool_manager"]["address"])

    def _give(self, token: str, to: str, amount: int, symbol: str) -> None:
        if self.sim_collateral:
            self.owner.send(token, "mint(address,uint256)", to, amount)
        else:
            source = self._token_source(symbol)
            self.anvil.fund_eth(source, 1)
            self.anvil.send_as(source, token, "transfer(address,uint256)", to, amount)

    def lenders(self) -> list[dict[str, Any]]:
        """Deposit USDG into the vault from `sim.lenders` accounts."""
        loan = self.d["loan_token"]["address"]
        vault = self.d["vault"]["address"]
        dec = int(call_many(self.w3, [Call(loan, "decimals()(uint8)")])[0])
        out = []
        for i in range(self.cfg.sim.lenders):
            who = actor(f"lender-{i}")
            r = self.cfg.sim.lender_deposit_usdg
            amount = int(self.rng.uniform(r.low, r.high)) * 10**dec
            self.anvil.fund_eth(who, self.cfg.sim.eth_per_actor)
            self._give(loan, who, amount, "NVDA")  # on the fork, the NVDA/USDG pool also holds USDG
            self.anvil.send_as(who, loan, "approve(address,uint256)", vault, amount)
            self.anvil.send_as(who, vault, "deposit(uint256,address)(uint256)", amount, who)
            out.append({"lender": who, "usdg": amount / 10**dec})
        return out

    def borrowers(self) -> list[dict[str, Any]]:
        """Borrow in every market the vault supplies, at LTVs spread across the tier."""
        state = read_state(self.w3, self.d)
        morpho = self.d["morpho"]["address"]
        unit = 10**state.decimals
        prices = call_many(self.w3, [Call(m.params[2], "price()(uint256)") for m in state.markets])
        out = []
        for m, price in zip(state.markets, prices, strict=True):
            available = (
                m.market_supply - m.market_borrow
            ) * self.cfg.sim.borrow_share_of_market_supply
            if available * unit < 1 or not price:
                continue
            lltv = m.params[4] / WAD
            per = available / self.cfg.sim.borrowers_per_market
            for j in range(self.cfg.sim.borrowers_per_market):
                who = actor(f"borrower-{m.symbol}-{m.tier}-{j}")
                r = self.cfg.sim.borrower_ltv_share_of_lltv
                ltv = lltv * self.rng.uniform(r.low, r.high)
                borrow = int(per * unit)
                collateral = borrow * 10**36 // int(ltv * WAD) * WAD // int(price)
                self.anvil.fund_eth(who, self.cfg.sim.eth_per_actor)
                self._give(m.params[1], who, collateral, m.symbol)
                self.anvil.send_as(who, m.params[1], "approve(address,uint256)", morpho, collateral)
                params = m.params
                self.anvil.send_as(
                    who,
                    morpho,
                    f"supplyCollateral({PARAMS_TYPE},uint256,address,bytes)",
                    params,
                    collateral,
                    who,
                    b"",
                )
                self.anvil.send_as(
                    who,
                    morpho,
                    f"borrow({PARAMS_TYPE},uint256,uint256,address,address)(uint256,uint256)",
                    params,
                    borrow,
                    0,
                    who,
                    who,
                )
                out.append(
                    {
                        "borrower": who,
                        "symbol": m.symbol,
                        "tier": m.tier,
                        "usdg": borrow / unit,
                        "ltv": round(ltv, 4),
                    }
                )
        return out


def market_data(params: tuple[str, str, str, str, int]) -> bytes:
    """abi.encode(MarketParams) as the adapter expects."""
    return encode([PARAMS_TYPE], [params])
