"""Afterhours as MCP tools: read-only weekend risk for Robinhood Stock Tokens.

Four tools, each a thin call to the Afterhours REST API (`/v1/agent/*`, docs/AGENTS.md):

- market_status()            session state, next open and close, where feeds stand;
- get_weekend_risk(ticker)   regime, price quality, next closed period, bad case, a summary;
- check_position(address)    every Stock Token Morpho loan of an address vs tonight's bad case;
- explain_move(reason_id)    a reason card from the vault's ledger and its onchain check.

Nothing here can sign or send a transaction: the server holds no key and the API it calls has
no write endpoint for these tools. Configure with environment variables:

- AFTERHOURS_API_URL (required): the API's base URL, for example the hosted one in the README;
- AFTERHOURS_TIMEOUT_SECONDS (optional, default 90): how long one tool call may take, including
  waiting while a freshly started API reads its first risk board.

Run: `afterhours-mcp` (stdio). Standard library only besides the MCP SDK.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

__all__ = ["main", "mcp"]

INSTRUCTIONS = (
    "Afterhours reads Robinhood Stock Token risk on Robinhood Chain mainnet, read-only. Stock "
    "Tokens trade around the clock but their price feeds follow the US exchange: inside the "
    "weekend window (Friday 20:00 to Sunday 20:00 New York) they have posted nothing in every "
    "weekend measured so far. Use market_status first, then get_weekend_risk for a ticker or "
    "check_position for a wallet. Each answer has a plain-English summary; quote it rather than "
    "restating numbers. Nothing here is financial advice and nothing here can trade."
)

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
TICKER = re.compile(r"^[A-Za-z.]{1,10}$")

mcp = MCPServer("afterhours", instructions=INSTRUCTIONS)


class AfterhoursError(ToolError):
    """An error the agent should see in plain words (the SDK hides other exceptions' text)."""


def _base() -> str:
    url = os.environ.get("AFTERHOURS_API_URL", "").strip().rstrip("/")
    if not url:
        raise AfterhoursError(
            "AFTERHOURS_API_URL is not set. Set it to the Afterhours API base URL in this "
            "server's environment (see the Agents page or docs/AGENTS.md)."
        )
    return url


def _get(path: str) -> dict[str, Any]:
    """GET a JSON document, waiting politely while the API says it is still reading."""
    deadline = time.monotonic() + float(os.environ.get("AFTERHOURS_TIMEOUT_SECONDS", "90"))
    url = _base() + path
    while True:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "afterhours-mcp/0.1"}
        )
        try:
            remaining = max(1.0, deadline - time.monotonic())
            with urllib.request.urlopen(req, timeout=remaining) as res:
                doc: dict[str, Any] = json.loads(res.read().decode())
                return doc
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode()).get("detail", "")
            except (ValueError, AttributeError):
                detail = ""
            retry = exc.headers.get("Retry-After")
            wait = float(retry) if retry and retry.replace(".", "").isdigit() else 5.0
            if exc.code == 503 and time.monotonic() + wait < deadline:
                time.sleep(wait)  # a freshly started API is reading its first board
                continue
            if exc.code == 429:
                raise AfterhoursError(
                    f"Rate limited by the Afterhours API; retry in {wait:.0f} s."
                ) from exc
            raise AfterhoursError(
                detail or f"The Afterhours API answered HTTP {exc.code}."
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AfterhoursError(f"Can't reach the Afterhours API at {_base()}: {exc}") from exc


@mcp.tool(annotations=READ_ONLY)
def market_status() -> dict[str, Any]:
    """Is the US stock exchange open, when it next opens and closes, whether Stock Token price
    feeds are posting or inside their weekend shut stretch, and how many Stock Tokens are in
    each price regime (regular, extended, weekend price, frozen)."""
    return _get("/v1/agent/market-status")


@mcp.tool(annotations=READ_ONLY)
def get_weekend_risk(ticker: str) -> dict[str, Any]:
    """Weekend and overnight risk for one Robinhood Stock Token (for example NVDA, TSLA, SPY):
    its price regime and price quality score, the next closed period, the calibrated bad-case
    drop for it (the forecast targets 1% of closed periods; the answer also gives how often such
    falls were beaten on held-out years for that kind of period, more often on weekends and
    holidays than the target), which
    USDG Morpho markets' cushions that drop passes, and a one-paragraph plain-English summary."""
    if not TICKER.match(ticker.strip()):
        raise AfterhoursError(f"{ticker!r} does not look like a ticker, such as NVDA.")
    return _get("/v1/agent/weekend-risk/" + urllib.parse.quote(ticker.strip().upper()))


@mcp.tool(annotations=READ_ONLY)
def check_position(address: str) -> dict[str, Any]:
    """Every Morpho loan against a Robinhood Stock Token held by a wallet address on Robinhood
    Chain mainnet: amount borrowed, LTV, liquidation price, the fall needed to reach it, and
    whether tonight's bad case reaches it. Reads public data only."""
    if not ADDRESS.match(address.strip()):
        raise AfterhoursError(f"{address!r} is not a 0x address (40 hex characters).")
    return _get("/v1/agent/positions/" + address.strip())


@mcp.tool(annotations=READ_ONLY)
def explain_move(reason_id: str) -> dict[str, Any]:
    """Why the Afterhours vault made a move: the reason card the bot wrote, its canonical JSON,
    and whether its hash matches the ReasonLogged event onchain. Reason ids are listed on the
    ledger page and in GET /v1/reasons."""
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", reason_id.strip()):
        raise AfterhoursError(f"{reason_id!r} is not a reason id (a UUID from the ledger).")
    return _get("/v1/agent/moves/" + reason_id.strip())


def main() -> None:
    """Run over stdio (what Claude Desktop and most MCP clients start)."""
    mcp.run()


if __name__ == "__main__":
    main()
