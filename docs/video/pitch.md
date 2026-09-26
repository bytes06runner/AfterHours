# Pitch video: script and shot list

Colosseum asks for a two-to-three-minute presentation video and says judges review it first.
Target: 2 minutes 30 seconds. Numbers come from `artifacts/report/numbers.json`
(`make lint-numbers`). Lines marked TEAM are yours to fill in: we do not write quotes,
traction or backgrounds we have not got.

## Script

**1. The hook (0:00 to 0:20).** Speaker on camera, then the landing page at night.

> Stock Tokens on Robinhood Chain trade all weekend. Their price feeds do not. We read every
> update of the 35 Stock Token feeds over 8 weekends: 32 posted nothing from Friday night to
> Sunday night. A lending market cannot liquidate anyone while its prices are frozen.

**2. The problem (0:20 to 0:50).** The gap histogram from the landing story, then the two-setting
chart.

> So when trading resumes, prices gap. Across 523 US stocks and funds since 2010, 2.1% of
> earnings nights opened 10% or more down. Lenders have two bad choices. Lend at a high limit all
> the time and, in our backtest, the gaps cost 108,748 USDG on a 2,000,000 USDG vault. Lend at a
> safe limit all the time and you earn 6.85% instead of 8.84%.

**3. The product (0:50 to 1:25).** The closing bell, the allocation board moving, a telegram,
"Verify on chain".

> Afterhours does both, at the right times. It is a Morpho vault with two markets per stock: a
> weekday tier at 91.5% loan-to-value and a weekend tier at 77.0%. Before every close it
> forecasts each stock's bad-case drop, and moves the money borrowers are not using out of any
> market whose cushion does not cover it. Every move writes its reason onchain, and anyone can
> check it from the browser.

**4. The proof (1:25 to 1:55).** Replay of META, then the report card table.

> On real prices since 2017, Afterhours earned 7.47% with 5,122 USDG of bad debt: about 21
> times less than always lending at the high limit, and safer than the low one while earning
> more. When META fell 24.5% after earnings, an ordinary vault lost 24,300 USDG; Afterhours lost
> 2,228. And we publish what did not work: our machine learning model lost to a simple
> volatility baseline, so the baseline ships.

**5. The market and the plan (1:55 to 2:20).** Speaker on camera.

> TEAM: who lends and borrows against Stock Tokens today, and how many (with a source).
> TEAM: quotes from the calls with DeFi lenders and vault curators (KICKOFF.md asks for 3).
> TEAM: distribution: listing the vault where Morpho users find vaults, curators who could run
> it, the Robinhood Chain ecosystem.

**6. The team and the ask (2:20 to 2:30).** Speaker on camera.

> TEAM: who you are and why you are the ones to build this.
> TEAM: what you will do next (testnet, audit, mainnet with a curator) and what you are asking
> for.

## Shot list

| # | Shot | Source |
| --- | --- | --- |
| 1 | Speaker, head and shoulders, plain background | Camera |
| 2 | Landing page at night, slow push on the exchange | `make up`, then Preview the close |
| 3 | Gap histogram, then "Both fixed settings lose" | Landing scroll story |
| 4 | Closing bell: board bars move, row flashes | Demo video shot 6 |
| 5 | Telegram and "Matched onchain" | Demo video shot 7 |
| 6 | Replay of the META night, counters running | `/replay` |
| 7 | Report card backtest table | `/report-card` |
| 8 | Speaker for market, team and ask | Camera |

Label any backtest shot on screen "historical stock prices, simulated vault" and keep the
Simulation banner in product shots.
