import { defineConfig } from "@playwright/test";

// E2E runs against a running stack (`make up`, then `make e2e`). WEB_BASE_URL, API_BASE_URL,
// ANVIL_RPC_URL and ADMIN_TOKEN come from the environment.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  use: { baseURL: process.env.WEB_BASE_URL },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    {
      name: "mobile",
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
      // The wallet and demo flows are covered on desktop; phones get every page and state.
      testIgnore: [/vault\.spec/, /demo\.spec/],
    },
  ],
});
