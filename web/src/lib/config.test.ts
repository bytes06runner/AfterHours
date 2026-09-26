import { describe, expect, it } from "vitest";

import { fetchPublicConfig, parsePublicConfig, readWebEnv } from "./config";

const sample = {
  profile: "fork",
  chain: { key: "robinhood", chain_id: null, explorer_url: null, rpc_url: null },
  simulation: { oracle: false, collateral: false },
  vault: { name: "Afterhours USDG", symbol: "ahUSDG" },
  exchange_calendar: "XNYS",
  deployment: {},
  discovered: { morpho: { blue: "0x" + "1".repeat(40) } },
};

describe("parsePublicConfig", () => {
  it("accepts the document the API produces", () => {
    expect(parsePublicConfig(sample).vault.symbol).toBe("ahUSDG");
  });

  it("rejects a malformed address", () => {
    expect(() => parsePublicConfig({ ...sample, discovered: { usdg: "0x12" } })).toThrow(
      /Public config is invalid/,
    );
  });

  it("rejects a missing field", () => {
    const rest: Record<string, unknown> = { ...sample };
    delete rest.vault;
    expect(() => parsePublicConfig(rest)).toThrow();
  });
});

describe("fetchPublicConfig", () => {
  it("fetches and parses from the API base", async () => {
    let requested = "";
    const fake = (async (input: URL | RequestInfo) => {
      requested = String(input);
      return new Response(JSON.stringify(sample), { status: 200 });
    }) as typeof fetch;
    const cfg = await fetchPublicConfig("http://api.test", fake);
    expect(requested).toBe("http://api.test/v1/config/public");
    expect(cfg.profile).toBe("fork");
  });

  it("says what happened when the API fails", async () => {
    const fake = (async () => new Response("", { status: 503 })) as typeof fetch;
    await expect(fetchPublicConfig("http://api.test", fake)).rejects.toThrow(/503/);
  });
});

describe("readWebEnv", () => {
  it("requires an API base URL", () => {
    expect(() => readWebEnv({})).toThrow();
    expect(
      readWebEnv({ NEXT_PUBLIC_API_BASE_URL: "http://api.test" }).NEXT_PUBLIC_API_BASE_URL,
    ).toBe("http://api.test");
  });
});
