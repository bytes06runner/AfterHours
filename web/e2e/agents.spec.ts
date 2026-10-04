import type { APIRequestContext } from "@playwright/test";

import { API } from "./env";
import { expect, test } from "./fixtures";

async function json(request: APIRequestContext, path: string) {
  const res = await request.get(new URL(path, API).href);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

test.describe("agents page", () => {
  test("shows the install config, the tools and a real captured session", async ({
    page,
    request,
  }) => {
    test.skip(!API, "needs API_BASE_URL and a running API");
    const cfg = await json(request, "/v1/config/public");
    const session = await json(request, "/v1/agents/example-session");
    await page.goto("/agents");
    await expect(page.getByRole("heading", { level: 1, name: "Agents" })).toBeVisible();
    await expect(page.getByText("Read-only: no tool can sign, send or trade")).toBeVisible();
    // The Claude Desktop config is built from public config and the API base URL.
    const configBlock = page.locator("pre").first();
    await expect(configBlock).toContainText(cfg.agents.mcp_source);
    await expect(configBlock).toContainText(cfg.agents.api_url_env);
    await expect(page.getByRole("button", { name: "Copy Claude Desktop config" })).toBeVisible();
    for (const tool of [
      "market_status()",
      "get_weekend_risk(ticker)",
      "check_position(address)",
      "explain_move(reason_id)",
    ])
      await expect(page.getByRole("cell", { name: tool })).toBeVisible();
    const steps = session.session.filter((s: { tool?: string }) => s.tool);
    const shown = page.getByTestId("agent-session").locator("blockquote");
    await expect(shown).toHaveCount(steps.length);
    await expect(shown.first()).toHaveText(steps[0].result.summary);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    expect(overflow).toBe(false);
  });

  test("the agent REST endpoints are rate limited and read-only", async ({ request }) => {
    test.skip(!API, "needs API_BASE_URL and a running API");
    const spec = await json(request, "/openapi.json");
    const agentPaths = Object.keys(spec.paths).filter((p: string) => p.startsWith("/v1/agent/"));
    expect(agentPaths.length).toBe(4);
    for (const p of agentPaths) expect(Object.keys(spec.paths[p])).toEqual(["get"]);
  });
});
