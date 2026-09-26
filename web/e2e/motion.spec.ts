import { expect, test } from "@playwright/test";

import { API } from "./env";

test.use({ reducedMotion: "reduce" });

test("reduced motion: no pinned story, static ticker, instant replay", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Checked against history." })).toBeVisible();
  // Without motion every step carries its own visual; nothing is pinned.
  await expect(page.locator(".sticky")).toHaveCount(0);
  await expect(page.getByRole("img", { name: /Earnings-night gaps/ })).toBeVisible();
  const animation = await page
    .locator(".ticker-track")
    .first()
    .evaluate((el) => getComputedStyle(el).animationName);
  expect(animation).toBe("none");
  // The closing bell preview still works, as a short crossfade.
  const before = await page.evaluate(() => document.documentElement.dataset.phase);
  await page.getByRole("button", { name: "Preview the close" }).click();
  expect(before).toMatch(/day|night/);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.dataset.phase), { timeout: 3_000 })
    .not.toBe(before);

  await page.goto("/replay");
  await expect(page.getByRole("button", { name: "Jump to the gap" })).toBeVisible();
});
