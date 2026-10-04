"""The public, secret-free slice of configuration served to the web app.

Served by `GET /v1/config/public` and printed by `afterhours config public`.
The web app parses it with the zod schema in `web/src/lib/config.ts`; keep both in step.
"""

from __future__ import annotations

from typing import Any

from afterhours.config import AfterhoursConfig
from afterhours.deployments import load_deployment, load_discovered


def public_config(cfg: AfterhoursConfig) -> dict[str, Any]:
    """Build the public config document for the active profile."""
    profile = cfg.profile
    chain = cfg.chain
    return {
        "profile": cfg.active_profile,
        "chain": {
            "key": profile.chain,
            "name": chain.name,
            "native_currency": chain.native_currency.model_dump(),
            "chain_id": chain.chain_id,
            "faucet_url": chain.faucet_url,
            "explorer_url": chain.explorer_url,
            "rpc_url": browser_rpc(cfg),
        },
        "simulation": {
            "oracle": profile.oracle_mode == "simulated",
            "collateral": profile.collateral_mode == "simulated",
        },
        "vault": {"name": cfg.vault.name, "symbol": cfg.vault.symbol},
        "live": {
            "network": cfg.chains[cfg.profiles[cfg.live.profile].chain].name,
            "explorer_url": cfg.chains[cfg.profiles[cfg.live.profile].chain].explorer_url,
        },
        "analytics": {
            "script_src": cfg.web.analytics.script_src,
            "endpoint_domain": cfg.web.analytics.endpoint_domain,
        },
        "agents": {
            "mcp_source": cfg.agents.mcp_source,
            "mcp_command": cfg.agents.mcp_command,
            "api_url_env": cfg.agents.api_url_env,
            "rate_limit_per_minute": cfg.agents.rate_limit_per_minute,
        },
        "exchange_calendar": cfg.data.exchange_calendar,
        "schedule": {
            "hourly": cfg.schedule.hourly,
            "pre_close_minutes": cfg.schedule.pre_close_minutes,
            "post_open_minutes": cfg.schedule.post_open_minutes,
            "lookahead_closed_periods": cfg.policy.lookahead_closed_periods,
        },
        "deployment": load_deployment(cfg),
        "discovered": _addresses_only(load_discovered(cfg)),
    }


def browser_rpc(cfg: AfterhoursConfig) -> str | None:
    """An RPC the browser may use: the local node on fork and local profiles, else the chain's
    public RPC. Never the RPC from .env, which may carry an API key."""
    if cfg.profile.local_rpc_port_env:
        try:
            return cfg.node_url()
        except KeyError:
            return None
    return cfg.chain.public_rpc_url


def _addresses_only(discovered: dict[str, Any]) -> dict[str, Any]:
    """Strip evidence blobs; the web needs addresses, not verification logs."""
    out: dict[str, Any] = {}
    for key, value in discovered.items():
        if isinstance(value, dict) and "address" in value:
            out[key] = value["address"]
        elif isinstance(value, dict):
            nested = _addresses_only(value)
            if nested:
                out[key] = nested
    return out
