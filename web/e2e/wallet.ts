import type { Page } from "@playwright/test";

/**
 * A minimal EIP-1193 wallet for tests on a local Anvil chain. It forwards every request to the
 * node and sends transactions from an impersonated test account, so no key is involved.
 */
export async function injectTestWallet(
  page: Page,
  rpcUrl: string,
  account: string,
  chainIdHex: string,
) {
  await page.addInitScript(
    ({ rpc, from, chainId }) => {
      let id = 0;
      const call = async (method: string, params: unknown[] = []) => {
        const res = await fetch(rpc, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ jsonrpc: "2.0", id: ++id, method, params }),
        });
        const body = await res.json();
        if (body.error)
          throw Object.assign(new Error(body.error.message), { code: body.error.code });
        return body.result;
      };
      const listeners: Record<string, ((...a: unknown[]) => void)[]> = {};
      const provider = {
        isMetaMask: true,
        request: async ({ method, params }: { method: string; params?: unknown[] }) => {
          if (method === "eth_requestAccounts" || method === "eth_accounts") return [from];
          if (method === "eth_chainId") return chainId;
          if (method === "wallet_switchEthereumChain" || method === "wallet_addEthereumChain")
            return null;
          if (method === "eth_sendTransaction") {
            await call("anvil_impersonateAccount", [from]);
            return call(method, params ?? []);
          }
          return call(method, params ?? []);
        },
        on: (event: string, fn: (...a: unknown[]) => void) => {
          (listeners[event] ??= []).push(fn);
        },
        removeListener: (event: string, fn: (...a: unknown[]) => void) => {
          listeners[event] = (listeners[event] ?? []).filter((f) => f !== fn);
        },
      };
      Object.defineProperty(window, "ethereum", { value: provider, configurable: true });
    },
    { rpc: rpcUrl, from: account, chainId: chainIdHex },
  );
}
