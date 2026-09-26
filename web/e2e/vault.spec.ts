import { randomBytes } from "node:crypto";

import { expect, test } from "@playwright/test";

import { injectTestWallet } from "./wallet";

const RPC = process.env.ANVIL_RPC_URL ?? "";
// A fresh test address per run (no key needed on Anvil; the wallet impersonates it), so the
// faucet's per-address cooldown never blocks a rerun.
const ACCOUNT = `0x${randomBytes(20).toString("hex")}`;

test("deposit and withdraw USDG on the local chain", async ({ page }) => {
  test.skip(!RPC, "needs ANVIL_RPC_URL and a running stack (make up)");
  await injectTestWallet(page, RPC, ACCOUNT, "0x7a69");
  await page.goto("/vault");
  // The test wallet usually reconnects on its own; connect by hand only if it does not.
  const faucet = page.getByRole("button", { name: "Get test USDG (sim)" });
  try {
    await faucet.waitFor({ timeout: 10_000 });
  } catch {
    await page.getByRole("button", { name: "Connect" }).first().click();
    await page
      .getByRole("button", { name: /Browser Wallet|Injected|MetaMask/ })
      .first()
      .click();
  }
  await page.getByRole("button", { name: "Get test USDG (sim)" }).click();
  await expect(page.getByText(/Received 50,000 USDG \(sim\)/)).toBeVisible();

  await page.getByLabel("Amount in USDG").fill("1000");
  await page
    .getByRole("button", { name: /deposit USDG/i })
    .last()
    .click();
  await expect(page.getByText("Deposited 1,000.00 USDG.")).toBeVisible({ timeout: 60_000 });

  await page.getByRole("tab", { name: "Withdraw" }).click();
  await page.getByLabel("Amount in USDG").fill("400");
  await page.getByRole("button", { name: "Withdraw" }).last().click();
  await expect(page.getByText("Withdrawn 400.00 USDG.")).toBeVisible({ timeout: 60_000 });
});
