import { API } from "./env";
import { expect, test } from "./fixtures";

const tonight = {
  period: {
    starts: "2026-10-09T20:00:00+00:00",
    ends: "2026-10-12T13:30:00+00:00",
    segment: "weekend",
    hours: 65.5,
  },
  alpha: 0.01,
  held_out_miss_rate: 0.017257,
  held_out_years: [2017, 2026],
};

function market(id: string, symbol: string, rec: string, label: string, extra: object) {
  return {
    market_id: id,
    symbol,
    lltv: 0.625,
    cushion: 0.2958,
    margin_limit: 0.1775,
    supplied_usdg: 1000,
    borrowed_usdg: 500,
    utilization: 0.5,
    exit_liquidity_usdg: 500,
    oracle: { state: "frozen", regime_label: "Frozen", quality: 0, quality_grade: "poor" },
    borrowers: { count: 2, top_share: 0.6 },
    tonight,
    bad_case_drop: 0.05,
    headroom: 0.2458,
    breach: false,
    highest_surviving_lltv: 0.915,
    highest_lltv_with_margin: 0.86,
    recommendation: rec,
    label,
    reason: `${symbol} reason.`,
    ...extra,
  };
}

/** A curator document shaped like /v1/live/curator, with one market per recommendation. */
const DOC = {
  network: "Robinhood Chain",
  block: 82622425,
  as_of: "2026-10-10T14:00:00+00:00",
  totals: { markets: 3, supplied_usdg: 3000, borrowed_usdg: 2490, utilization: 0.83 },
  summary: {
    reduce_cap: { markets: 1, supplied_usdg: 1000, borrowed_usdg: 500 },
    watch: { markets: 1, supplied_usdg: 1000, borrowed_usdg: 1000 },
    survives: { markets: 1, supplied_usdg: 1000, borrowed_usdg: 990 },
  },
  borrowers_scanned_to_block: 82622000,
  policy: { margin_fraction: 0.4, watch_utilization: 0.95, concentration_watch_share: 0.5 },
  markets: [
    market("0x" + "11".repeat(32), "META", "reduce_cap", "Reduce cap", {
      lltv: 0.915,
      cushion: 0.061,
      margin_limit: 0.037,
      bad_case_drop: 0.12,
      breach: true,
      highest_surviving_lltv: 0.77,
      highest_lltv_with_margin: 0.625,
    }),
    market("0x" + "22".repeat(32), "GOOGL", "watch", "Watch", {
      borrowed_usdg: 1000,
      utilization: 1,
      exit_liquidity_usdg: 0,
    }),
    market("0x" + "33".repeat(32), "NVDA", "survives", "Survives the modelled bad case", {}),
  ],
};

test.describe("curator view", () => {
  test("puts tonight's bad case against each market's cushion, with a call per market", async ({
    page,
  }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    await page.route("**/v1/live/curator", (r) => r.fulfill({ json: DOC }));
    await page.goto("/curators");
    await expect(
      page.getByRole("heading", { level: 1, name: "Which LLTV survives tonight?" }),
    ).toBeVisible();
    await expect(page.getByText(/^Live: .+ mainnet, read-only/)).toBeVisible();
    const wide = (page.viewportSize()?.width ?? 0) >= 768;
    const rows = page.getByTestId(wide ? "curator-row" : "curator-card");
    await expect(rows).toHaveCount(3);
    await expect(rows.first()).toContainText("META");
    await expect(rows.first()).toContainText("12.0%");
    await expect(rows.first()).toContainText("against a 6.1% cushion");
    await expect(rows.first()).toContainText("Reduce cap");
    await expect(rows.nth(1)).toContainText("Exit liquidity 0 USDG");
    // The measured coverage, never "1 in 100" alone.
    await expect(
      page.getByText(/beaten on 1\.73% of weekend periods, about 1 in 58/),
    ).toBeVisible();
    await page.getByRole("button", { name: "Cut or hold caps" }).click();
    await expect(rows).toHaveCount(1);
    await page.getByRole("button", { name: "Survives" }).click();
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText("NVDA");
  });

  test("says when mainnet cannot be read", async ({ page }) => {
    test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
    test.setTimeout(150_000); // like the risk board, it retries for about a minute first
    await page.route("**/v1/live/curator", (r) =>
      r.fulfill({ status: 503, json: { detail: "Can't reach Robinhood Chain right now." } }),
    );
    await page.goto("/curators");
    await expect(
      page.getByText("Reading every Stock Token lending market on mainnet."),
    ).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert").first()).toContainText(
      "Retrying in 10 seconds",
      { timeout: 120_000 },
    );
  });
});
