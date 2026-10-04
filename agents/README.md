# afterhours-mcp

Read-only weekend risk for Robinhood Stock Tokens, as MCP tools. A small stdio server that
calls the Afterhours API; it holds no key and cannot sign or send a transaction.

| Tool | Answers |
| --- | --- |
| `market_status()` | Is the exchange open, next open and close, whether Stock Token feeds are posting, Stock Tokens per price regime |
| `get_weekend_risk(ticker)` | Price regime, price quality, next closed period, bad-case drop, which USDG Morpho markets' cushions it passes, a plain-English paragraph |
| `check_position(address)` | Every Stock Token Morpho loan of a wallet: borrowed, LTV, liquidation price, whether tonight's bad case reaches it |
| `explain_move(reason_id)` | A reason card from the vault's ledger and whether its hash matches the onchain event |

## Install (needs uv)

Claude Desktop: Settings, Developer, Edit Config, then add to `claude_desktop_config.json`:

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

Restart Claude Desktop. Any other MCP client: run the same command over stdio with the same
environment variable.

From a clone: `uv run --package afterhours-mcp afterhours-mcp` with `AFTERHOURS_API_URL` set
(for a local API, `http://127.0.0.1:8000`).

## Settings

- `AFTERHOURS_API_URL` (required): the Afterhours API base URL.
- `AFTERHOURS_TIMEOUT_SECONDS` (default 90): longest wait for one call. The hosted API sleeps
  when idle; the first call after a sleep can take about a minute while it wakes and reads the
  board.

The same data is plain REST at `/v1/agent/*` (OpenAPI at `/openapi.json`), rate limited per
client. Not financial advice.
