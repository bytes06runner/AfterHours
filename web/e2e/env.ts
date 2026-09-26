/** Stack coordinates for the E2E suite, all from the environment (see `make e2e`). */
export const API = process.env.API_BASE_URL ?? "";
export const RPC = process.env.ANVIL_RPC_URL ?? "";
export const ADMIN = process.env.ADMIN_TOKEN ?? "";

/** True for requests to the Afterhours API (used to fail or stub it). */
export const isApi = (url: URL) => API !== "" && url.origin === new URL(API).origin;

export const PAGES = [
  { path: "/", heading: /The market is (open|closed)\./ },
  { path: "/vault", heading: "The vault" },
  { path: "/almanac", heading: "Almanac" },
  { path: "/ledger", heading: "Ledger" },
  { path: "/replay", heading: "Replay" },
  { path: "/report-card", heading: "Report card" },
] as const;
