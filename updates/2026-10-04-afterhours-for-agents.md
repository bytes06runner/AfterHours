# Afterhours for AI agents

Robinhood's announced trading agents can run strategies around the clock, overnight included.
An agent acting while its owner sleeps needs to know when a Stock Token's price stops meaning
much, in a form it can read.

Afterhours now offers four read-only tools over MCP: is the market open, how risky is this
stock tonight, can this wallet be liquidated, and why did the vault move. The same data is plain
REST under /v1/agent with an OpenAPI schema and a rate limit. The MCP server is a small package
you add to Claude Desktop with one config block; it holds no key and cannot trade.

We checked the install end to end: the exact command from the README, started from GitHub,
answered all four tools against the live API. The session is on the new Agents page.
