# Pitch video: script and shot list

Colosseum asks for a two-to-three-minute presentation video and says judges review it first.
Target: under 2 minutes 30 seconds read aloud at a normal pace (the spoken lines below are
266 words, about 1 minute 50 seconds; lines marked TEAM add roughly 30 seconds). Every number is in
`artifacts/report/numbers.json` (`make lint-numbers`). Methods, tables and every caveat live on
the report card, not here. Lines marked TEAM are yours: we do not write quotes, traction or
backgrounds we have not got.

## Script

**1. The hook (0:00 to 0:20).** Speaker on camera, then the landing page at night.

> Stock Tokens on Robinhood Chain trade all weekend. Their price feeds do not: over 8 weekends,
> 32 of the 35 feeds posted nothing from Friday night to Sunday night. A lending market cannot
> liquidate anyone while its prices are frozen, so when trading resumes, lenders take the gap.

**2. The product (0:20 to 0:50).** The allocation board, then the Almanac.

> Afterhours is a Morpho vault that lends each stock in the riskiest market its own last year
> allows, at 91.5%, 86% or 77% loan-to-value. Before every close it forecasts each stock's bad
> case, and when a night looks too risky for any market, it pulls the money borrowers are not
> using. Every move writes its reason onchain.

**3. The claim (0:50 to 1:20).** The frontier chart, Afterhours above the line.

> Against the fixed mix of markets that earns the same, Afterhours had 47% less bad debt and a
> 51% smaller worst night. Against a fixed plan that re-rates each stock once a year, 31% less
> bad debt and a 46% smaller worst night, again at the same yield. Those figures come from
> 2022 to 2026, with settings chosen on earlier years, and before running we wrote down the test
> our first design had to pass; it did not, so this simpler design ships. The backtest uses
> modelled rates; real Stock Token markets pay lenders 0.0016% today.

**4. One night (1:20 to 1:40).** The replay of META, counters running.

> In October 2022 META opened 24.5% down after earnings. Afterhours had already pulled the
> money borrowers were not using, and lost 59% less than a vault lending at the top limit.

**5. The market (1:40 to 2:05).** Speaker on camera, market numbers on screen.

> The market is early: 150 Morpho markets take a Stock Token as collateral, with 804,926 USDG
> supplied and 6,182 borrowed. We are building the vault lenders can trust with it as it grows.
> TEAM: one quote from a call with a DeFi lender or vault curator.

**6. The team and the ask (2:05 to 2:25).** Speaker on camera.

> TEAM: who you are and why you are the ones to build this.
> TEAM: what you will do next (testnet, audit, mainnet with a curator) and what you are asking
> for.

## Shot list

| # | Shot | Source |
| --- | --- | --- |
| 1 | Speaker, head and shoulders, plain background | Camera |
| 2 | Landing page at night, the welcome sequence and the closing bell | `make up`, then Preview the close |
| 3 | Allocation board with three tiers; the Almanac with META's earnings night above the line | `/vault`, `/almanac` |
| 4 | Frontier chart with Afterhours above the line | `/report-card` |
| 5 | Replay of the META night | `/replay` |
| 6 | Speaker for market, team and ask | Camera |

Label any backtest shot on screen "historical stock prices, simulated vault" and keep the
Simulation banner in product shots.
