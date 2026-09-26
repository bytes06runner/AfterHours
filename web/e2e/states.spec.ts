import { expect, test } from "@playwright/test";

import { API, isApi, PAGES } from "./env";

test.describe("API unreachable", () => {
  for (const { path } of PAGES) {
    test(`${path} says what happened and that it retries`, async ({ page }) => {
      test.skip(!API, "needs API_BASE_URL");
      await page.route(isApi, (route) => route.abort("connectionrefused"));
      await page.goto(path);
      // React Query retries three times before it reports an error.
      await expect(page.getByRole("main").getByRole("alert").first()).toContainText(
        "Retrying in 10 seconds.",
        {
          timeout: 30_000,
        },
      );
    });
  }
});

test("an empty ledger names the next plan", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL");
  await page.route(
    (url) => isApi(url) && url.pathname === "/v1/reasons",
    (route) => route.fulfill({ json: { items: [], next_cursor: null, total: 0, next_plan: null } }),
  );
  await page.goto("/ledger");
  await expect(
    page.getByText(/No moves yet\. The next plan runs at the pre-close check/),
  ).toBeVisible();
});

test("an empty replay list says so", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL");
  await page.route(
    (url) => isApi(url) && url.pathname === "/v1/replay/scenarios",
    (route) =>
      route.fulfill({ json: { label: "historical stock prices, simulated vault", scenarios: [] } }),
  );
  await page.goto("/replay");
  await expect(page.getByText(/No replays yet/)).toBeVisible();
  await expect(page.locator('main [aria-busy="true"]')).toHaveCount(0);
});
