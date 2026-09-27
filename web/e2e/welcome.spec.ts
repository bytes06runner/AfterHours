import { expect, test } from "./fixtures";
import { API } from "./env";

test.use({ skipWelcome: false });

test("the welcome sequence opens onto the landing page and can be skipped", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL");
  await page.goto("/");
  const curtain = page.getByTestId("welcome");
  await expect(curtain).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /./ }).first()).toBeVisible();
  // It opens by itself once the page is ready, within a few seconds.
  await expect(curtain).toBeHidden({ timeout: 10_000 });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // Once per session: a reload goes straight to the page.
  await page.reload();
  await expect(page.getByTestId("welcome")).toHaveCount(0);
});

test("the welcome sequence can be skipped", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL");
  await page.goto("/");
  await page.getByRole("button", { name: "Skip" }).click();
  await expect(page.getByTestId("welcome")).toHaveCount(0);
});
