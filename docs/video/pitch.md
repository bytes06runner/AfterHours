# Pitch video: script and shot list

Colosseum asks for a two-to-three-minute presentation video and says judges review it first.
Target: under 2 minutes 50 seconds read aloud at a normal pace (the spoken lines below are about
2 minutes 15 seconds; lines marked TEAM add roughly 25 seconds). Every number is in
`artifacts/report/numbers.json` (`make lint-numbers`). Methods, tables and every caveat live on
the report card, `docs/REGIME.md` and `docs/AGENTS.md`, not here. Lines marked TEAM are yours:
we do not write quotes, traction or backgrounds we have not got.

What Robinhood announced is quoted only from its own newsroom post and the Bruce Markets press
release (`docs/findings/robinhood-2026-09-29.md`): weekend trading is "pending regulatory
review", and this script names no AI lab behind Robinhood's agents.

The animated version in [animation/](animation/README.md) follows the earlier cut (before the
regime monitor and the agents); it still works as a backing track for sections 3 to 6.

## Script

**1. Frozen today (0:00 to 0:20).** Speaker on camera, then the landing page at night.

> Stock Tokens on Robinhood Chain trade all weekend. Their price feeds do not: over 8 weekends,
> 32 of the 35 feeds posted nothing from Friday night to Sunday night, and so did the two
> weekends since. With prices frozen nobody can be liquidated, so when trading resumes,
> lenders take the gap.

**2. Thin tomorrow (0:20 to 0:45).** The landing's "Frozen today, thin tomorrow" panel, then the
risk board's price regime column.

> Robinhood has announced weekend trading for a curated list of stocks and ETFs, pending
> regulatory review. If the feeds follow it, weekend prices will come from one venue, and can
> be thin. So Afterhours reads each Stock Token's price regime, regular, extended, weekend price
> or frozen, with a quality score. Last Saturday all 35 were frozen, and on the DEX, IONQ and
> RGTI had already drifted 3.4% and 7.3%.

**3. The product (0:45 to 1:05).** The allocation board, then the Almanac.

> Afterhours is a Morpho vault that lends each stock in the riskiest market its own last year
> allows, at 91.5%, 86% or 77% loan-to-value. Before every close it forecasts each stock's bad
> case, and when a night looks too risky for any market, it pulls the money borrowers are not
> using. Every move writes its reason onchain.

**4. The claim (1:05 to 1:35).** The frontier chart, Afterhours above the line.

> Against the fixed mix of markets that earns the same, Afterhours had 47% less bad debt and a
> 51% smaller worst night, on 2022 to 2026 with settings chosen on earlier years. We wrote the
> test down before running; our first design failed it, so this simpler design ships. The
> backtest uses modelled rates; real Stock Token markets pay lenders 0.0016% today.

**5. One night (1:35 to 1:50).** The replay of META, counters running.

> In October 2022 META opened 24.5% down after earnings. Afterhours had already pulled the
> money borrowers were not using, and lost 59% less than a vault lending at the top limit.

**6. For agents (1:50 to 2:05).** An MCP client calling the tools, then the Agents page.

> Robinhood's trading agents will run strategies overnight. Afterhours gives any agent this risk
> as four read-only tools: is the market open, how risky is this stock tonight, can this wallet
> be liquidated, and why did the vault move. They read; they cannot trade.

**7. The market (2:05 to 2:20).** Speaker on camera, market numbers on screen.

> The market is early: 150 Morpho markets take a Stock Token as collateral, with 804,926 USDG
> supplied and 6,182 borrowed. We are building the risk layer lenders and agents can trust as it
> grows.
> TEAM: one quote from a call with a DeFi lender or vault curator.

**8. The team and the ask (2:20 to 2:45).** Speaker on camera.

> TEAM: who you are and why you are the ones to build this. When you mention the paper, say it
> this way, and never call it "under review": "Our paper was submitted to the Astronomical
> Journal, and the editor invited an expanded resubmission."
> TEAM: what you will do next (testnet, audit, mainnet with a curator) and what you are asking
> for.

## Shot list

| # | Shot | Source |
| --- | --- | --- |
| 1 | Speaker, head and shoulders, plain background | Camera |
| 2 | Landing page at night, the welcome sequence | Live site |
| 3 | "Frozen today, thin tomorrow": regime counts and the least trustworthy prices; the risk board's price regime column and the Poor price quality filter | Live site, `/` and `/live` |
| 4 | Allocation board with three tiers; the Almanac with META's earnings night above the line | `make up`, `/vault`, `/almanac` |
| 5 | Frontier chart with Afterhours above the line | `/report-card` |
| 6 | Replay of the META night | `/replay` |
| 7 | An MCP client (Claude Desktop) calling `get_weekend_risk`, then the Agents page's real session | Claude Desktop with `afterhours-mcp`; `/agents` |
| 8 | Speaker for market, team and ask | Camera |

Label any backtest shot on screen "historical stock prices, simulated vault", keep the
Simulation banner in product shots, and keep the "Live: Robinhood Chain mainnet, read-only"
label in risk board shots.
