# Weekend risk for AI agents

Robinhood announced AI trading agents whose Loops run a strategy around the clock, overnight
included, "coming soon to eligible U.S. customers" (docs/findings/robinhood-2026-09-29.md).
An agent acting while its owner sleeps needs to know when a Stock Token's price stops meaning
much. Afterhours serves that as read-only tools.

Nothing here can sign or send a transaction. The MCP server holds no key; the REST routes are
GET only (checked in tests against the OpenAPI schema).

## REST, versioned under /v1/agent/

| Route | Returns |
| --- | --- |
| `GET /v1/agent/market-status` | Session state (open, closed, holiday), next open and close, where feeds stand (regular, extended, closed), the start of the current shut stretch, Stock Tokens per price regime, a summary |
| `GET /v1/agent/weekend-risk/{ticker}` | Price regime and quality (docs/REGIME.md), the next closed period, its bad-case drop and alpha, the USDG Morpho markets and which cushions the drop passes, a one-paragraph summary |
| `GET /v1/agent/positions/{address}` | Every Stock Token Morpho loan: borrowed, loan token, LLTV, LTV, liquidation price, fall to liquidation, tonight's bad case and whether it reaches it, a summary |
| `GET /v1/agent/moves/{reason_id}` | A reason card from the vault's ledger, its RFC 8785 canonical JSON, the onchain verification, a summary |

- OpenAPI: `/openapi.json` (interactive at `/docs`), with response models for these routes.
- Rate limit: a token bucket per client, `agents.rate_limit_per_minute` (30) and
  `agents.rate_limit_burst` (10); over it, HTTP 429 with Retry-After. The client is
  X-Forwarded-For's last entry (Render's proxy appends the real address; `trusted_proxy_hops`).
- While a freshly started API reads its first board, live routes answer 503 with Retry-After.
- Code: `engine/afterhours/agents.py` (documents, summaries, limiter), routes in
  `engine/afterhours/api/app.py`. Tests: `engine/tests/test_agents.py`.

## MCP server (agents/, stdio)

`afterhours-mcp`, built on the official MCP Python SDK 2.3 (`MCPServer`, API checked with
Context7 and the SDK docs on 2026-10-04). Tools `market_status`, `get_weekend_risk`,
`check_position`, `explain_move`, each annotated `read_only_hint=True`,
`destructive_hint=False`, each a thin call to the route above. Errors reach the agent in plain
words (the SDK hides the text of other exceptions, so they are raised as `ToolError`).
Dependencies: the SDK only (HTTP through the standard library).

Install for Claude Desktop (also on the web app's Agents page, built from config):

```json
{
  "mcpServers": {
    "afterhours": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/bytes06runner/AfterHours#subdirectory=agents", "afterhours-mcp"],
      "env": { "AFTERHOURS_API_URL": "https://afterhours-api.onrender.com" }
    }
  }
}
```

Tests: `agents/tests/test_server.py` (tool list and read-only hints, calls through a stub API
including the "still reading" wait, plain errors, a real stdio subprocess).

### Why stdio and not streamable HTTP on the Render service

Measured on 2026-10-04: importing the SDK adds 25 MB to the API process; production peaked at
482 MB under load against Render free's 512 MB. Mounting it would leave about 5 MB, so the
server ships as a local stdio package that calls the hosted REST API instead.

## A real session

`agents/scripts/capture_example.py` starts the server exactly as the install steps do (`uvx`
from GitHub), calls all four tools against the hosted API and writes
`artifacts/agents/example-session.json`, served at `/v1/agents/example-session` and shown on
the Agents page. Captured 2026-10-04 15:02 UTC: all five calls answered without error. The
questions are examples; the tool calls and answers are real.
