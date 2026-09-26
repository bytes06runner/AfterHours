import { expect, test } from "@playwright/test";

import { API, PAGES } from "./env";

/** Every page renders its live content, logs no errors and never scrolls sideways. */
for (const { path, heading } of PAGES) {
  test(`${path} renders live data`, async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole("note").filter({ hasText: "Simulation" })).toBeVisible();
    // Wait for the data-driven part of each page, then check nothing is still loading.
    const ready = {
      "/": page.getByRole("heading", { name: "Checked against history." }),
      "/vault": page.getByRole("heading", { name: "Allocation board" }),
      "/almanac": page.getByText("weekend tier only").first(),
      "/ledger": page.getByText(/reasons|No moves yet/).first(),
      "/replay": page.getByRole("heading", { name: /earnings night of/ }),
      "/report-card": page.getByRole("heading", { name: "Calibration of the shipped forecaster" }),
    }[path];
    await expect(ready).toBeVisible();
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow, "horizontal page scroll").toBe(false);
    expect(errors, errors.join("\n")).toEqual([]);
  });
}
