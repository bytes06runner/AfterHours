/**
 * Typed client for the Afterhours API (docs/SPEC.md section 8). Every response is parsed with
 * zod so a contract change fails loudly instead of rendering nonsense. The base URL comes from
 * NEXT_PUBLIC_API_BASE_URL; there are no URL literals here.
 */
import { z } from "zod";

import { parsePublicConfig, type PublicConfig } from "./config";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** The API's own words for a live-view 503 ("still reading", "answering slowly"), else the
 *  fallback. A bare status code is not a message. */
export function liveErrorText(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 503 && !/^\d+$/.test(err.message)) {
    return err.message;
  }
  return fallback;
}

/** How often a failed query is retried; the error messages quote it. */
export const ERROR_RETRY_MS = 10_000;
export const RETRY_TEXT = `Retrying in ${ERROR_RETRY_MS / 1000} seconds.`;

export function apiBase(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) throw new ApiError(0, "NEXT_PUBLIC_API_BASE_URL is not set.");
  return base;
}

async function get<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(new URL(path, apiBase()), {
      ...init,
      headers: { accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Can't reach the Afterhours API.");
  }
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail);
  }
  return schema.parse(await response.json());
}

export const StatusSchema = z.object({
  now: z.string(),
  state: z.enum(["open", "closed", "holiday"]),
  next_open: z.string(),
  next_close: z.string(),
  seconds_to_open: z.number(),
  seconds_to_close: z.number(),
  clock: z.enum(["chain", "wall"]),
  profile: z.string(),
});
export type Status = z.infer<typeof StatusSchema>;

const MarketSchema = z.object({
  symbol: z.string(),
  tier: z.enum(["weekday", "middle", "weekend"]),
  market_id: z.string(),
  vault_supply: z.number(),
  lent_out: z.number(),
  market_supply: z.number(),
  market_borrow: z.number(),
  supply_apy: z.number(),
  absolute_cap: z.number(),
});
export type Market = z.infer<typeof MarketSchema>;

const TierSchema = z.object({
  lltv: z.number(),
  liquidation_allowance_b: z.number(),
  cushion: z.number(),
});

export const VaultSchema = z.object({
  profile: z.string(),
  simulation: z.object({
    oracle: z.boolean(),
    collateral: z.boolean(),
    morpho_self_deployed: z.boolean(),
  }),
  block: z.number(),
  tvl_usdg: z.number(),
  idle_usdg: z.number(),
  placed_usdg: z.number(),
  liquidity_market: z.string().nullable(),
  withdrawable_now_usdg: z.number(),
  idle_reserve_share: z.number(),
  max_share_per_stock: z.number(),
  apy: z.number(),
  share_price: z.number(),
  tiers: z.record(z.enum(["weekday", "middle", "weekend"]), TierSchema),
  markets: z.array(MarketSchema),
});
export type Vault = z.infer<typeof VaultSchema>;

const PeriodSchema = z.object({
  starts: z.string(),
  ends: z.string(),
  segment: z.enum(["earnings", "holiday", "weekend", "overnight"]),
  hours: z.number(),
});
const DriverSchema = z.object({
  feature: z.string(),
  contribution: z.number(),
  detail: z.string(),
});
const ForecastSchema = z.object({
  symbol: z.string(),
  period: PeriodSchema,
  bad_case_drop: z.number(),
  alpha: z.number(),
  model_version: z.string(),
  method: z.string(),
  drivers: z.array(DriverSchema),
});
export type Forecast = z.infer<typeof ForecastSchema>;

export const RiskSchema = z.object({
  now: z.string(),
  policy: z.literal("option_b"),
  lookahead_closed_periods: z.number(),
  map_fraction: z.number(),
  pullback_fraction: z.number(),
  tier_limits: z.record(
    z.string(),
    z.object({ lltv: z.number(), cushion: z.number(), map_limit: z.number() }),
  ),
  stocks: z.array(
    z.object({
      symbol: z.string(),
      next: ForecastSchema,
      worst_in_lookahead: ForecastSchema,
      tiers: z.record(z.string(), z.object({ allowed: z.boolean(), reason: z.string() })),
      policy: z.object({
        rating: z.number().nullable(),
        rating_year: z.number(),
        mapped_tier: z.string(),
        pull_limit: z.number(),
        pulled: z.boolean(),
        reason: z.string(),
      }),
    }),
  ),
});
export type Risk = z.infer<typeof RiskSchema>;

export const AlmanacSchema = z.object({
  now: z.string(),
  days: z.number(),
  periods: z.array(PeriodSchema),
  stocks: z.array(
    z.object({
      symbol: z.string(),
      earnings: z.array(z.object({ date: z.string(), timing: z.string() })),
      forecasts: z.array(ForecastSchema),
    }),
  ),
});
export type Almanac = z.infer<typeof AlmanacSchema>;

export const CardSchema = z.object({
  id: z.string(),
  created_at: z.string(),
  profile: z.string(),
  subject: z.string(),
  stock: z.string(),
  action: z.string(),
  from_tier: z.string().nullable(),
  to_tier: z.string().nullable(),
  amount_usdg: z.string(),
  closed_period: z.object({
    starts: z.string(),
    ends: z.string(),
    segment: z.string(),
    hours: z.string(),
  }),
  prediction: z.object({
    alpha: z.string(),
    bad_case_drop: z.string(),
    model_version: z.string(),
    method: z.string(),
  }),
  top_drivers: z.array(
    z.object({ feature: z.string(), contribution: z.string(), detail: z.string() }),
  ),
  drivers_method: z.string(),
  rule_fired: z.string(),
  tx: z
    .object({ chain_id: z.number(), reallocate_tx: z.string(), registry_tx: z.string() })
    .optional(),
  reason_hash: z.string().optional(),
});
export type Card = z.infer<typeof CardSchema>;

export const ReasonsSchema = z.object({
  items: z.array(CardSchema),
  next_cursor: z.number().nullable(),
  total: z.number(),
});
export type Reasons = z.infer<typeof ReasonsSchema>;

export const VerificationSchema = z.object({
  status: z.enum(["matched", "mismatched", "event_missing", "no_tx"]),
  recomputed_hash: z.string(),
  onchain_hash: z.string().optional(),
  seq: z.number().optional(),
  block: z.number().optional(),
  registry_tx: z.string().optional(),
  uri: z.string().optional(),
});
export const ReasonDetailSchema = z.object({
  card: CardSchema,
  canonical_json: z.string(),
  verification: VerificationSchema,
});
export type ReasonDetail = z.infer<typeof ReasonDetailSchema>;

export const PricesSchema = z.object({
  source: z.enum(["simulated", "chainlink"]),
  prices: z.array(z.object({ symbol: z.string(), price_usdg: z.number() })),
});
export type Prices = z.infer<typeof PricesSchema>;

export const SEGMENT_KEYS = ["overall", "earnings", "holiday", "weekend", "overnight"] as const;
export type SegmentKey = (typeof SEGMENT_KEYS)[number];
const Perf = z.object({
  n: z.number(),
  miss_rate: z.number(),
  pinball: z.number(),
  mean_drop: z.number(),
});
const CalPoint = z.object({ nominal: z.number(), observed: z.number(), n: z.number() });
const Strategy = z.object({
  net_lender_yield_annualised: z.number(),
  net_return_total: z.number(),
  interest_usdg: z.number(),
  bad_debt_usdg: z.number(),
  bad_debt_events: z.number(),
  worst_event: z
    .object({
      session_prev: z.string(),
      bad_debt_usdg: z.number(),
      share_of_vault: z.number(),
      ticker: z.string(),
      g: z.number(),
      segment: z.string(),
    })
    .partial()
    .nullable(),
  share_of_time: z.object({ weekday: z.number(), weekend: z.number(), idle: z.number() }),
  reallocations: z.number(),
  final_assets_usdg: z.number(),
});
export const STRATEGIES = [
  "always_weekday",
  "always_weekend",
  "afterhours",
  "perfect_foresight",
] as const;
export type StrategyKey = (typeof STRATEGIES)[number];
const Quant = z.object({
  n: z.number(),
  std: z.number(),
  min: z.number(),
  share_drops_at_least: z.record(z.string(), z.number()),
  count_drops_at_least: z.record(z.string(), z.number()),
});
const Hist = z.object({
  edges: z.array(z.number()),
  segments: z.record(z.string(), z.object({ n: z.number(), share: z.array(z.number()) })),
});

const FrontierPoint = z.object({
  yield: z.number(),
  worst: z.number(),
  bad_debt: z.number(),
  interest: z.number(),
});
export type FrontierPoint = z.infer<typeof FrontierPoint>;
const DecisionUniverse = z.object({
  stocks: z.number(),
  evaluation: z.object({ first: z.string(), last: z.string(), closed_periods: z.number() }),
  b: FrontierPoint.extend({ share_of_time: z.record(z.string(), z.number()) }),
  b_chosen: z.object({
    map_fraction: z.number(),
    pullback_fraction: z.number(),
    lookahead: z.number(),
  }),
  b_met_cap_on_tuning: z.boolean(),
  b_tuning_worst: z.number(),
  b_settings_meeting_cap: z.number(),
  b_settings: z.number(),
  fixed_map_tuning_smallest_worst: z.number(),
  fixed_map: FrontierPoint,
  dynamic: FrontierPoint,
  nearest_blend: FrontierPoint.extend({ w: z.number() }),
  blends: z.array(FrontierPoint.extend({ w: z.number() })),
  pulls: z.object({
    per_year: z.record(z.string(), z.object({ nights: z.number(), usdg_moved: z.number() })),
    total: z.object({ nights: z.number(), stock_nights: z.number(), usdg_moved: z.number() }),
    by_symbol: z.record(z.string(), z.number()),
  }),
});
export type DecisionUniverse = z.infer<typeof DecisionUniverse>;

export const ReportCardSchema = z.object({
  decision: z.object({
    rule: z.string(),
    result: z.string(),
    tuning_years: z.string(),
    evaluation_years: z.string(),
    cap: z.number(),
    label: z.string(),
    second_evaluation_note: z.string(),
    universes: z.object({ vault: DecisionUniverse, stock_tokens: DecisionUniverse }),
    assumed_apy: z.record(z.string(), z.number()),
    market_now: z.object({
      block: z.number(),
      block_time: z.string(),
      markets: z.number(),
      usdg_supplied: z.number(),
      usdg_borrowed: z.number(),
      supply_apy: z.number(),
      borrow_apy: z.number(),
      utilization: z.number(),
    }),
  }),
  oracle: z.object({
    weekends: z.number(),
    feeds: z.number(),
    feeds_without_update: z.number(),
    feeds_with_update: z.array(z.string()),
    updates_in_window: z.number(),
    max_seconds_after_window_opened: z.number().nullable(),
    first_weekend_close: z.string().nullable(),
    last_weekend_close: z.string().nullable(),
  }),
  model: z.object({
    first_sentence: z.string(),
    label: z.string(),
    acceptance: z.object({
      alpha: z.number(),
      held_out: z.record(z.string(), z.record(z.string(), Perf)),
      coverage_overall: z.object({
        miss_rate: z.number(),
        target: z.number(),
        tolerance: z.number(),
        pass: z.boolean(),
      }),
      coverage_earnings: z.object({
        miss_rate: z.number(),
        target: z.number(),
        tolerance: z.number(),
        pass: z.boolean(),
      }),
      pinball_vs_baselines: z.record(
        z.string(),
        z.object({ model: z.number(), baseline: z.number(), pass: z.boolean() }),
      ),
      passed: z.boolean(),
      shipped: z.string(),
      fallback_reason: z.string().optional(),
    }),
    shipped_performance: z.record(z.string(), Perf),
    calibration_curves: z.record(z.string(), z.record(z.string(), z.array(CalPoint))),
    variants_tried: z.array(
      z.object({
        target_scaling: z.string(),
        conformal_normalize: z.string(),
        model_pinball: z.number(),
        miss_rate_overall: z.number(),
      }),
    ),
    code_version: z.string(),
    config: z.object({
      target_alpha: z.number(),
      conformal: z.object({ method: z.string(), mondrian_segments: z.array(z.string()) }),
      walk_forward: z.object({
        train_years: z.number(),
        calibrate_years: z.number(),
        test_years: z.number(),
      }),
      baselines: z.object({ ewma_lambda: z.number(), min_ticker_segment_rows: z.number() }),
    }),
    model_version: z.string(),
    folds: z.number(),
  }),
  backtest: z.object({
    label: z.string(),
    period: z.object({
      first: z.string(),
      last: z.string(),
      closed_periods: z.number(),
      rows: z.number(),
    }),
    selected: z.array(z.string()),
    chosen: z.object({
      weekday_lltv: z.number(),
      weekend_lltv: z.number(),
      safety_margin: z.number(),
      lookahead_closed_periods: z.number(),
      rule: z.string(),
      eligible_settings: z.number(),
    }),
    strategies: z.record(z.string(), Strategy),
    sensitivity: z.array(
      z.object({ kind: z.string(), value: z.number(), results: z.record(z.string(), Strategy) }),
    ),
    assumptions: z.object({
      vault_usdg: z.number(),
      supply_apy_by_lltv: z.record(z.string(), z.number()),
      utilization: z.number(),
      loan_turnover_per_session: z.number(),
      note: z.string(),
    }),
  }),
  gaps: z.object({
    label: z.string(),
    period: z.object({ first_close: z.string(), last_open: z.string() }),
    tickers: z.object({ universe: z.number(), selected: z.array(z.string()) }),
    universe: z.record(z.string(), Quant),
    selected: z.record(z.string(), Quant),
    worst_selected: z.array(
      z.object({
        ticker: z.string(),
        session_prev: z.string(),
        session_next: z.string(),
        segment: z.string(),
        g: z.number(),
      }),
    ),
    histograms: z.object({ universe: Hist, selected: Hist.nullable() }),
    tail: z.object({
      drops: z.array(z.number()),
      universe: z.record(z.string(), z.array(z.number())),
      selected: z.record(z.string(), z.array(z.number())).optional(),
    }),
  }),
});
export type ReportCard = z.infer<typeof ReportCardSchema>;

const ScenarioSchema = z.object({
  id: z.string(),
  ticker: z.string(),
  session_prev: z.string(),
  session_next: z.string(),
  segment: z.enum(["earnings", "holiday", "weekend", "overnight"]),
  g: z.number(),
  hours_closed: z.number(),
});
export type Scenario = z.infer<typeof ScenarioSchema>;
export const ScenariosSchema = z.object({ label: z.string(), scenarios: z.array(ScenarioSchema) });

const ReplayPoint = z.object({
  session_prev: z.string(),
  weekday_supply: z.number(),
  weekday_lent: z.number(),
  middle_supply: z.number().default(0),
  middle_lent: z.number().default(0),
  weekend_supply: z.number(),
  weekend_lent: z.number(),
  idle: z.number(),
  bad_debt_period: z.number(),
  bad_debt_cum: z.number(),
  interest_cum: z.number(),
  assets: z.number(),
});
export type ReplayPoint = z.infer<typeof ReplayPoint>;
const ReplayVault = z.object({
  bad_debt_usdg: z.number(),
  interest_usdg: z.number(),
  final_assets_usdg: z.number(),
  series: z.array(ReplayPoint),
});
export const ReplaySchema = ScenarioSchema.extend({
  label: z.string(),
  price_path: z.array(z.object({ date: z.string(), open: z.number(), close: z.number() })),
  periods: z.array(
    z.object({
      session_prev: z.string(),
      session_next: z.string(),
      g: z.number(),
      segment: z.string(),
      bad_case_drop: z.number(),
      rating: z.number().nullable(),
      mapped_tier: z.string(),
      pulled: z.boolean(),
      pull_limit: z.number(),
    }),
  ),
  vaults: z.object({ always_weekday: ReplayVault, afterhours: ReplayVault }),
  vault_usdg: z.number(),
  settings: z.object({
    policy: z.literal("option_b"),
    map_fraction: z.number(),
    pullback_fraction: z.number(),
    lookahead_closed_periods: z.number(),
  }),
  tiers: z.record(z.string(), z.object({ lltv: z.number(), cushion: z.number() })),
});
export type Replay = z.infer<typeof ReplaySchema>;

const LiveForecast = z.object({
  symbol: z.string(),
  period: z.object({
    starts: z.string(),
    ends: z.string(),
    segment: z.string(),
    hours: z.number(),
  }),
  bad_case_drop: z.number(),
  alpha: z.number(),
});
/** Price regime of one Stock Token (docs/REGIME.md). */
export const LiveRegime = z.object({
  regime: z.enum(["regular", "extended", "weekend_venue", "frozen"]),
  label: z.string(),
  since: z.string().nullable(),
  feed_age_seconds: z.number().nullable(),
  typical_interval_minutes: z.number().nullable(),
  dex_price: z.number().nullable(),
  divergence: z.number().nullable(),
  depth_usd: z.number().nullable(),
  quality: z.object({
    score: z.number().nullable(),
    grade: z.enum(["good", "fair", "poor"]).nullable(),
    marks: z.record(z.string(), z.number().nullable()),
    used: z.array(z.string()),
  }),
  line: z.string(),
});
export type LiveRegimeT = z.infer<typeof LiveRegime>;
const RegimeSummary = z.object({
  calendar: z.string(),
  segment: z.string(),
  closed_since: z.string().nullable(),
  counts: z.record(z.string(), z.number()),
  method: z.string(),
});
export const LiveRegimesSchema = RegimeSummary.extend({
  network: z.string(),
  block: z.number(),
  as_of: z.string(),
  tokens: z.array(LiveRegime.extend({ symbol: z.string(), feed_price: z.number().nullable() })),
});
export type LiveRegimes = z.infer<typeof LiveRegimesSchema>;

export const LiveBoardSchema = z.object({
  network: z.string(),
  block: z.number(),
  as_of: z.string(),
  regimes: RegimeSummary.nullish(),
  stocks: z.array(
    z.object({
      symbol: z.string(),
      feed: z.string(),
      price: z.number().nullable(),
      updated_at: z.string().nullable(),
      status: z
        .object({
          state: z.enum(["frozen", "quiet", "updating"]),
          age_seconds: z.number(),
          window_start: z.string(),
          window_end: z.string(),
        })
        .nullable(),
      tonight: LiveForecast.nullable(),
      markets: z.array(z.object({ lltv: z.number(), cushion: z.number() })),
      breached: z.array(z.number()),
      regime: LiveRegime.nullish(),
    }),
  ),
});
export type LiveBoard = z.infer<typeof LiveBoardSchema>;

export const LivePositionsSchema = z.object({
  network: z.string(),
  address: z.string(),
  block: z.number(),
  as_of: z.string(),
  markets_checked: z.number(),
  positions: z.array(
    z.object({
      market_id: z.string(),
      symbol: z.string(),
      lltv: z.number(),
      loan_is_usdg: z.boolean(),
      loan_token: z.string(),
      loan_symbol: z.string().nullable(),
      collateral_tokens: z.number(),
      borrowed: z.number(),
      supplied: z.number(),
      price: z.number().nullable(),
      ltv: z.number().optional(),
      liquidation_price: z.number().optional(),
      drop_to_liquidation: z.number().optional(),
      tonight: LiveForecast.nullable().optional(),
      breach_tonight: z.boolean().optional(),
    }),
  ),
});
export type LivePositions = z.infer<typeof LivePositionsSchema>;

export const api = {
  config: (): Promise<PublicConfig> =>
    get("/v1/config/public", z.unknown()).then(parsePublicConfig),
  status: () => get("/v1/status", StatusSchema),
  vault: () => get("/v1/vault", VaultSchema),
  prices: () => get("/v1/prices", PricesSchema),
  risk: () => get("/v1/risk", RiskSchema),
  almanac: (days: number) => get(`/v1/almanac?days=${days}`, AlmanacSchema),
  reasons: (cursor = 0, stock?: string) =>
    get(
      `/v1/reasons?cursor=${cursor}${stock ? `&stock=${encodeURIComponent(stock)}` : ""}`,
      ReasonsSchema,
    ),
  reason: (id: string) => get(`/v1/reasons/${encodeURIComponent(id)}`, ReasonDetailSchema),
  reportCard: () => get("/v1/report-card", ReportCardSchema),
  scenarios: () => get("/v1/replay/scenarios", ScenariosSchema),
  replay: (id: string) => get(`/v1/replay/${encodeURIComponent(id)}`, ReplaySchema),
  liveBoard: () => get("/v1/live/board", LiveBoardSchema),
  liveRegimes: () => get("/v1/live/regimes", LiveRegimesSchema),
  livePositions: (address: string) =>
    get(`/v1/live/positions/${encodeURIComponent(address)}`, LivePositionsSchema),
  liveExamples: () => get("/v1/live/examples", z.object({ addresses: z.array(z.string()) })),
};

export const STREAM_EVENTS = [
  "status",
  "plan_changed",
  "tx_sent",
  "tx_confirmed",
  "reason_logged",
  "vault_updated",
] as const;
export type StreamEvent = (typeof STREAM_EVENTS)[number];

export function streamUrl(): string {
  return new URL("/v1/stream", apiBase()).toString();
}
