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
Its pre-rendered voiceover still says "Real markets pay lenders 0.0016% today" and "6,182
borrowed": both are true only at block 73,650,323 (2026-09-27). Do not use those two clips;
the market has since filled (section 7).

## Script

**1. Frozen today (0:00 to 0:20).** Speaker on camera, then the landing page at night.

> Stock Tokens on Robinhood Chain trade all weekend. Their price feeds do not: over 8 weekends,
> 32 of the 35 feeds posted nothing from Friday night to Sunday night, and in the two weekends
> we read since, all 35 were silent. While prices are frozen, no loan is liquidated on what the
> stock is really doing, so when trading resumes, lenders take the gap.

**2. Thin tomorrow (0:20 to 0:45).** The landing's "Frozen today, thin tomorrow" panel, then the
risk board's price regime column.

> Robinhood has announced weekend trading for a curated list of stocks and ETFs, pending
> regulatory review. If the feeds follow it, weekend prices will come from one venue, and can
> be thin. So Afterhours reads each Stock Token's price regime, regular, extended, weekend price
> or frozen, with a quality score. On Sunday, October 4th, all 35 were frozen. The DEX pools for
> IONQ and RGTI sat -3.4% and +7.3% from their feeds, but those pools held $50 and $73 of
> depth: a thin price, not a real one.

**3. The product (0:45 to 1:05).** The allocation board, then the Almanac.

> Afterhours is a Morpho vault that lends each stock in the riskiest market its own last year
> allows, at 91.5%, 86% or 77% loan-to-value. Before each close a scheduled job forecasts each
> stock's bad case, and when a night looks too risky for any market, it pulls the money borrowers
> are not using. Every decision is recorded, holds included, and every move writes its reason
> onchain.
> TEAM, before recording: say "a scheduled job" only once `/v1/automation` shows a completed
> scheduled cycle (`last_successful_cycle.trigger_source` is `schedule`). Until then say "a job
> scheduled to run before each close". The vault runs on testnet with simulated tokens; keep the
> Simulation banner in the shot.

**4. The claim (1:05 to 1:35).** The frontier chart, Afterhours above the line.

> Against the fixed mix of markets that earns the same, Afterhours had 47% less bad debt and a
> 51% smaller worst night, on 2022 to 2026 with settings chosen on earlier years. We wrote the
> decision rule down before running, and our first design failed it. We then defined this
> simpler design and tested it once on the same years, a second look we disclose. The backtest
> uses modelled rates on a simulated vault.

**5. One night (1:35 to 1:50).** The replay of META, counters running.

> In October 2022 META opened 24.5% down after earnings. Afterhours had already pulled the
> money borrowers were not using, and lost 59% less than a vault lending at the top limit, with
> the backtest's assumed share of loans rolling over each day.

**6. For agents (1:50 to 2:05).** An MCP client calling the tools, then the Agents page.

> Robinhood's trading agents will run strategies overnight. Afterhours gives any agent this risk
> as four read-only tools: is the market open, how risky is this stock tonight, can this wallet
> be liquidated, and why did the vault move. They read; they cannot trade.

**7. The market (2:05 to 2:20).** Speaker on camera, market numbers on screen.

> In ten days this market went from idle to almost fully lent. On October 7th, Morpho markets
> on Robinhood Chain held 1,721,781 USDG against Stock Tokens with 1,665,217 borrowed: 96.7%
> utilization, 99.97% of it at 62.5% loan-to-value, on prices that freeze every weekend. Those
> lenders cannot pull money that is lent. What their curators need before each close is which
> loan-to-value survives tonight, and whether to stop adding supply. Afterhours answers that,
> per market, read-only, today.
> TEAM: one quote from a call with a curator who funds these markets. Do not claim one you have
> not got.

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
