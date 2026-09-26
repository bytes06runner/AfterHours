/** Display names shared by the report card and the landing story. */
export const FORECASTERS: Record<string, string> = {
  model: "LightGBM quantile model",
  global_segment: "Segment quantile",
  ticker_segment: "Stock and segment quantile",
  ewma_normal: "EWMA volatility",
};
export const STRATEGY_NAMES = {
  always_weekday: "Always weekday tier",
  always_weekend: "Always weekend tier",
  afterhours: "Afterhours",
  perfect_foresight: "Perfect foresight",
} as const;
