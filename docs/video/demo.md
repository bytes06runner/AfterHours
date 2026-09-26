# Demo video: script and shot list

Colosseum asks for a product demo of no more than three minutes explaining how the product
works. Target: 2 minutes 45 seconds. Every number spoken or shown is in
`artifacts/report/numbers.json` (`make lint-numbers` checks this file).

## Before recording

1. `make up` and wait for "demo: running". The chain clock starts on Tuesday 2026-08-18 at
   13:00 New York, with the exchange open.
2. Browser at 1440 x 900, zoom 100% <!-- numbers-ok: browser setting -->, light system theme, `http://localhost:$WEB_PORT`. Close
   other tabs; hide bookmarks.
3. A terminal beside the browser, font large enough to read, in the repository folder.
4. Keep the Simulation banner visible in every shot: it is part of the product.

## Shot list

| # | Time | Screen | Action | Voice over |
| --- | --- | --- | --- | --- |
| 1 | 0:00 to 0:15 | Landing, day | Let the exchange sit for a beat; hover the ticker so it pauses | "This is Afterhours, a lending vault for Robinhood Stock Tokens. The market is open, so lending runs at full speed." |
| 2 | 0:15 to 0:30 | Landing | Press "Preview the close"; let the bell ring and the building go to night | "When the exchange closes, Stock Tokens keep trading but their price feeds stop. Over 8 weekends, 32 of 35 feeds posted nothing between Friday and Sunday night." |
| 3 | 0:30 to 0:55 | Vault | Open the vault. Press "Get test USDG (sim)", then deposit 1,000 USDG <!-- numbers-ok: an amount typed on camera --> | "Lenders deposit USDG. The vault lends it to borrowers in two Morpho markets per stock: a weekday tier at 91.5% loan-to-value, and a weekend tier at 77.0%." |
| 4 | 0:55 to 1:15 | Vault, allocation board | Point at the hatched part of a bar, then the idle reservoir | "Brass is what the vault supplies; hatched is what borrowers are using. Some cash stays idle so withdrawals always work." |
| 5 | 1:15 to 1:35 | Almanac | Scroll the spread; click NVDA and show the gauge | "Before every close, Afterhours forecasts each stock's bad-case drop. NVDA reports earnings next week, so its bad case jumps past both tiers' limits." |
| 6 | 1:35 to 2:00 | Terminal, then Vault | Run `make scenario NAME=closing_bell`; switch to the vault and watch the bars move and a row flash | "Now the closing bell. The bot sees a weekday-tier stock whose bad case no longer fits the 6.1% cushion, and moves the money borrowers are not using to the weekend tier." |
| 7 | 2:00 to 2:20 | Ledger | Open the newest telegram; press "Verify on chain" | "Every move prints a reason: the forecast, what drove it, the rule that fired. Its hash is written onchain, and the browser checks it. Matched." |
| 8 | 2:20 to 2:35 | Replay | Show the META night; press "Replay this night" | "On real history: when META fell 24.5% after earnings in 2022, a vault always in the weekday tier would have lost 24,300 USDG. Afterhours, 2,228." |
| 9 | 2:35 to 2:45 | Report card | Show the first sentence and the backtest table | "The report card is honest about what worked: our machine learning model lost to a simple baseline, so the baseline ships. Everything here is on GitHub." |

## Notes

- If a shot runs long, cut shot 4 first, then shot 9's second sentence.
- Shot 6 depends on the scripted week: the closing-bell scenario steps to the next pre-close
  checks until the bot moves money. If nothing moves on the first step, keep the vault on screen;
  the next step follows within seconds.
- Do not show `.env` or any terminal output with keys. The local demo needs none.
