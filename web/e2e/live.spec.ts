import { randomBytes } from "node:crypto";

import { API, isApi } from "./env";
import { expect, test } from "./fixtures";

/**
 * The risk board and the position checker read Robinhood Chain mainnet through the local API,
 * so these tests need the stack (make up) and a reachable public RPC.
 */
test.describe("live risk board", () => {
  test("lists every Stock Token feed with its state and tonight's bad case", async ({
    page,
    request,
  }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    const board = await (await request.get(new URL("/v1/live/board", API).href)).json();
    await page.goto("/live");
    await expect(page.getByRole("heading", { level: 1, name: "Live risk board" })).toBeVisible();
    await expect(page.getByText(/^Live: .+ mainnet, read-only/)).toBeVisible();
    // The vault stays labelled a simulation while this page reads mainnet live.
    await expect(page.getByRole("note").filter({ hasText: "Simulation" })).toBeVisible();
    const rows = page.getByTestId("board-row");
    await expect(rows).toHaveCount(board.stocks.length, { timeout: 60_000 });
    const first = rows.first();
    await expect(first).toContainText(/Frozen for the weekend|No update for|Updating/);
    await expect(first).toContainText(/\d+(\.\d+)?%/);
    await expect(first).toContainText("New York");

    const frozen = board.stocks.filter(
      (r: { status: { state: string } | null }) => r.status?.state === "frozen",
    ).length;
    await page.getByRole("button", { name: "Frozen now" }).click();
    if (frozen > 0) await expect(rows).toHaveCount(frozen);
    else await expect(page.getByText("No stock matches this filter right now.")).toBeVisible();
  });

  test("says when mainnet cannot be reached", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL");
    await page.route(
      (url) => isApi(url) && url.pathname.startsWith("/v1/live/"),
      (route) => route.fulfill({ status: 503, body: "{}" }),
    );
    await page.goto("/live");
    await expect(page.getByRole("main").getByRole("alert").first()).toContainText(
      "Can't reach Robinhood Chain right now.",
      { timeout: 30_000 },
    );
  });
});

test.describe("position checker", () => {
  test("rejects something that is not an address", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    await page.goto("/positions");
    await page.getByLabel("Wallet address").fill("not-an-address");
    await page.getByRole("button", { name: "Check", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "not a wallet address" })).toBeVisible();
  });

  test("an empty wallet has no positions", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    const fresh = `0x${randomBytes(20).toString("hex")}`;
    await page.goto("/positions");
    await page.getByLabel("Wallet address").fill(fresh);
    await page.getByRole("button", { name: "Check", exact: true }).click();
    await expect(page.getByText(/^No positions for 0x/)).toBeVisible({ timeout: 60_000 });
    await expect(page).toHaveURL(new RegExp(`address=${fresh}`, "i"));
  });

  test("a live borrower shows LTV, liquidation price and tonight", async ({ page, request }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    test.setTimeout(180_000);
    const ex = await (await request.get(new URL("/v1/live/examples", API).href)).json();
    test.skip(ex.addresses.length === 0, "no open Stock Token borrow on mainnet right now");
    await page.goto("/positions");
    await page.getByText("Try a live borrower:").getByRole("button").first().click();
    const card = page.getByTestId("position").first();
    await expect(card).toBeVisible({ timeout: 60_000 });
    await expect(card).toContainText(/Your loan is \d+(\.\d+)?% of your collateral/);
    await expect(card).toContainText(/You would be liquidated if \w+ fell to/);
    await expect(page.getByTestId("tonight").first()).toContainText(
      /Tonight's bad case(,| is) a \d+(\.\d+)?% fall/,
    );
    await expect(page.getByTestId("tonight").first()).toContainText("New York");
    // Debt is shown in the loan token's own onchain symbol, never assumed.
    const first = new URL(page.url()).searchParams.get("address") ?? "";
    const pos = await (await request.get(new URL(`/v1/live/positions/${first}`, API).href)).json();
    const loan = pos.positions.find((p: { ltv?: number }) => p.ltv !== undefined);
    await expect(card).toContainText(`You borrowed`);
    await expect(card).toContainText(loan.loan_symbol);
  });
});
