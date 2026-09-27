/**
 * Every number in the video comes from the repository's generated files, never typed in:
 * artifacts/report/numbers.json (the same source the README and pitch are checked against)
 * and the mainnet discovery file for the 35 Stock Token names.
 */
import numbersDoc from "../../../../artifacts/report/numbers.json";
import discovered from "../../../../deployments/fork.discovered.json";

type Entry = { text: string; value?: unknown; source?: string };
const numbers = (numbersDoc as { numbers: Record<string, Entry> }).numbers;

/** The text of a generated number, e.g. n("rel.b_vs_blend.bad_debt_less") -> "47%". */
export function n(key: string): string {
  const e = numbers[key];
  if (!e) throw new Error(`numbers.json has no ${key}`);
  return e.text;
}

/** A generated number as a float, for animation (e.g. counters, chart positions). */
export function v(key: string): number {
  return parseFloat(n(key).replace(/,/g, "").replace("%", ""));
}

export const STOCK_TOKENS: string[] = Object.keys(
  (discovered as { stock_tokens: Record<string, unknown> }).stock_tokens,
).sort();

/** Feeds that did post inside the weekend window (the other 32 posted nothing). */
export const UPDATED_FEEDS: string[] = n("oracle.feeds_with_update").split(", ");

export const VAULT_STOCKS: string[] = n("backtest.selected").split(", ");

/** The three tiers: LLTV and cushion. */
export const TIERS = [
  { name: "weekday", lltv: n("tiers.weekday.lltv_short"), cushion: n("tiers.weekday.cushion") },
  { name: "middle", lltv: n("tiers.middle.lltv_short"), cushion: n("tiers.middle.cushion") },
  { name: "weekend", lltv: n("tiers.weekend.lltv_short"), cushion: n("tiers.weekend.cushion") },
];

/** Strategies on the 5 vault stocks, held-out 2022 to 2026: yield (%) and bad debt (USDG). */
export const FRONTIER = [
  { key: "always_weekend", label: "Always 77%", fixedMix: true },
  { key: "blend", label: "Fixed mix, same yield", fixedMix: true },
  { key: "always_weekday", label: "Always 91.5%", fixedMix: true },
  { key: "fixed_map", label: "Yearly fixed plan", fixedMix: false },
  { key: "b", label: "Afterhours", fixedMix: false },
].map((s) => ({
  ...s,
  yield: v(`b5.${s.key}.yield`),
  badDebt: v(`b5.${s.key}.bad_debt`),
  yieldText: n(`b5.${s.key}.yield`),
  badDebtText: n(`b5.${s.key}.bad_debt`),
}));
