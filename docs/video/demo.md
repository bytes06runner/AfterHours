# Demo video: recording runbook

Colosseum asks for a product demo of no more than three minutes. Target: 2 minutes 45 seconds.
Every number spoken or shown in the voice-over is in `artifacts/report/numbers.json`
(`make lint-numbers` checks this file).

The story leads with "frozen today, thin tomorrow": Stock Token feeds freeze every weekend
today, and if Robinhood's announced weekend trading (pending regulatory review) reaches them,
weekend prices will come from one thin venue. Four sources, each labelled in the shot list:

- **LIVE**: the hosted site, https://after-hours-web-eta.vercel.app. Real time; the risk board
  and position checker read Robinhood Chain mainnet.
- **LOCAL**: the local stack (`make up`), a replayed week on a local chain. It is the only place
  a visitor's wallet can get test USDG: the "Get test USDG (sim)" button exists only on the local
  profile, and the hosted API refuses its faucet ("The faucet runs only on the local
  simulation", checked 2026-09-27). So the deposit and the closing-bell scenario are recorded
  here.
- **EXPLORER**: the Robinhood Chain Testnet explorer, for one real reallocation by the bot.
- **AGENT**: Claude Desktop (or any MCP client) with `afterhours-mcp` installed, calling the
  read-only tools against the hosted API.

Keep the Simulation banner visible in every product shot: it is part of the product.

## Before recording

1. **Local stack.** In a terminal in the repository folder, run `make up` and wait for
   "demo: running". The chain clock replays Tuesday 2025-04-22 at 13:00 New York with the
   exchange open; META reports earnings on 2025-04-30 after the close.
2. **Live site.** Open https://after-hours-web-eta.vercel.app/live once and wait until the table
   fills. The API may need up to a minute after it wakes; the page says "Reading every Stock
   Token price feed on mainnet" meanwhile.
3. **Browser.** One window at 1440 x 900, bookmarks bar hidden, no other tabs. Open these tabs in
   this order so each shot is one click away:
   1. https://after-hours-web-eta.vercel.app/
   2. https://after-hours-web-eta.vercel.app/live
   3. https://after-hours-web-eta.vercel.app/positions
   4. `http://localhost:3000/vault` (the local stack; another port if you set `WEB_PORT`)
   5. `http://localhost:3000/ledger`
   6. https://explorer.testnet.chain.robinhood.com/tx/0xb61dcb010b5c98f5edff731f764e2b5331e43f119e3405d4ab97ddaf25e5ad6e
   7. https://after-hours-web-eta.vercel.app/agents
   8. https://after-hours-web-eta.vercel.app/report-card
4. **Wallet for the deposit (LOCAL).** A browser wallet (Brave Wallet, Rabby or MetaMask) with a
   fresh account that holds nothing real. You do not need to add the local chain by hand: the
   vault page's "Switch to" button adds it. The faucet button gives the account simulated USDG
   and gas.
5. **Claude Desktop for shot 9 (AGENT).** Add the server from the Agents page ("Connect Claude
   Desktop in under a minute"), restart Claude Desktop, and check that the tools icon lists
   `afterhours` with four tools. Ask one throwaway question first so the hosted API is awake.
6. **Terminal** beside the browser for shot 6, font large enough to read. Never show `.env` or
   any output with keys; the local demo needs none.
7. **Recordly.** Record the browser window (and the terminal for shot 6) at 1440 x 900 with the
   cursor visible. Record each shot as its own clip so a mistake costs one shot, not the take.

## Shot list

| # | Time | Source | Tab and clicks | Wait for | Voice over |
| --- | --- | --- | --- | --- | --- |
| 1 | 0:00 to 0:12 | LIVE | Tab 1, landing. Let the exchange sit; hover the ticker so it pauses | The ticker shows prices | "This is Afterhours, a lending vault and risk layer for Robinhood Stock Tokens." |
| 2 | 0:12 to 0:35 | LIVE | Tab 1, scroll to "Frozen today, thin tomorrow". Rest on the four regime counts, then the least trustworthy prices | The counts and three lines | "Stock Tokens trade around the clock, but their price feeds follow the exchange. Over 8 weekends, 32 of 35 feeds posted nothing between Friday and Sunday night. Robinhood has announced weekend trading, pending regulatory review; if the feeds follow it, weekend prices will come from one venue and can be thin. So Afterhours reads every token's price regime, live." |
| 3 | 0:35 to 0:50 | LIVE | Tab 2, risk board. Point at the Price regime column; click "Poor price quality" | Rows with a regime badge and a price quality score | "Each price gets a quality score from how stale the feed is, how far the DEX has drifted from it, and how much can be sold. On Sunday, October 4th, all 35 were frozen; IONQ's and RGTI's DEX pools sat -3.4% and +7.3% from their feeds, in pools with $50 and $73 of depth, so thin they score as poor." |
| 4 | 0:50 to 1:05 | LIVE | Tab 3, position checker. Click the first "Try a live borrower" address | A position card | "Anyone can check a real loan: how close it is to liquidation, and whether tonight's bad case would get there." |
| 5 | 1:05 to 1:25 | LOCAL | Tab 4, vault. Click "Connect", pick your wallet; click "Switch to" if asked; click "Get test USDG (sim)"; type 1000 and click "Approve and deposit USDG"; approve in the wallet | "Received" notice, then your deposit in the panel | "Lenders deposit USDG. Each stock has three Morpho markets, at 91.5%, 86% and 77% loan-to-value, and lends in the riskiest one its last year of prices allows." |
| 6 | 1:25 to 1:50 | LOCAL | Terminal: `make scenario NAME=closing_bell`. Switch to tab 4 and keep the allocation board on screen | META's bar shrinks and its row flashes | "Now the closing bell. META reports next week; its bad case is far above the 10.4% line every market can take, so the bot pulls the money borrowers are not using. Money already lent stays." |
| 7 | 1:50 to 2:05 | LOCAL | Tab 5, ledger. Open the newest card; click "Verify on chain" | "Matched" | "Every move prints a reason, and its hash is written onchain. The browser checks it." |
| 8 | 2:05 to 2:12 | EXPLORER | Tab 6. Point at From (the allocator), To (the vault) and the method | The transaction page | "The same contracts are deployed on Robinhood Chain Testnet. This is the bot's first allocation there, from the seed cycle on September 27th." |
| 9 | 2:12 to 2:35 | AGENT | Claude Desktop: ask "Is NVDA safe to lend against this weekend?" Let it call `get_weekend_risk` (expand the tool call), then read the answer. Cut to tab 7, the Agents page | The tool call and its answer | "Robinhood's trading agents will run strategies overnight. Any agent can read this risk through four read-only MCP tools. They read; they cannot trade." |
| 10 | 2:35 to 2:55 | LIVE | Tab 8, report card. Show the frontier chart, then scroll to the decision section | The chart | "On 2022 to 2026, with settings chosen on earlier years, Afterhours earned 9.12%, the same as the best fixed mix at 9.09%, with about half the bad debt. Historical stock prices, simulated vault." |

The screen-demo recorder (`docs/video/screen-demo`, `node scenes.mjs regimes,agents`) records
shots 2, 3 and the Agents page part of 9 with zoom and click data; shot 9's Claude Desktop part is
recorded with Recordly.

## Notes

- If the take runs long, shorten shot 4 first, then shot 8.
- Shot 5 amount: type 1000; it is typed on camera, not a claim.
- Shots 2 and 3 are live: regime counts and scores change with the clock. The voice-over's
  numbers are from the dated snapshot (`artifacts/regime/`, Sunday 2026-10-04 10:34 UTC), so say
  the date as written, never "last Saturday".
- Shot 9: if the hosted API was asleep, the first tool call can take about a minute; ask the
  throwaway question before recording.
- Shot 6: the scenario steps through the pre-close checks of 2025-04-22, 04-23 and 04-24; META
  is pulled at the third. Keep the vault on screen while it runs.
- Shot 8: the transaction is the allocator's first `allocate` call on the testnet vault
  (`deployments/rh-testnet.json`), from the seed cycle on 2026-09-27. Do not click through to
  other addresses.
- Local and live show different clocks: the local stack replays April 2025, the live site uses
  today. That is expected; each shot carries its own banner.
- A testnet deposit from your own wallet is not possible from the site (no faucet there). If you
  want one on camera anyway, ask for a one-time mint of simulated USDG from the testnet deployer
  to your wallet; it is not needed for this video.
