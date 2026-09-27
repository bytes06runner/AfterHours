import { API } from "./env";
import { expect, test } from "./fixtures";

/** A wallet that never answers the connection request (what a Brave user saw) gets a hint. */
test("a wallet that does not answer gets told where to approve", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
  test.setTimeout(60_000);
  await page.addInitScript(() => {
    const provider = {
      request: ({ method }: { method: string }) =>
        method === "eth_requestAccounts"
          ? new Promise(() => undefined) // never answers
          : method === "eth_accounts"
            ? Promise.resolve([])
            : method === "eth_chainId"
              ? Promise.resolve("0x1")
              : Promise.resolve(null),
      on: () => undefined,
      removeListener: () => undefined,
    };
    Object.defineProperty(window, "ethereum", { value: provider, configurable: true });
  });
  await page.goto("/vault");
  await page.getByRole("button", { name: "Connect" }).first().click();
  await page
    .getByRole("button", { name: /Browser Wallet/ })
    .first()
    .click();
  await expect(page.getByRole("alert").filter({ hasText: "has not answered" })).toBeVisible({
    timeout: 25_000,
  });
});
