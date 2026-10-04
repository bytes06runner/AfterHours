# Screen demo

A product walkthrough built from real sessions on the site. A script drives Chromium: the cursor
moves like a person's, every click is a real click, and every transaction is really sent. The
Remotion edit then adds the browser window, auto zoom on clicks, chapter cards and click sounds,
like Recordly or Screen Studio would. There is no voiceover; the cut leaves room for yours.

| Footage | Where it runs | Label in the video |
| --- | --- | --- |
| Landing page | the hosted site | Live site · the vault is a simulation |
| Risk board, position checker | the hosted site, reading Robinhood Chain mainnet | Live · Robinhood Chain mainnet, read-only |
| Deposit, closing bell, ledger | `make up` on a local chain (the only place a visitor wallet can deposit) | Simulation · local chain |
| Reason card verified, explorer | the hosted site's testnet ledger and the Robinhood Chain Testnet explorer | Robinhood Chain Testnet |
| Price regimes (landing panel, risk board column) | the hosted site, reading Robinhood Chain mainnet | Live · Robinhood Chain mainnet, read-only |
| Agents page and its real session | the hosted site and API | Live site · read-only tools, nothing can trade |
| Report card | the hosted site | Historical prices · simulated vault |

Waiting on the network is played faster, and the video says so ("7× speed, reading the
borrower's positions on mainnet").

## Rebuild it

1. Start the local stack: `DEMO_SKIP_SCENARIO=1 DEMO_SKIP_WEB=1 ./scripts/demo.sh`, and serve
   the web app with `next start -p 3100` (NEXT_PUBLIC_* from the local profile).
2. Record: `node scenes.mjs all` (or one scene: `node scenes.mjs checker`). The closing bell
   scene runs the scripted scenario, so record it on a fresh chain.
3. Make the clips: `node assemble.mjs` (writes `../animation/public/demo/*.mp4` and
   `../animation/src/demo/recordings.generated.json`).
4. Render: in `../animation`, `npx remotion render ScreenDemo out/afterhours-screen-demo.mp4`
   (`ScreenDemoSilent` has no sound effects). The cut itself lives in `src/demo/edit.ts`.

## Narration cue sheet (2:59)

Times are in the rendered video. Suggested lines are only a starting point; their numbers are in
`artifacts/report/numbers.json`.

| Time | On screen | Suggested line |
| --- | --- | --- |
| 0:00 | Title | "This is Afterhours, recorded on the real site." |
| 0:05 | Chapter 01, The front door | |
| 0:07 | Landing page, the exchange at night; scrolling the story | "Stock Tokens trade all weekend, but their price feeds follow the exchange: over 8 weekends, 32 of 35 posted nothing from Friday night to Sunday night." |
| 0:28 | Chapter 02, Frozen today, thin tomorrow | |
| 0:30 | "Frozen today, thin tomorrow", the four regime counts | "Robinhood has announced weekend trading, pending regulatory review. If the feeds follow it, weekend prices come from one venue and can be thin. So Afterhours reads every token's price regime, live." |
| 0:40 | The least trustworthy prices, one plain line zoomed | "Each price gets a quality score: how stale the feed is, how far the DEX has drifted, how much can be sold." |
| 0:44 | Click through to the risk board (sped up while it loads) | |
| 0:52 | The Price regime column, then Poor price quality | "Last Saturday all 35 were frozen; IONQ and RGTI had drifted 3.4% and 7.3% on the DEX." |
| 1:00 | Position checker, a live borrower (sped up while it reads) | "Anyone can check a real loan: how close it is to liquidation, and whether tonight's bad case would get there." |
| 1:16 | Chapter 03, A night in the vault | |
| 1:19 to 1:24 | Get test USDG, type 1000, Approve and deposit | "On a local chain, a visitor gets test USDG and deposits a thousand into the vault." |
| 1:38 | The closing bell scenario runs; the site turns to night | "Now the closing bell. Before an earnings night, the vault pulls META back to idle." |
| 1:52 | Ledger, the META card; Verify on chain, Matched onchain | "Every move is written down with its reason, and the browser checks its hash onchain." |
| 2:03 | Chapter 04, Every move, provable onchain | |
| 2:07 | Testnet ledger, Verify on chain, then the explorer | "The same bot runs on Robinhood Chain Testnet. Here is its allocation on the explorer." |
| 2:18 | Chapter 05, For agents | |
| 2:20 | The Agents page; Copy the Claude Desktop config | "Robinhood's trading agents will run strategies overnight. Any agent can read this risk through four read-only tools." |
| 2:32 | A real get_weekend_risk answer | "This is a real answer. The tools read; they cannot trade." |
| 2:39 | Chapter 06, The evidence | |
| 2:42 | Report card | "And the report card: the test we wrote down before running, and the result as recorded." |
| 2:52 | Outro: live site and GitHub | "Afterhours. Try it at the link below." |
