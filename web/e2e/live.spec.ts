import { randomBytes } from "node:crypto";

import type { APIRequestContext } from "@playwright/test";

import { API, isApi } from "./env";
import { expect, test } from "./fixtures";

/** GET a live endpoint, waiting while the API answers "still reading" (503) after a start. */
async function liveJson(request: APIRequestContext, path: string) {
  for (let i = 0; i < 40; i++) {
    const res = await request.get(new URL(path, API).href);
    if (res.ok()) return res.json();
    await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error(`${path} did not answer`);
}

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
    test.setTimeout(180_000);
    const board = await liveJson(request, "/v1/live/board");
    await page.goto("/live");
    await expect(page.getByRole("heading", { level: 1, name: "Live risk board" })).toBeVisible();
    await expect(page.getByText(/^Live: .+ mainnet, read-only/)).toBeVisible();
    // The vault stays labelled a simulation while this page reads mainnet live.
    await expect(page.getByRole("note").filter({ hasText: "Simulation" })).toBeVisible();
    const rows = page.getByTestId("board-row");
    await expect(rows).toHaveCount(board.stocks.length, { timeout: 60_000 });
    const first = rows.first();
    await expect(first).toContainText(/Regular session|Extended hours|Weekend price|Frozen/);
    await expect(first).toContainText(/Price quality \d+, (good|fair|poor)/);
    await expect(first).toContainText(/\d+(\.\d+)?%/);
    await expect(first).toContainText("New York");

    type R = { regime?: { regime: string; quality: { grade: string | null } } };
    const count = async (name: string, n: number) => {
      await page.getByRole("button", { name }).click();
      if (n > 0) await expect(rows).toHaveCount(n);
      else await expect(page.getByText("No stock matches this filter right now.")).toBeVisible();
    };
    await count("Frozen now", board.stocks.filter((r: R) => r.regime?.regime === "frozen").length);
    await count(
      "Poor price quality",
      board.stocks.filter((r: R) => r.regime?.quality.grade === "poor").length,
    );
  });

  test("the landing shows every Stock Token's price regime", async ({ page, request }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    test.setTimeout(180_000);
    const reg = await liveJson(request, "/v1/live/regimes");
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Frozen today, thin tomorrow" })).toBeVisible();
    const panel = page.getByTestId("regimes-now");
    const tiles = panel.getByRole("list", { name: "Stock Tokens by price regime" });
    await expect(tiles.getByRole("listitem")).toHaveCount(4, { timeout: 60_000 });
    await expect(tiles.getByRole("listitem").filter({ hasText: "Frozen" })).toContainText(
      String(reg.counts.frozen),
    );
    await expect(
      panel.getByRole("heading", { name: "Least trustworthy prices right now" }),
    ).toBeVisible();
  });

  test("a weekend price is named as such, with its plain line", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL");
    const token = {
      symbol: "NVDA",
      feed_price: 235.1,
      regime: "weekend_venue",
      label: "Weekend price",
      since: "2026-10-03T00:00:00+00:00",
      feed_age_seconds: 600,
      typical_interval_minutes: 272.2,
      dex_price: 237.4,
      divergence: 0.0098,
      depth_usd: 50000,
      quality: { score: 41, grade: "poor", marks: {}, used: ["depth", "divergence", "staleness"] },
      line: "Weekend price: the exchange is shut but the feed posted 10 minutes ago, so it follows a weekend source, which can be thin.",
    };
    await page.route(
      (url) => isApi(url) && url.pathname === "/v1/live/regimes",
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            network: "Robinhood Chain",
            block: 1,
            as_of: "2026-10-03T10:00:00+00:00",
            calendar: "closed",
            segment: "frozen",
            closed_since: "2026-10-03T00:00:00+00:00",
            counts: { regular: 0, extended: 0, weekend_venue: 1, frozen: 0 },
            method: "docs/REGIME.md",
            tokens: [token],
          }),
        }),
    );
    await page.goto("/");
    const panel = page.getByTestId("regimes-now");
    await expect(panel).toContainText("Price quality 41, poor");
    await expect(panel).toContainText("follows a weekend source, which can be thin");
  });

  test("says when mainnet cannot be reached", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL");
    test.setTimeout(150_000); // the board retries for about a minute before it gives up
    await page.route(
      (url) => isApi(url) && url.pathname.startsWith("/v1/live/"),
      (route) => route.fulfill({ status: 503, body: "{}" }),
    );
    await page.goto("/live");
    await expect(page.getByRole("main").getByRole("alert").first()).toContainText(
      "Can't reach Robinhood Chain right now.",
      { timeout: 120_000 },
    );
  });

  test("while the first board is read, it says so instead of waiting", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL");
    test.setTimeout(150_000);
    await page.route(
      (url) => isApi(url) && url.pathname === "/v1/live/board",
      (route) =>
        route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "Still reading every Stock Token price feed on mainnet.",
          }),
        }),
    );
    await page.goto("/live");
    await expect(page.getByText("Reading every Stock Token price feed on mainnet.")).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert").first()).toContainText(
      "Still reading every Stock Token price feed on mainnet.",
      { timeout: 120_000 },
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
    const ex = await liveJson(request, "/v1/live/examples");
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
    const pos = await liveJson(request, `/v1/live/positions/${first}`);
    const loan = pos.positions.find((p: { ltv?: number }) => p.ltv !== undefined);
    await expect(card).toContainText(`You borrowed`);
    await expect(card).toContainText(loan.loan_symbol);
  });
});
