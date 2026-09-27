# Demo video: recording runbook

Colosseum asks for a product demo of no more than three minutes. Target: 2 minutes 45 seconds.
Every number spoken or shown in the voice-over is in `artifacts/report/numbers.json`
(`make lint-numbers` checks this file).

Three sources, each labelled in the shot list:

- **LIVE**: the hosted site, https://after-hours-web-eta.vercel.app. Real time; the risk board
  and position checker read Robinhood Chain mainnet.
- **LOCAL**: the local stack (`make up`), a replayed week on a local chain. It is the only place
  a visitor's wallet can get test USDG: the "Get test USDG (sim)" button exists only on the local
  profile, and the hosted API refuses its faucet ("The faucet runs only on the local
  simulation", checked 2026-09-27). So the deposit and the closing-bell scenario are recorded
  here.
- **EXPLORER**: the Robinhood Chain Testnet explorer, for one real reallocation by the bot.

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
   7. https://after-hours-web-eta.vercel.app/report-card
4. **Wallet for the deposit (LOCAL).** A browser wallet (Brave Wallet, Rabby or MetaMask) with a
   fresh account that holds nothing real. You do not need to add the local chain by hand: the
   vault page's "Switch to" button adds it. The faucet button gives the account simulated USDG
   and gas.
5. **Terminal** beside the browser for shot 6, font large enough to read. Never show `.env` or
   any output with keys; the local demo needs none.
6. **Recordly.** Record the browser window (and the terminal for shot 6) at 1440 x 900 with the
   cursor visible. Record each shot as its own clip so a mistake costs one shot, not the take.

## Shot list

| # | Time | Source | Tab and clicks | Wait for | Voice over |
| --- | --- | --- | --- | --- | --- |
| 1 | 0:00 to 0:15 | LIVE | Tab 1, landing. Let the exchange sit; hover the ticker so it pauses | The ticker shows prices | "This is Afterhours, a lending vault for Robinhood Stock Tokens." |
| 2 | 0:15 to 0:35 | LIVE | Tab 2, risk board. Scroll the table slowly; click "Frozen now" | Rows with "Frozen for the weekend" or "Updating" | "Stock Tokens trade around the clock, but their price feeds follow the exchange. Over 8 weekends, 32 of 35 feeds posted nothing between Friday and Sunday night. This board reads every feed on Robinhood Chain mainnet, live." |
| 3 | 0:35 to 0:55 | LIVE | Tab 3, position checker. Click the first "Try a live borrower" address; scroll to the line starting "Tonight's bad case" | A position card | "Anyone can check a real loan: how close it is to liquidation, and whether tonight's bad case would get there." |
| 4 | 0:55 to 1:20 | LOCAL | Tab 4, vault. Click "Connect", pick your wallet; click "Switch to" if asked; click "Get test USDG (sim)"; type 1000 and click "Approve and deposit USDG"; approve in the wallet | "Received" notice, then your deposit in the panel | "Lenders deposit USDG. Each stock has three Morpho markets, at 91.5%, 86% and 77% loan-to-value, and lends in the riskiest one its last year of prices allows." |
| 5 | 1:20 to 1:30 | LOCAL | Tab 4, landing header: click "Preview the close" | The bell rings, the building goes to night | "Before every close, Afterhours forecasts each stock's bad case." |
| 6 | 1:30 to 1:55 | LOCAL | Terminal: `make scenario NAME=closing_bell`. Switch to tab 4 and keep the allocation board on screen | META's bar shrinks and its row flashes | "Now the closing bell. META reports next week; its bad case is far above the 10.4% line every market can take, so the bot pulls the money borrowers are not using. Money already lent stays." |
| 7 | 1:55 to 2:15 | LOCAL | Tab 5, ledger. Open the newest card; click "Verify on chain" | "Matched" | "Every move prints a reason: the rating, the forecast, the rule that fired. Its hash is written onchain, and the browser checks it." |
| 8 | 2:15 to 2:25 | EXPLORER | Tab 6. Point at From (the allocator), To (the vault) and the method | The transaction page | "The same bot runs on Robinhood Chain Testnet. This is one of its real reallocations." |
| 9 | 2:25 to 2:45 | LIVE | Tab 7, report card. Show the frontier chart, then scroll to the decision section | The chart | "On 2022 to 2026, with settings chosen on earlier years, Afterhours earned 9.12%, the same as the best fixed mix at 9.09%, with about half the bad debt. Historical stock prices, simulated vault. And we wrote the test down before running it; our first design earned less, so it did not ship." |

## Notes

- If the take runs long, cut shot 5 first, then shorten shot 3.
- Shot 4 amount: type 1000; it is typed on camera, not a claim.
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
