import type { PublicConfig } from "./config";

/** What is simulated, in words ("" when nothing is). */
export function simulationParts(data: PublicConfig): string {
  return [
    data.simulation.oracle ? "simulated prices" : null,
    data.simulation.collateral ? "simulated Stock Tokens and USDG" : null,
    data.chain.chain_id === null || data.profile === "local" || data.profile === "fork"
      ? `a ${data.profile} chain`
      : null,
  ]
    .filter(Boolean)
    .join(", ");
}
