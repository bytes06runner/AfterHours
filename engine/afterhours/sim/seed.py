"""Seed simulated lenders and borrowers (Simulation).

Two ways to act as many accounts:
- On Anvil (local and fork profiles), actors are fixed addresses derived from a label and driven
  with account impersonation, so no keys exist for them. On the local profile, USDG (sim) and
  Stock Tokens (sim) are minted by the deployer; on the fork, balances come from real holders
  (the deepest Uniswap pools), also through impersonation.
- On a public testnet with simulated tokens, each actor is a throwaway key from `cast wallet new`
  (kept in the git-ignored state folder, mode 600) that signs real transactions. The deployer
  mints its tokens and sends it `sim.testnet_eth_per_actor` testnet ETH for gas.
"""

from __future__ import annotations

import json
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
from afterhours.deploy import cast_wallet_new, role_keys
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

    def address(self, label: str) -> str:
        return actor(label)

    def fund_eth(self, label_or_address: str, eth: float) -> None:
        address = label_or_address if label_or_address.startswith("0x") else actor(label_or_address)
        self.w3.provider.make_request("anvil_setBalance", [address, hex(int(eth * 1e18))])  # type: ignore[arg-type]

    def send(self, label: str, to: str, signature: str, *args: Any) -> str:
        return self.send_as(actor(label), to, signature, *args)

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


class SignedActors:
    """Actors with their own throwaway keys, for public testnets (no impersonation there)."""

    def __init__(self, cfg: AfterhoursConfig, w3: Web3, funder: Signer) -> None:
        self.w3 = w3
        self.funder = funder
        self.path = cfg.path(cfg.paths.state_dir) / f"testnet-actors-{cfg.active_profile}.json"
        self.keys: dict[str, str] = json.loads(self.path.read_text()) if self.path.exists() else {}

    def _signer(self, label: str) -> Signer:
        if label not in self.keys:
            self.keys[label] = cast_wallet_new()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.keys))
            self.path.chmod(0o600)
        return Signer(self.w3, self.keys[label])

    def address(self, label: str) -> str:
        return self._signer(label).address

    def fund_eth(self, label: str, eth: float) -> None:
        """Top the actor up to `eth` from the deployer."""
        who = self.address(label)
        need = int(eth * 1e18) - int(self.w3.eth.get_balance(who))  # type: ignore[arg-type]
        if need > 0:
            self.funder.transfer(who, need)

    def send(self, label: str, to: str, signature: str, *args: Any) -> str:
        return self._signer(label).send(to, signature, *args).tx_hash


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
        self.on_anvil = bool(cfg.profile.local_rpc_port_env)
        if not self.on_anvil and not self.sim_collateral:
            raise ValueError("off Anvil the seeder needs simulated tokens it can mint")
        self.actors: Anvil | SignedActors = (
            self.anvil if self.on_anvil else SignedActors(cfg, w3, self.owner)
        )
        self.eth_per_actor = (
            cfg.sim.eth_per_actor if self.on_anvil else cfg.sim.testnet_eth_per_actor
        )
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
            label = f"lender-{i}"
            who = self.actors.address(label)
            r = self.cfg.sim.lender_deposit_usdg
            amount = int(self.rng.uniform(r.low, r.high)) * 10**dec
            self.actors.fund_eth(label, self.eth_per_actor)
            self._give(loan, who, amount, "NVDA")  # on the fork, the NVDA/USDG pool also holds USDG
            self.actors.send(label, loan, "approve(address,uint256)", vault, amount)
            self.actors.send(label, vault, "deposit(uint256,address)(uint256)", amount, who)
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
                label = f"borrower-{m.symbol}-{m.tier}-{j}"
                who = self.actors.address(label)
                r = self.cfg.sim.borrower_ltv_share_of_lltv
                ltv = lltv * self.rng.uniform(r.low, r.high)
                borrow = int(per * unit)
                collateral = borrow * 10**36 // int(ltv * WAD) * WAD // int(price)
                self.actors.fund_eth(label, self.eth_per_actor)
                self._give(m.params[1], who, collateral, m.symbol)
                self.actors.send(label, m.params[1], "approve(address,uint256)", morpho, collateral)
                params = m.params
                self.actors.send(
                    label,
                    morpho,
                    f"supplyCollateral({PARAMS_TYPE},uint256,address,bytes)",
                    params,
                    collateral,
                    who,
                    b"",
                )
                self.actors.send(
                    label,
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
