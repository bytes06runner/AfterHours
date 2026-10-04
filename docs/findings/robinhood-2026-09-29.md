# Robinhood, 2026-09-29: weekend trading and AI trading agents

Checked 2026-10-04. Only what a primary source says goes into the product, README or pitch.
Secondary reporting is listed separately and is not used for claims.

## Primary sources

1. **Robinhood newsroom, "HOOD Summit 2026"**, dated September 29, 2026.
   https://robinhood.com/us/en/newsroom/hood-summit-2026/
2. **Bruce Markets press release** (PR Newswire), dateline Chicago, September 30, 2026:
   "Markets to Be Open Seven Days a Week; Bruce Markets to Launch First Continuous Weekend U.S.
   Equities Trading with Strategic Investments Led by PEAK6 and Robinhood".
   https://en.prnasia.com/releases/apac/markets-to-be-open-seven-days-a-week-bruce-markets-to-launch-first-continuous-weekend-u-s-equities-trading-with-strategic-investments-led-by-peak6-and-robinhood-550034.shtml

Reuters: our fetch tools are blocked from reuters.com, so no Reuters text was read. Robinhood's
investor relations PDF (investors.robinhood.com/node/15291/pdf) timed out twice. Neither is used.

## Facts the primary sources support

Weekend trading (source 1, confirmed by source 2):

- Robinhood customers will be able to trade "a selection of U.S. equities 24/7, including
  weekends", "a curated list of stocks and ETFs across all account types" (source 1).
- "Weekend trading is powered by Bruce ATS", an alternative trading system (source 1).
- Status: "coming soon, pending regulatory review" (source 1); "subject to regulatory review" and
  expected "in the coming months" (source 2). It is not live today.
- It extends the Robinhood 24 Hour Market (launched 2023), which runs "from Sunday at 8pm ET
  through Friday at 8pm ET" (source 1).
- Bruce Markets is an SEC-registered broker-dealer operating Bruce ATS, which today runs
  overnight from 8:00 PM to 4:00 AM ET (source 2). PEAK6 (majority shareholder) and Robinhood led
  a strategic investment (source 2).
- Neither source describes weekend hours in detail, market makers, or how weekend prices form.

AI trading agents (source 1):

- Customers can create an agent and "choose a model from several leading AI labs including
  OpenAI". Usage on OpenAI GPT-Luna is free until the end of the year.
- Loops turn "a strategy into a standing, ongoing instruction for your agent to execute on repeat,
  around the clock", for example a "continuous overnight strategy to look for opportunities while
  you sleep".
- The agent can only use the funds in a dedicated agentic trading account; manual approval of each
  trade is on by default.
- "Coming soon to eligible U.S. customers."

Not in either primary source: anything about Robinhood Chain or Stock Tokens.

## Secondary reporting (not used for claims)

- CoinDesk, 2026-09-29 (Helene Braun), on the agents and weekend trading.
  https://www.coindesk.com/markets/2026/09/29/robinhood-adds-ai-agents-perps-and-weekend-trading-in-push-to-win-active-traders
- Yahoo Finance, Bloomberg (paywalled), Traders Magazine (reprint of source 2).

Which AI labs' models the agents use: Robinhood's own post names only OpenAI ("several leading AI
labs including OpenAI"). Secondary reports go further than that; we do not repeat them. Our text
says "AI trading agents" and names no other lab as a Robinhood partner.

## What it means for Afterhours (our reading, not Robinhood's)

- Our weekend oracle study found Stock Token feeds on Robinhood Chain post nothing from Friday
  20:00 to Sunday 20:00 New York time (artifacts/discovery/oracle_study.json). That is exactly the
  window the Robinhood 24 Hour Market does not cover today (source 1). Weekend trading would fill
  that window from one venue, Bruce ATS.
- If feeds start following a weekend venue, the risk changes from "no price" to "thin price": one
  venue's weekend price can gap or be pushed while the regular market is shut. Afterhours has to
  know which regime each Stock Token is in. Whether any feed changes is measured, not assumed:
  see the dated readings of the weekend oracle study.
- Agents that act "while you sleep" are the readers who most need machine-readable weekend risk.
