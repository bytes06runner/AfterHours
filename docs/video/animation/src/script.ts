/**
 * The spoken lines of docs/video/pitch.md, per scene, with every number from numbers.json.
 * Shown as timed subtitles in the PitchWithScript render (a guide for recording the voiceover).
 */
import { n } from "./data";
import { SCENES } from "./theme";

export const SCRIPT: Record<keyof typeof SCENES, string[]> = {
  hook: [
    "Stock Tokens on Robinhood Chain trade all weekend.",
    `Their price feeds do not: over ${n("oracle.weekends")} weekends, ${n("oracle.feeds_without_update")} of the ${n("oracle.feeds")} feeds posted nothing from Friday night to Sunday night.`,
    "A lending market cannot liquidate anyone while its prices are frozen, so when trading resumes, lenders take the gap.",
  ],
  product: [
    `Afterhours is a Morpho vault that lends each stock in the riskiest market its own last year allows, at ${n("tiers.weekday.lltv_short")}, ${n("tiers.middle.lltv_short")} or ${n("tiers.weekend.lltv_short")} loan-to-value.`,
    "Before every close it forecasts each stock's bad case, and when a night looks too risky for any market, it pulls the money borrowers are not using.",
    "Every move writes its reason onchain.",
  ],
  claim: [
    `Against the fixed mix of markets that earns the same, Afterhours had ${n("rel.b_vs_blend.bad_debt_less")} less bad debt and a ${n("rel.b_vs_blend.worst_less")} smaller worst night.`,
    `Against a fixed plan that re-rates each stock once a year, ${n("rel.b_vs_fixed_map.bad_debt_less")} less bad debt and a ${n("rel.b_vs_fixed_map.worst_less")} smaller worst night, again at the same yield.`,
    "Those figures come from 2022 to 2026, with settings chosen on earlier years, and before running we wrote down the test our first design had to pass; it did not, so this simpler design ships.",
    `The backtest uses modelled rates; real Stock Token markets pay lenders ${n("market.supply_apy")} today.`,
  ],
  night: [
    `In October 2022 ${n("replay.ticker")} opened ${n("replay.gap")} down after earnings.`,
    `Afterhours had already pulled the money borrowers were not using, and lost ${n("rel.replay.b_less")} less than a vault lending at the top limit.`,
  ],
  market: [
    `The market is early: ${n("market.stock_token_markets")} Morpho markets take a Stock Token as collateral, with ${n("market.usdg_supplied")} USDG supplied and ${n("market.usdg_borrowed")} borrowed.`,
    "We are building the vault lenders can trust with it as it grows.",
    "(TEAM: one quote from a call with a DeFi lender or vault curator.)",
  ],
  close: [
    "(TEAM: who you are and why you are the ones to build this.)",
    "(TEAM: what you will do next, and what you are asking for.)",
  ],
};
