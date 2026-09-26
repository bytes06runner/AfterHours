"use client";

import { useConfig } from "@/lib/queries";

/** Always visible when any data or contract on screen is simulated (DESIGN section 6). */
export function SimulationBanner() {
  const { data } = useConfig();
  if (!data) return null;
  const parts = [
    data.simulation.oracle ? "simulated prices" : null,
    data.simulation.collateral ? "simulated Stock Tokens and USDG" : null,
    data.chain.chain_id === null || data.profile === "local" || data.profile === "fork"
      ? `a ${data.profile} chain`
      : null,
  ].filter(Boolean);
  if (parts.length === 0) return null;
  return (
    <div
      role="note"
      className="border-b border-rule bg-surface px-4 py-2 text-center text-[14px] font-semibold"
    >
      Simulation: {parts.join(", ")}. Nothing here is real money.
    </div>
  );
}
