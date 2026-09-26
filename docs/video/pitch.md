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

**2. The problem (0:20 to 0:45).** The gap histogram, then the frontier chart from the landing
story.

> So when trading resumes, prices gap. Across 523 US stocks and funds since 2010, 2.1% of
> earnings nights opened 10% or more down. A lender picks a loan-to-value limit and lives with
> it: lend at 91.5% and you earn 9.34%, but on one night between 2022 and 2026 that lost 0.247%
> of the vault; lend at 77% and you earn 6.88%. Every fixed mix sits on one line between them.

**3. The product (0:45 to 1:15).** The allocation board, the Almanac, a telegram and "Verify on
chain".

> Afterhours is a Morpho vault that lends each stock in the riskiest market its own history
> allows: 91.5%, 86% or 77%, re-rated every January from the year before. Before every close it
> forecasts each stock's bad case, and when that is too large for any market it pulls the money
> borrowers are not using. Every move writes its reason onchain, and anyone can check it from
> the browser.

**4. The proof (1:15 to 1:50).** The frontier chart with Afterhours above the line, then the
report card's decision section.

> We tested it on 2022 to 2026 with settings chosen on earlier years only. Afterhours earned
> 9.12%, the same as the best fixed mix at 9.09%, with 5,849 USDG of bad debt against 11,132:
> about half the loss. We also wrote down, before running, what our first design had to beat.
> It had less bad debt but earned less, so by our own rule it did not ship. We publish that, and
> we publish that no setting of Afterhours or of the fixed map kept its worst night under our
> 0.10% cap in the tuning years. Historical stock prices, simulated vault.

**5. The market and the plan (1:50 to 2:20).** Speaker on camera, with the market numbers on
screen.

> The market is early. At the end of September 2026, 149 Morpho markets on Robinhood Chain took a
> Stock Token as collateral, with 804,926 USDG supplied and 6,115 borrowed. Lending against
> Stock Tokens has barely started; we are building the vault lenders can trust with it when it
> grows.
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
| 3 | Gap histogram, then the frontier chart | Landing scroll story |
| 4 | Allocation board with three tiers; Almanac with META's earnings night above the line | `/vault`, `/almanac` |
| 5 | The pullback: board bar shrinks, row flashes, telegram and "Matched onchain" | Demo video shots 6 and 7 |
| 6 | Frontier chart with Afterhours above the line; the decision section | `/report-card` |
| 7 | Speaker for market, team and ask | Camera |

Label any backtest shot on screen "historical stock prices, simulated vault" and keep the
Simulation banner in product shots.
