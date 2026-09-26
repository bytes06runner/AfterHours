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
    throw new ApiError(0, "Can't reach the Afterhours API. Retrying shortly.");
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
  tier: z.enum(["weekday", "weekend"]),
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
  apy: z.number(),
  share_price: z.number(),
  tiers: z.object({ weekday: TierSchema, weekend: TierSchema }),
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
  lookahead_closed_periods: z.number(),
  safety_margin: z.number(),
  stocks: z.array(
    z.object({
      symbol: z.string(),
      next: ForecastSchema,
      worst_in_lookahead: ForecastSchema,
      tiers: z.record(z.string(), z.object({ allowed: z.boolean(), reason: z.string() })),
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

// The report card and replay payloads are large, artifact-shaped documents; the pages that use
// them validate the parts they read.
const Loose = z.record(z.string(), z.unknown());

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
  reportCard: () => get("/v1/report-card", Loose),
  scenarios: () => get("/v1/replay/scenarios", Loose),
  replay: (id: string) => get(`/v1/replay/${encodeURIComponent(id)}`, Loose),
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
