import { expect, test } from "@playwright/test";

import { ADMIN, API } from "./env";

/**
 * The demo as a visitor sees it: the landing page, a forced close-out on the simulated chain
 * (the same admin endpoint `make demo` uses), the new telegram in the ledger, and its hash
 * matched onchain in the browser.
 */
test("closing bell: the vault moves, prints a reason, and the reason verifies", async ({
  page,
  request,
}) => {
  test.skip(!API || !ADMIN, "needs API_BASE_URL, ADMIN_TOKEN and a running stack (make up)");
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview the close" })).toBeVisible();

  const before = (await (await request.get(`${API}/v1/reasons`)).json()) as { total: number };
  let moved = false;
  for (let i = 0; i < 6 && !moved; i++) {
    const res = await request.post(`${API}/v1/sim/close-out`, {
      headers: { authorization: `Bearer ${ADMIN}` },
      timeout: 120_000,
    });
    expect(res.ok(), await res.text()).toBe(true);
    const body = (await res.json()) as { plan: { executed_markets?: string[] } };
    moved = (body.plan.executed_markets ?? []).length > 0;
  }
  expect(moved, "a close-out should move money").toBe(true);

  await page.goto("/ledger");
  await expect(page.getByText(/\d+ reasons/)).toBeVisible();
  const after = (await (await request.get(`${API}/v1/reasons`)).json()) as { total: number };
  expect(after.total).toBeGreaterThan(before.total);

  const first = page.getByRole("article").first();
  await first.getByRole("button", { name: "Verify on chain" }).click();
  await expect(first.getByRole("status")).toContainText("Matched onchain", { timeout: 30_000 });

  await page.goto("/vault");
  await expect(page.getByRole("heading", { name: "Allocation board" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Latest telegrams" })).toBeVisible();
});
