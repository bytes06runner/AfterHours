import { describe, expect, it } from "vitest";

import card from "./__fixtures__/card.json";
import { canonicalCard, reasonHash } from "./verify";

describe("reason hash", () => {
  it("matches the hash the Python bot anchored onchain", () => {
    // The fixture is a real card from the local demo; reason_hash was computed by
    // engine/afterhours/explain/reason.py (rfc8785 + keccak256) and logged to the registry.
    expect(reasonHash(card)).toBe(card.reason_hash);
  });

  it("ignores the tx block and the stored hash", () => {
    const withTx = { ...card, tx: { chain_id: 1, reallocate_tx: "0x01", registry_tx: "0x02" } };
    expect(reasonHash(withTx)).toBe(card.reason_hash);
    expect(canonicalCard(withTx)).not.toContain("registry_tx");
  });

  it("changes when any field changes", () => {
    expect(reasonHash({ ...card, amount_usdg: "1.00" })).not.toBe(card.reason_hash);
  });

  it("sorts keys (RFC 8785)", () => {
    expect(canonicalCard({ b: 1, a: { d: 2, c: 3 } })).toBe('{"a":{"c":3,"d":2},"b":1}');
  });
});
