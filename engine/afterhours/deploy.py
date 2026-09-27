"""`afterhours deploy`: plan, run the Foundry script, finalise `deployments/<profile>.json`.

The plan is built from config and the discovered file, so the Solidity script holds no
addresses or parameters of its own. Keys come from the environment (`DEPLOYER_PK`, ...). For
the local and fork profiles only, missing keys are replaced by throwaway keys made with
`cast wallet new` and kept in `data/cache/throwaway-keys.json` (git-ignored, never printed).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eth_utils import keccak, to_checksum_address

from afterhours.config import REPO_ROOT, AfterhoursConfig
from afterhours.deployments import deployment_path, load_discovered
from afterhours.policy.lp import tier_spec

ZERO = "0x" + "0" * 40
WAD = 10**18
ROLES = ("DEPLOYER_PK", "CURATOR_PK", "ALLOCATOR_PK", "GUARDIAN_PK")
LOCAL_PROFILES_FOR_THROWAWAY_KEYS = ("local", "fork")


def plan(cfg: AfterhoursConfig, profile: str) -> dict[str, Any]:
    """Deployment plan for `profile`."""
    prof = cfg.profiles[profile]
    discovered = load_discovered(cfg, profile) or load_discovered(cfg, "fork")
    core = discovered.get("core", {})
    selected = list(discovered.get("selected", []))
    stocks = discovered.get("stock_tokens", {})
    reuse = prof.morpho_source == "discovered"
    sim_collateral = prof.collateral_mode == "simulated"

    def addr(key: str) -> str:
        return str(core[key]["address"]) if reuse and key in core else ZERO

    lltv = cfg.morpho.lltv_tiers
    if lltv.weekday is None or lltv.weekend is None:
        raise ValueError("morpho.lltv_tiers must be set (M4) before deploying")
    usdg = addr("usdg") if not sim_collateral else ZERO
    return {
        "profile": profile,
        "self_deploy_morpho": not reuse,
        "sim_oracle": prof.oracle_mode == "simulated",
        "sim_collateral": sim_collateral,
        "morpho": {
            "blue": addr("morpho_blue"),
            "irm": addr("adaptive_curve_irm"),
            "vault_v2_factory": addr("vault_v2_factory"),
            "adapter_factory": addr("market_v1_adapter_v2_factory"),
            "oracle_factory": addr("chainlink_oracle_v2_factory"),
        },
        "loan_token": {"address": usdg, "decimals": 6},
        "tiers": {
            "names": [n for n, _ in lltv.ordered()],
            "lltvs_wad": [str(round(v * WAD)) for _, v in lltv.ordered()],
        },
        "tokens": {
            "symbols": selected,
            "addresses": [stocks[s]["address"] if not sim_collateral else ZERO for s in selected],
            "feeds": [stocks[s]["feed"]["address"] for s in selected],
            "decimals": [18 for _ in selected],
            # Starting price for simulated oracles: the last Chainlink answer seen in M1.
            "initial_prices_8": [
                round(float(stocks[s]["feed"]["latest_answer"]) * 1e8) for s in selected
            ],
        },
        "vault": {
            "name": cfg.vault.name,
            "symbol": cfg.vault.symbol,
            "performance_fee_wad": str(cfg.vault.performance_fee_bps * 10**14),
            "timelock_seconds": cfg.vault.timelock_seconds or 0,
            "market_cap_assets": str(round(cfg.vault.market_cap_usdg * 10**6)),
            "collateral_relative_cap_wad": str(round(cfg.vault.max_share_per_stock * WAD)),
        },
        "salt": "0x" + keccak(text=f"afterhours:{profile}:{cfg.vault.symbol}").hex(),
    }


def cast_wallet_new() -> str:
    """A fresh throwaway private key from `cast wallet new` (never logged)."""
    out = subprocess.run(
        ["cast", "wallet", "new", "--json"], capture_output=True, text=True, check=True
    )
    doc = json.loads(out.stdout)
    # Foundry 1.8 wraps the result in {"data": [...], ...}.
    wallet = (doc.get("data") or doc) if isinstance(doc, dict) else doc
    key: str = (wallet[0] if isinstance(wallet, list) else wallet)["private_key"]
    return key


def _env_value(line: str, name: str) -> str | None:
    """The value of `name` on this .env line (quotes stripped), or None if it is another line."""
    m = re.match(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=(.*)$", line)
    return m.group(1).strip().strip("'\"") if m else None


def write_testnet_keys(env_path: Path, new_key: Callable[[], str] | None = None) -> dict[str, str]:
    """Make one key per role and write them into `env_path`; return {role: address} only.

    Refuses (KeyError naming the roles, never the values) if any role already has a value, so
    no key is ever overwritten. Empty `ROLE=` lines (from .env.example) are filled in place;
    missing ones are appended. The file is replaced atomically and left readable by you only.
    """
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    taken = [r for r in ROLES if any(_env_value(line, r) for line in lines)]
    if taken:
        raise KeyError(
            f"{', '.join(taken)} already set in {env_path.name}; not overwriting any key"
        )
    make = new_key or cast_wallet_new
    keys = {role: make() for role in ROLES}
    for role, key in keys.items():
        at = next((i for i, line in enumerate(lines) if _env_value(line, role) == ""), None)
        if at is None:
            lines.append(f"{role}={key}")
        else:
            lines[at] = f"{role}={key}"
    fd, tmp = tempfile.mkstemp(dir=env_path.parent, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:  # mkstemp creates the file readable by you only
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, env_path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return addresses(keys)


def _throwaway_keys(cfg: AfterhoursConfig) -> dict[str, str]:
    """Throwaway keys from `cast wallet new`, cached; only for local and fork profiles."""
    path = cfg.path(cfg.data.cache_dir) / "throwaway-keys.json"
    if path.exists():
        keys: dict[str, str] = json.loads(path.read_text())
        return keys
    keys = {role: cast_wallet_new() for role in ROLES}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keys))
    path.chmod(0o600)
    return keys


def role_keys(
    cfg: AfterhoursConfig, profile: str, roles: tuple[str, ...] = ROLES
) -> dict[str, str]:
    """Private keys for `roles` from the environment, or throwaway keys on local chains.

    Ask only for the roles you sign with: the hosted bot needs ALLOCATOR_PK alone, so the
    deployer, curator and guardian keys never have to be on the server.
    """
    env = {r: os.environ.get(r, "") for r in roles}
    if all(env.values()):
        return env
    if profile not in LOCAL_PROFILES_FOR_THROWAWAY_KEYS:
        missing = ", ".join(r for r, v in env.items() if not v)
        raise KeyError(f"set {missing} in .env (throwaway keys from `cast wallet new`)")
    return {r: k for r, k in _throwaway_keys(cfg).items() if r in roles}


def addresses(keys: dict[str, str]) -> dict[str, str]:
    """Public addresses for role keys (no key material leaves this function)."""
    from eth_account import Account

    return {r: to_checksum_address(Account.from_key(k).address) for r, k in keys.items()}


def fund_local(rpc: str, accounts: list[str], wei: int) -> None:
    """Give accounts ETH on an Anvil node (anvil_setBalance)."""
    for a in accounts:
        subprocess.run(
            ["cast", "rpc", "anvil_setBalance", a, hex(wei), "--rpc-url", rpc],
            check=True,
            capture_output=True,
        )


def top_up(
    balance_of: Callable[[str], int],
    send: Callable[[str, int], object],
    address: str,
    target_wei: int,
) -> int:
    """Send `address` what it lacks to reach `target_wei`; returns the wei sent (0 if enough)."""
    lacking = target_wei - balance_of(address)
    if lacking <= 0:
        return 0
    send(address, lacking)
    return lacking


def top_up_curator(cfg: AfterhoursConfig, rpc: str, keys: dict[str, str]) -> int:
    """Before a real-chain deploy: the curator signs the curation transactions, so the deployer
    tops it up to `funding.curator_eth` (only what it lacks)."""
    from afterhours.chain.rpc import connect
    from afterhours.chain.tx import Signer

    w3 = connect(rpc)
    deployer = Signer(w3, keys["DEPLOYER_PK"])
    curator = addresses({"CURATOR_PK": keys["CURATOR_PK"]})["CURATOR_PK"]
    return top_up(
        lambda a: int(w3.eth.get_balance(to_checksum_address(a))),
        deployer.transfer,
        curator,
        int(cfg.funding.curator_eth * 10**18),
    )


def run_script(
    cfg: AfterhoursConfig,
    profile: str,
    plan_path: Path,
    out_path: Path,
    rpc: str,
    keys: dict[str, str],
) -> None:
    """Run the Foundry deploy script with the plan and keys in its environment."""
    env = {**os.environ, **keys, "PLAN_PATH": str(plan_path), "DEPLOYMENT_PATH": str(out_path)}
    subprocess.run(
        [
            "forge",
            "script",
            "script/DeployAfterhours.s.sol:DeployAfterhours",
            "--rpc-url",
            rpc,
            "--broadcast",
            "--slow",
            "-vv",
        ],
        cwd=REPO_ROOT / "contracts",
        env=env,
        check=True,
    )


def finalise(
    cfg: AfterhoursConfig, profile: str, raw_path: Path, plan_doc: dict[str, Any]
) -> dict[str, Any]:
    """Reshape the script output into `deployments/<profile>.json` with tier metadata."""
    raw = json.loads(raw_path.read_text())
    lltv = cfg.morpho.lltv_tiers
    tiers = {}
    for name, value in lltv.ordered():
        spec = tier_spec(name, float(value))
        tiers[name] = {
            "lltv": spec.lltv,
            "liquidation_allowance_b": spec.allowance,
            "cushion": spec.cushion,
            "formula": "b = LLTV * (min(1.15, 1/(1 - 0.3*(1 - LLTV))) - 1), verified in M1",
        }
    markets = [
        {
            "symbol": sym,
            "tier": tier,
            "market_id": mid,
            "collateral": col,
            "oracle": orc,
            "lltv_wad": str(lv),
            "loan_token": raw["loan_token"],
            "irm": raw["irm"],
        }
        for sym, tier, mid, col, orc, lv in zip(
            raw["market_symbols"],
            raw["market_tiers"],
            raw["market_ids"],
            raw["market_collateral"],
            raw["market_oracles"],
            raw["market_lltvs"],
            strict=True,
        )
    ]
    doc = {
        "profile": profile,
        "chain_id": raw["chain_id"],
        "deployed_at_block": raw["block"],
        "simulation": {
            "oracle": plan_doc["sim_oracle"],
            "collateral": plan_doc["sim_collateral"],
            "morpho_self_deployed": plan_doc["self_deploy_morpho"],
        },
        "morpho": {"address": raw["morpho"]},
        "irm": {"address": raw["irm"]},
        "vault_v2_factory": {"address": raw["vault_v2_factory"]},
        "adapter_factory": {"address": raw["adapter_factory"]},
        "loan_token": {"address": raw["loan_token"]},
        "vault": {"address": raw["vault"]},
        "adapter": {"address": raw["adapter"]},
        "registry": {"address": raw["registry"]},
        "roles": {
            "owner": raw["owner"],
            "curator": raw["curator"],
            "allocator": raw["allocator"],
            "guardian": raw["guardian"],
        },
        "tiers": tiers,
        "markets": markets,
    }
    deployment_path(cfg, profile).write_text(json.dumps(doc, indent=2) + "\n")
    return doc
