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
| Replay, report card | the hosted site | Historical prices · simulated vault |

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

## Narration cue sheet (2:56)

Times are in the rendered video. Suggested lines are only a starting point.

| Time | On screen | Suggested line |
| --- | --- | --- |
| 0:00 | Title | "This is Afterhours, recorded on the real site." |
| 0:05 | Chapter 01, The front door | |
| 0:07 | Landing page, exchange clock | "Stock Tokens trade all weekend, but their price feeds follow the stock exchange." |
| 0:14 to 0:25 | Scrolling the story: the gap chart, the yield table | "When the market reopens, a price can gap past a lending market's cushion, and lenders take the loss." |
| 0:28 | Click: Preview the close | "Preview the close shows what the site looks like when the bell rings." |
| 0:37 | Chapter 02, Live risk | |
| 0:40 | Click: Risk board | "The risk board reads every Stock Token price feed straight from Robinhood Chain mainnet." |
| 0:47 to 0:52 | Filters: Frozen now, Beyond a cushion tonight, All stocks | "Filter by feeds frozen right now, or by stocks whose bad case tonight is beyond a market's cushion." |
| 0:58 | Position checker | "Paste any wallet, or try a live borrower." |
| 1:00 | Click: a live borrower (sped up while it reads mainnet) | |
| 1:05 | The result: the loan, the liquidation price, tonight's bad case | "It shows how close this loan is to liquidation, and whether tonight's bad case would get there." |
| 1:14 | Chapter 03, A night in the vault | |
| 1:19 to 1:24 | Get test USDG, type 1000, Approve and deposit | "On a local chain, a visitor gets test USDG and deposits a thousand into the vault." |
| 1:32 | Deposited 1,000.00 USDG | |
| 1:38 | The closing bell scenario runs; the site turns to night | "Now we ring the closing bell. Before an earnings night, the vault pulls META back to idle." |
| 1:48 | META: pulled back tonight | |
| 1:52 | Click: Ledger, the META pullback card | "Every move is written down with its reason." |
| 1:59 | Click: Verify on chain, Matched onchain | "Verify hashes the reason in your browser and matches it to the record onchain." |
| 2:03 | Chapter 04, Every move, provable onchain | |
| 2:08 | Testnet ledger, Verify on chain | "The same bot runs on Robinhood Chain Testnet." |
| 2:12 to 2:22 | The transaction on the testnet explorer | "Here is that allocation on the explorer: from the allocator, successful." |
| 2:22 | Chapter 05, The evidence | |
| 2:26 | Click: Replay this night (META, October 2022) | "Replay the worst real nights: a vault that always lends at the weekday tier against Afterhours." |
| 2:36 | Click: Report card | "The report card: rules written before the test, and the result as recorded." |
| 2:49 | Outro: live site and GitHub | "Afterhours. Try it at the link below." |
