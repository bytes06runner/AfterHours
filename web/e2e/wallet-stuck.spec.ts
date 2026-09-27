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

/** Phone wallets draw a WalletConnect QR (needs NEXT_PUBLIC_WC_PROJECT_ID on the web server). */
test("a phone wallet shows a scannable QR code without errors", async ({ page }) => {
  test.skip(!API, "needs API_BASE_URL and a running stack (make up)");
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/vault");
  await page.getByRole("button", { name: "Connect" }).first().click();
  const rainbow = page.getByRole("button", { name: /^Rainbow/ }).first();
  test.skip(
    !(await rainbow.isVisible().catch(() => false)),
    "no WalletConnect project id on this web server",
  );
  await rainbow.click();
  await expect(page.getByText("Scan with Rainbow")).toBeVisible();
  await expect
    .poll(async () => page.locator('[role="dialog"] svg path').count(), { timeout: 20_000 })
    .toBeGreaterThan(0);
  expect(errors, errors.join("\n")).toEqual([]);
});
