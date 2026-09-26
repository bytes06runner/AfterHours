# Demo video: script and shot list

Colosseum asks for a product demo of no more than three minutes explaining how the product
works. Target: 2 minutes 45 seconds. Every number spoken or shown is in
`artifacts/report/numbers.json` (`make lint-numbers` checks this file).

## Before recording

1. `make up` and wait for "demo: running". The chain clock replays Tuesday 2025-04-22 at 13:00
   New York, with the exchange open. META reports earnings on 2025-04-30 after the close.
2. Browser at 1440 x 900, light system theme, `http://localhost:$WEB_PORT`. Close other tabs;
   hide bookmarks.
3. A terminal beside the browser, font large enough to read, in the repository folder.
4. Keep the Simulation banner visible in every shot: it is part of the product.

## Shot list

| # | Time | Screen | Action | Voice over |
| --- | --- | --- | --- | --- |
| 1 | 0:00 to 0:15 | Landing, day | Let the exchange sit for a beat; hover the ticker so it pauses | "This is Afterhours, a lending vault for Robinhood Stock Tokens. The market is open." |
| 2 | 0:15 to 0:30 | Landing | Press "Preview the close"; let the bell ring and the building go to night | "When the exchange closes, Stock Tokens keep trading but their price feeds stop. Over 8 weekends, 32 of 35 feeds posted nothing between Friday and Sunday night." |
| 3 | 0:30 to 0:55 | Vault | Press "Get test USDG (sim)", then deposit 1,000 USDG <!-- numbers-ok: an amount typed on camera --> | "Lenders deposit USDG. Each stock has three Morpho markets, at 91.5%, 86% and 77% loan-to-value, and lends in the riskiest one its last year of prices allows." |
| 4 | 0:55 to 1:15 | Vault, allocation board | Point at META's bar in the 91.5% column, then the hatched part, then the idle reservoir | "Brass is what the vault supplies; hatched is what borrowers are using. Some cash stays idle so withdrawals always work." |
| 5 | 1:15 to 1:35 | Almanac | Scroll to META; point at its earnings night above the red line; click META | "Before every close, Afterhours forecasts each stock's bad case. META reports next week, and that night's bad case is far above the 10.4% line that every market can take." |
| 6 | 1:35 to 2:00 | Terminal, then Vault | Run `make scenario NAME=closing_bell`; switch to the vault and watch META's bar shrink and its row flash | "Now the closing bell. From Thursday's close, META's earnings night is inside the five closes the bot looks ahead, so it pulls the money borrowers are not using. Money already lent stays." |
| 7 | 2:00 to 2:20 | Ledger | Open the newest telegram; press "Verify on chain" | "Every move prints a reason: the rating, the forecast, the rule that fired. Its hash is written onchain, and the browser checks it. Matched." |
| 8 | 2:20 to 2:35 | Report card | Show the frontier chart | "On 2022 to 2026, with settings chosen on earlier years, Afterhours earned 9.12%, the same as the best fixed mix at 9.09%, with about half the bad debt. Historical stock prices, simulated vault." |
| 9 | 2:35 to 2:45 | Report card | Show the decision section | "And we wrote the test down before running it. Our first design had less loss but earned less, so it did not ship. Everything is on GitHub." |

## Notes

- If a shot runs long, cut shot 4 first, then shot 9.
- Shot 6: the closing-bell scenario steps through the pre-close checks of 2025-04-22, 04-23 and
  04-24; META is pulled at the third. Keep the vault on screen while it runs.
- Do not show `.env` or any terminal output with keys. The local demo needs none.
