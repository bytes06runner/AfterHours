"use client";

import { useConfig } from "@/lib/queries";
import { simulationParts } from "@/lib/simulation";

/**
 * Always visible when any data or contract on screen is simulated (DESIGN section 6). The
 * server renders it from the public config (`initial`) so it is in the first paint and never
 * pushes the page down; the client keeps it current.
 */
export function SimulationBanner({ initial }: { initial: string | null }) {
  const { data } = useConfig();
  const parts = data ? simulationParts(data) : initial;
  if (!parts) return null;
  return (
    <div
      role="note"
      className="border-b border-rule bg-surface px-4 py-2 text-center text-[14px] font-semibold"
    >
      The vault is a simulation: {parts}. The risk board and position checker read mainnet live.
    </div>
  );
}
