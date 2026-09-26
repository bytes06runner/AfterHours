/**
 * Typed public configuration for the web app.
 *
 * The web app never reads config/afterhours.yaml directly and never holds literals for
 * addresses, chain ids or URLs. It gets the public config document from the API
 * (`GET /v1/config/public`, produced by engine/afterhours/public_config.py) or, at build time,
 * from a JSON file named by AFTERHOURS_PUBLIC_CONFIG_FILE. Both paths are parsed with the
 * zod schema below; keep it in step with the Python producer.
 */
import { z } from "zod";

const address = z.string().regex(/^0x[0-9a-fA-F]{40}$/, "expected a 20-byte hex address");

type AddressTree = string | { [key: string]: AddressTree };
const addressTree: z.ZodType<AddressTree> = z.lazy(() =>
  z.union([address, z.record(z.string(), addressTree)]),
);

export const PublicConfigSchema = z.object({
  profile: z.string().min(1),
  chain: z.object({
    key: z.string().min(1),
    chain_id: z.number().int().positive().nullable(),
    explorer_url: z.url({ protocol: /^https?$/ }).nullable(),
    rpc_url: z.url({ protocol: /^https?$/ }).nullable(),
  }),
  simulation: z.object({
    oracle: z.boolean(),
    collateral: z.boolean(),
  }),
  vault: z.object({
    name: z.string().min(1),
    symbol: z.string().min(1),
  }),
  exchange_calendar: z.string().min(1),
  schedule: z.object({
    hourly: z.boolean(),
    pre_close_minutes: z.number(),
    post_open_minutes: z.number(),
    lookahead_closed_periods: z.number(),
  }),
  deployment: z.record(z.string(), z.unknown()),
  discovered: z.record(z.string(), addressTree),
});

export type PublicConfig = z.infer<typeof PublicConfigSchema>;

/** Parse an unknown value into a PublicConfig, throwing a readable error on mismatch. */
export function parsePublicConfig(input: unknown): PublicConfig {
  const result = PublicConfigSchema.safeParse(input);
  if (!result.success) {
    throw new Error(`Public config is invalid: ${z.prettifyError(result.error)}`);
  }
  return result.data;
}

/** Environment the web app reads. Names mirror config/afterhours.yaml `web:`. */
export const WebEnvSchema = z.object({
  NEXT_PUBLIC_API_BASE_URL: z.url({ protocol: /^https?$/ }),
  NEXT_PUBLIC_WC_PROJECT_ID: z.string().optional(),
});

export type WebEnv = z.infer<typeof WebEnvSchema>;

/** Read and validate the public env. Pass `process.env` explicitly so Next can inline it. */
export function readWebEnv(env: Record<string, string | undefined>): WebEnv {
  return WebEnvSchema.parse({
    NEXT_PUBLIC_API_BASE_URL: env.NEXT_PUBLIC_API_BASE_URL,
    NEXT_PUBLIC_WC_PROJECT_ID: env.NEXT_PUBLIC_WC_PROJECT_ID || undefined,
  });
}

/** Fetch the public config from the API. */
export async function fetchPublicConfig(
  apiBaseUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<PublicConfig> {
  const url = new URL("/v1/config/public", apiBaseUrl);
  const response = await fetchImpl(url, { headers: { accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Can't load config from the API (${response.status}).`);
  }
  return parsePublicConfig(await response.json());
}
