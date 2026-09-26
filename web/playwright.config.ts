import { defineConfig } from "@playwright/test";

// E2E runs against a running stack (`make up`); WEB_BASE_URL and ANVIL_RPC_URL come from env.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  use: { baseURL: process.env.WEB_BASE_URL, viewport: { width: 1440, height: 900 } },
  workers: 1,
});
